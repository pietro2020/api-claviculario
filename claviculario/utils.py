"""Funções pequenas reutilizadas pelas rotas."""
from datetime import datetime, timezone

from flask import jsonify


def fail(message, status=400):
    """Monta respostas de erro consistentes no formato JSON."""
    # Flask interpreta (corpo, status) como corpo da resposta e código HTTP.
    return jsonify(error=message), status


def parse_datetime(value):
    """Converte ISO 8601 recebido na API para datetime UTC usado no banco."""
    if not value:
        raise ValueError("Campo de data/hora obrigatório.")
    # Python converte Z (designação comum de UTC em JSON) para deslocamento +00:00.
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        # Converte qualquer fuso enviado para UTC; tira tzinfo porque MySQL
        # DATETIME não armazena fuso. O projeto interpreta todos os DATETIME como UTC.
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed
