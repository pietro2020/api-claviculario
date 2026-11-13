"""Factory da aplicação Flask: configura extensões e registra as rotas."""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.security import generate_password_hash

from .extensions import db, jwt
from .models import User

load_dotenv()


def create_app(test_config=None):
    """Cria e configura o servidor Flask (padrão de projeto chamado Application Factory).

    Em vez de configurar o servidor diretamente ao importar um arquivo, esta
    função monta uma aplicação pronta. Isso facilita trocar configurações e
    separar configuração de inicialização.
    """
    # Flask(__name__) cria a aplicação. __name__ ajuda Flask a localizar recursos
    # deste pacote, como templates e arquivos estáticos, caso sejam adicionados.
    app = Flask(__name__)
    # config é um dicionário de opções da aplicação. os.getenv lê variáveis de
    # ambiente, usadas para não escrever senhas diretamente no código.
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///claviculario.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-only-change-me"),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "dev-only-change-me-too"),
        JWT_ACCESS_TOKEN_EXPIRES=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60")) * 60,
    )
    # Permite substituir configurações ao criar um app em outro contexto.
    if test_config:
        app.config.update(test_config)

    # As extensões são ligadas ao app aqui para facilitar configuração e reuso.
    db.init_app(app)  # conecta SQLAlchemy a esta aplicação Flask
    jwt.init_app(app)  # conecta verificação de JWT às requisições desta aplicação

    # Importar os blueprints centralmente e registrá-los mantém cada grupo de
    # rotas em seu próprio módulo.
    from .auth import bp as auth_bp
    from .device import bp as device_bp
    from .keys import bp as keys_bp
    from .loans import bp as loans_bp
    from .reservations import bp as reservations_bp

    # register_blueprint liga as URLs definidas em cada arquivo ao servidor.
    app.register_blueprint(auth_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(keys_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(reservations_bp)

    @app.get("/health")
    def health():
        """Verificação simples para saber se o processo está respondendo."""
        return jsonify(status="ok")

    @app.cli.command("init-db")
    def init_db():
        """Cria tabelas e, se configurado, o primeiro administrador."""
        with app.app_context():
            # app_context fornece o contexto que extensões Flask precisam para
            # saber qual configuração e banco estão ativos neste momento.
            db.create_all()  # cria tabelas que ainda não existirem; não apaga dados
            email = os.getenv("ADMIN_EMAIL", "").lower().strip()
            password = os.getenv("ADMIN_PASSWORD")
            # Só cria a conta inicial quando as variáveis estiverem definidas;
            # rodar o comando de novo não duplica o administrador.
            if email and password and not User.query.filter_by(email=email).first():
                db.session.add(User(
                    name=os.getenv("ADMIN_NAME", "Administrador"),
                    email=email,
                    password_hash=generate_password_hash(password),
                    role="admin",
                ))
                db.session.commit()
                print(f"Administrador criado: {email}")
            print("Banco inicializado.")

    return app
