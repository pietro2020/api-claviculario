"""Rotas de consulta, criação e cancelamento de reservas."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from .extensions import db
from .models import Key, Reservation
from .models import utc_now
from .utils import fail, parse_datetime

bp = Blueprint("reservations", __name__)
# Este Blueprint reúne as três ações do calendário: listar, criar e cancelar.


def reservation_json(reservation):
    """Formata reserva e seus nomes relacionados para resposta da API."""
    # reservation.key e reservation.user são relacionamentos ORM: SQLAlchemy
    # segue as chaves estrangeiras para buscar os registros relacionados.
    return {"id": reservation.id, "key_id": reservation.key_id, "key_name": reservation.key.name,
            "user_id": reservation.user_id, "user_name": reservation.user.name,
            "title": reservation.title, "starts_at": reservation.starts_at.isoformat() + "Z",
            "ends_at": reservation.ends_at.isoformat() + "Z", "status": reservation.status}


@bp.get("/api/reservations")
@jwt_required()
def list_reservations():
    # Os filtros from/to retornam apenas reservas que cruzam o período pedido.
    # A consulta é construída por etapas. Ainda não vai ao banco até chamar
    # .all() no final, então filtros opcionais podem ser adicionados antes.
    query = Reservation.query.filter(Reservation.status == "confirmed")
    if request.args.get("from"):
        try:
            query = query.filter(Reservation.ends_at > parse_datetime(request.args["from"]))
        except ValueError as exc:
            return fail(str(exc))
    if request.args.get("to"):
        try:
            query = query.filter(Reservation.starts_at < parse_datetime(request.args["to"]))
        except ValueError as exc:
            return fail(str(exc))
    if request.args.get("key_id"):
        query = query.filter_by(key_id=request.args.get("key_id", type=int))
    reservations = query.order_by(Reservation.starts_at).all()  # executa o SELECT
    return jsonify(reservations=[reservation_json(item) for item in reservations])


@bp.post("/api/reservations")
@jwt_required()
def create_reservation():
    # Primeiro converte os horários, depois valida intervalo e chave, e por fim
    # pesquisa sobreposição antes de gravar a nova reserva.
    data = request.get_json(silent=True) or {}  # dados enviados no corpo do POST
    try:
        key_id = int(data.get("key_id"))
        starts, ends = parse_datetime(data.get("starts_at")), parse_datetime(data.get("ends_at"))
    except (ValueError, TypeError):
        return fail("Informe key_id e datas ISO 8601 válidas em starts_at e ends_at.")
    if starts >= ends or starts < utc_now():
        return fail("O início deve ser futuro e anterior ao fim.")
    key = db.session.get(Key, key_id)
    if not key or not key.active:
        return fail("Chave não encontrada ou inativa.", 404)
    # Dois intervalos se cruzam se o novo começa antes do fim existente e
    # termina depois do início existente. A comparação permite reservas coladas.
    overlap = Reservation.query.filter(Reservation.key_id == key_id,
                                       Reservation.status == "confirmed",
                                       Reservation.starts_at < ends,
                                       Reservation.ends_at > starts).first()
    if overlap:
        return fail("A chave já possui reserva nesse intervalo.", 409)
    # A identidade vem do token validado, então o cliente não escolhe em nome
    # de qual usuário criar a reserva.
    reservation = Reservation(key_id=key_id, user_id=int(get_jwt_identity()),
                              title=(data.get("title") or "Aula").strip(),
                              starts_at=starts, ends_at=ends)
    db.session.add(reservation)  # prepara novo registro dentro da transação
    db.session.commit()  # persiste a reserva no banco
    return jsonify(reservation=reservation_json(reservation)), 201


@bp.delete("/api/reservations/<int:reservation_id>")
@jwt_required()
def cancel_reservation(reservation_id):
    # <int:reservation_id> na URL faz o Flask converter esse trecho em inteiro.
    reservation = db.session.get(Reservation, reservation_id)
    if not reservation:
        return fail("Reserva não encontrada.", 404)
    user_id = int(get_jwt_identity())
    if reservation.user_id != user_id and get_jwt().get("role") != "admin":
        return fail("Você só pode cancelar sua própria reserva.", 403)
    if reservation.status != "confirmed":
        return fail("Somente reservas confirmadas podem ser canceladas.", 409)
    # Mantém o registro histórico; reservas canceladas deixam de bloquear horário.
    reservation.status = "cancelled"  # atualização ORM: será gravada no commit
    db.session.commit()
    return "", 204
