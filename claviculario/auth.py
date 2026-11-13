"""Autenticação do site e administração de contas."""
# wraps mantém o nome/documentação da rota original ao criar o decorador abaixo.
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import User
from .utils import fail

bp = Blueprint("auth", __name__)
# Blueprint é um grupo de rotas. A aplicação principal registra este grupo em
# create_app(); por isso as rotas deste arquivo passam a fazer parte do servidor.


def admin_required(fn):
    """Decorador extra: autentica e depois confere o papel da conta."""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        # jwt_required valida o token antes de chegar aqui. get_jwt() lê os
        # dados (claims) que foram colocados dentro do token no login.
        if get_jwt().get("role") != "admin":
            return fail("Acesso permitido somente para administradores.", 403)
        # fn é a função da rota original; só executamos se a pessoa for admin.
        return fn(*args, **kwargs)
    return wrapper


@bp.post("/api/auth/login")
def login():
    # Flask disponibiliza o pedido HTTP atual pelo objeto request.
    # get_json lê o corpo JSON; silent=True evita exceção se o corpo estiver malformado.
    data = request.get_json(silent=True) or {}
    # .get evita erro quando email não foi enviado. lower/strip padronizam e-mail.
    user = User.query.filter_by(email=(data.get("email") or "").lower().strip()).first()
    # Um login só é aceito se a conta existe, está ativa e a senha confere.
    # A senha recebida é comparada ao hash armazenado, nunca descriptografada.
    if not user or not user.active or not check_password_hash(user.password_hash, data.get("password") or ""):
        return fail("E-mail ou senha inválidos.", 401)
    # O token representa o login; o navegador o envia nas próximas requisições.
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    # jsonify transforma dicionários Python em uma resposta HTTP JSON.
    return jsonify(access_token=token, token_type="Bearer", user=user.public())


@bp.get("/api/auth/me")
@jwt_required()
def me():
    # jwt_required colocou a identidade do token no contexto desta requisição.
    user = db.session.get(User, int(get_jwt_identity()))
    # A expressão condicional escolhe resposta de sucesso ou erro em uma linha.
    return (jsonify(user=user.public()), 200) if user and user.active else fail("Usuário não encontrado.", 404)


@bp.post("/api/users")
@admin_required
def create_user():
    # A senha nesta rota é definida pelo administrador, mas também é guardada
    # como hash. O endpoint não devolve senha nem hash na resposta.
    data = request.get_json(silent=True) or {}
    name, email, password = data.get("name"), (data.get("email") or "").lower().strip(), data.get("password")
    if not name or not email or not password or len(password) < 8:
        return fail("Informe nome, e-mail e senha com pelo menos 8 caracteres.")
    if User.query.filter_by(email=email).first():
        return fail("E-mail já cadastrado.", 409)
    role = data.get("role", "user")
    if role not in ("admin", "user"):
        return fail("Papel deve ser 'admin' ou 'user'.")
    rfid_uid = (data.get("rfid_uid") or "").strip().upper() or None
    if rfid_uid and User.query.filter_by(rfid_uid=rfid_uid).first():
        return fail("Esse cartão RFID já está associado a um usuário.", 409)
    # User(...) cria apenas um objeto Python por enquanto; add o coloca na
    # sessão ORM e commit envia de fato a instrução INSERT ao banco.
    user = User(name=name.strip(), email=email, rfid_uid=rfid_uid,
                password_hash=generate_password_hash(password), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify(user=user.public()), 201
