"""Consulta de empréstimos para o site."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from .models import KeyLoan

bp = Blueprint("loans", __name__)
# A rota é protegida e separada das rotas de escrita do ESP32: aqui só lemos.


@bp.get("/api/loans")
@jwt_required()
def list_loans():
    # Cada chamada encadeada adiciona uma condição à consulta SQL.
    query = KeyLoan.query
    if request.args.get("active", "true").lower() == "true":
        query = query.filter(KeyLoan.returned_at.is_(None))
    # Conta comum só vê os próprios dados; admin pode consultar todos.
    if get_jwt().get("role") != "admin":
        query = query.filter_by(user_id=int(get_jwt_identity()))
    loans = query.order_by(KeyLoan.checked_out_at.desc()).all()  # executa o SELECT
    # Relacionamentos loan.key e loan.user incluem descrições úteis para a tela.
    return jsonify(loans=[{"id": loan.id, "key_id": loan.key_id,
                          "key_code": loan.key.code, "key_name": loan.key.name,
                          "user_id": loan.user_id, "user_name": loan.user.name,
                          "checked_out_at": loan.checked_out_at.isoformat() + "Z",
                          "returned_at": loan.returned_at.isoformat() + "Z" if loan.returned_at else None}
                         for loan in loans])
