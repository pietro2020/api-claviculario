"""Rotas para cadastrar e consultar chaves."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from .auth import admin_required
from .extensions import db
from .models import Key, KeyLoan
from .utils import fail

bp = Blueprint("keys", __name__)
# As rotas deste módulo só são registradas quando create_app registra este bp.


def current_holders():
    """Retorna mapa chave_id -> usuário para empréstimos ainda abertos."""
    # query(...) escolhe apenas as colunas necessárias; filter(...) vira um
    # WHERE SQL; all() executa a consulta e traz as linhas como tuplas.
    rows = db.session.query(KeyLoan.key_id, KeyLoan.user_id).filter(KeyLoan.returned_at.is_(None)).all()
    # O dicionário torna rápida a busca de responsável para cada chave.
    return {key_id: user_id for key_id, user_id in rows}


@bp.get("/api/keys")
@jwt_required()
def list_keys():
    # @jwt_required bloqueia visitantes sem token. Flask verifica esse decorador
    # antes de chamar a função da rota.
    # .all() executa a consulta e devolve uma lista de objetos Key.
    keys = Key.query.filter_by(active=True).order_by(Key.code).all()
    holders = current_holders()
    # A compreensão de lista chama public() para transformar cada objeto em
    # dados simples, que jsonify consegue enviar como JSON.
    return jsonify(keys=[key.public(holders.get(key.id)) for key in keys])


@bp.post("/api/keys")
@admin_required
def create_key():
    # O decorador @admin_required foi definido no módulo auth. Ele é reutilizado
    # aqui para que somente administradores possam alterar o inventário.
    data = request.get_json(silent=True) or {}
    if not data.get("code") or not data.get("name"):
        return fail("Informe code e name.")
    key = Key(code=data["code"].strip(), name=data["name"].strip(),
              description=data.get("description"), sensor_id=data.get("sensor_id"))
    db.session.add(key)  # marca o objeto para INSERT quando a transação for confirmada
    try:
        db.session.commit()  # salva; aqui o banco também verifica campos UNIQUE
    except IntegrityError:
        db.session.rollback()  # desfaz a transação que falhou e limpa a sessão ORM
        return fail("Código ou identificador do sensor já cadastrado.", 409)
    return jsonify(key=key.public()), 201
