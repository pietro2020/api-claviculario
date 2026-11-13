"""Extensões compartilhadas, inicializadas pela factory da aplicação.

São criadas sem app aqui para evitar dependência circular entre arquivos.
create_app() conecta cada extensão à aplicação concreta usando init_app().
"""
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()  # fornece ORM: modelos Python, consultas e transações SQL
jwt = JWTManager()  # confere e cria os tokens Bearer usados nas rotas do site
