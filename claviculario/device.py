"""Ponto de entrada de eventos enviados pelo ESP32."""
import os

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import AccessEvent, Key, KeyLoan, User, utc_now
from .utils import fail, parse_datetime

bp = Blueprint("device", __name__)
# Este Blueprint fala com o firmware; suas credenciais são diferentes do JWT do site.


@bp.post("/api/device/events")
def device_event():
    # Token confirma que o pedido veio do dispositivo configurado; RFID
    # identifica qual usuário realizou a operação.
    # O segredo vem do ambiente do servidor, não do corpo do pedido. Assim o
    # firmware precisa provar que conhece o token configurado.
    device_token = os.getenv("DEVICE_TOKEN")
    if not device_token or request.headers.get("X-Device-Token") != device_token:
        return fail("Dispositivo não autorizado.", 401)
    data = request.get_json(silent=True) or {}
    # Separar os campos em variáveis deixa as validações abaixo mais legíveis.
    event_id, action, key_ids = data.get("event_id"), data.get("action"), data.get("key_ids")
    if not event_id or len(str(event_id)) > 100 or action not in ("withdraw", "return") or not isinstance(key_ids, list) or not key_ids:
        return fail("Informe event_id, action ('withdraw' ou 'return') e uma lista key_ids.")
    # Repetições da mesma mensagem são normais em uma rede instável; não
    # devemos aplicar duas vezes uma operação física já registrada.
    if AccessEvent.query.filter_by(device_event_id=str(event_id)).first():
        return jsonify(message="Evento já recebido; nenhuma alteração duplicada foi feita.", duplicate=True), 200
    rfid_uid = (data.get("rfid_uid") or "").strip().upper()
    if not rfid_uid:
        return fail("Informe o rfid_uid lido no cartão.")
    user = User.query.filter_by(rfid_uid=rfid_uid, active=True).first()
    if not user:
        return fail("Usuário inexistente ou inativo.", 404)
    # Busca somente chaves ativas cujo ID está na lista enviada pelo ESP32.
    keys = Key.query.filter(Key.id.in_(key_ids), Key.active.is_(True)).all()
    if len({key.id for key in keys}) != len(set(key_ids)):
        return fail("Uma ou mais chaves não existem ou estão inativas.", 404)
    try:
        occurred = parse_datetime(data.get("occurred_at")) if data.get("occurred_at") else utc_now()
    except ValueError as exc:
        return fail(str(exc))

    # Cria um evento de auditoria. flush() abaixo envia o INSERT sem finalizar
    # a transação, permitindo obter event.id para ligar os empréstimos a ele.
    event = AccessEvent(device_event_id=str(event_id), user_id=user.id,
                        action=action, occurred_at=occurred)
    db.session.add(event)
    try:
        # A transação agrupa todas as chaves do evento. Se uma falhar, nenhuma
        # é atualizada. FOR UPDATE ajuda a serializar eventos concorrentes no MySQL.
        db.session.flush()  # envia o evento ao banco, mas ainda permite rollback
        for key in keys:
            # with_for_update pede ao MySQL para bloquear a linha lida enquanto
            # a transação está aberta, reduzindo conflitos de duas operações juntas.
            active_loan = (KeyLoan.query.filter_by(key_id=key.id, returned_at=None)
                           .with_for_update().first())
            if action == "withdraw":
                if active_loan:
                    db.session.rollback()
                    return fail(f"A chave {key.code} já está emprestada.", 409)
                # Retirada: cria empréstimo sem returned_at, portanto fica aberto.
                db.session.add(KeyLoan(key_id=key.id, user_id=user.id,
                                       checkout_event_id=event.id, checked_out_at=occurred))
            else:
                if not active_loan:
                    db.session.rollback()
                    return fail(f"A chave {key.code} não possui retirada ativa.", 409)
                # Devolução: fecha o empréstimo existente e aponta para o evento.
                active_loan.returned_at = occurred
                active_loan.return_event_id = event.id
        db.session.commit()  # só confirma quando todas as chaves foram processadas
    except IntegrityError:
        db.session.rollback()
        # Pode ocorrer se duas cópias do mesmo evento chegarem quase juntas.
        if AccessEvent.query.filter_by(device_event_id=str(event_id)).first():
            return jsonify(message="Evento já recebido.", duplicate=True), 200
        current_app.logger.exception("Falha de integridade ao registrar evento do dispositivo")
        return fail("Não foi possível registrar o evento.", 500)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao registrar evento do dispositivo")
        return fail("Não foi possível registrar o evento.", 500)
    # Código 201 significa que um novo recurso/evento foi criado com sucesso.
    return jsonify(event_id=event.id, device_event_id=event.device_event_id,
                   action=action, user_id=user.id, key_ids=key_ids,
                   occurred_at=occurred.isoformat() + "Z"), 201
