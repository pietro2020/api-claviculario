"""Ponto de entrada simples para `flask --app app` e execução local."""
import os

# Este arquivo é uma ponte curta para a estrutura do pacote claviculario.
# Flask procura a variável app ao executar `flask --app app ...`.
from claviculario import create_app

app = create_app()

if __name__ == "__main__":
    # Útil para desenvolvimento local; em produção use um servidor WSGI.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
