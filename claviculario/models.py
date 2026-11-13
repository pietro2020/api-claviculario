"""Definições das tabelas e relações do banco de dados."""
from datetime import datetime, timezone

from .extensions import db


# db.Model é a classe base do Flask-SQLAlchemy. Cada classe abaixo vira uma
# tabela; cada db.Column vira uma coluna dessa tabela.
def utc_now():
    """Retorna a hora UTC sem tzinfo, formato usado pelas colunas DATETIME."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """Conta do site; o UID opcional liga um cartão RFID à pessoa."""
    __tablename__ = "users"
    # primary_key é o identificador interno que outras tabelas podem referenciar.
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    rfid_uid = db.Column(db.String(64), unique=True)  # unique: um cartão por conta
    password_hash = db.Column(db.String(255), nullable=False)  # nunca guardar senha em texto
    role = db.Column(db.Enum("admin", "user", name="user_role"), nullable=False, default="user")
    active = db.Column(db.Boolean, nullable=False, default=True)  # desativar sem apagar histórico
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    def public(self):
        """Campos que podem ser devolvidos ao cliente; nunca inclui o hash."""
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


class Key(db.Model):
    """Cadastro físico de uma chave que pode ser reservada ou emprestada."""
    __tablename__ = "keys"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500))
    sensor_id = db.Column(db.String(80), unique=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    def public(self, holder_id=None):
        """Serializa chave e estado do empréstimo atual."""
        return {"id": self.id, "code": self.code, "name": self.name,
                "description": self.description, "sensor_id": self.sensor_id,
                "available": holder_id is None, "holder_user_id": holder_id}


class Reservation(db.Model):
    """Reserva de horário; apenas confirmadas bloqueiam o calendário."""
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    # ForeignKey (chave estrangeira) liga esta reserva à chave e ao usuário.
    key_id = db.Column(db.Integer, db.ForeignKey("keys.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.Enum("confirmed", "cancelled", "completed", name="reservation_status"), nullable=False, default="confirmed")
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    # relationship facilita acessar reservation.key e reservation.user em Python.
    key = db.relationship(Key)
    user = db.relationship(User)


class AccessEvent(db.Model):
    """Evento do ESP32; device_event_id impede aplicar reenvios em duplicidade."""
    __tablename__ = "access_events"
    id = db.Column(db.Integer, primary_key=True)
    # É o ID criado pelo próprio ESP32, único mesmo se uma mensagem for reenviada.
    device_event_id = db.Column(db.String(100), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.Enum("withdraw", "return", name="access_action"), nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    received_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    user = db.relationship(User)


class KeyLoan(db.Model):
    """Empréstimo; returned_at nulo indica que a chave continua fora."""
    __tablename__ = "key_loans"
    id = db.Column(db.Integer, primary_key=True)
    key_id = db.Column(db.Integer, db.ForeignKey("keys.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # Um empréstimo aponta para o evento que o abriu e, depois, para o evento
    # de devolução. As duas colunas apontam à mesma tabela, por isso foreign_keys
    # abaixo esclarece qual relação corresponde a cada coluna.
    checkout_event_id = db.Column(db.Integer, db.ForeignKey("access_events.id"), nullable=False)
    return_event_id = db.Column(db.Integer, db.ForeignKey("access_events.id"))
    checked_out_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    returned_at = db.Column(db.DateTime)
    key = db.relationship(Key)
    user = db.relationship(User)
    checkout_event = db.relationship(AccessEvent, foreign_keys=[checkout_event_id])
    return_event = db.relationship(AccessEvent, foreign_keys=[return_event_id])
