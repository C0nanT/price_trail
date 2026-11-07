# Imagem de produção do Price Trail: gunicorn atrás do Traefik da VPS.
# Construída pelo CI e publicada em ghcr.io/c0nant/price_trail; a VPS nunca compila.
FROM python:3.12.16-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DB_PATH=/data/app.db \
    DATA_DIR=/data/pdfs

# O importador chama o pdftotext.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# UID/GID fixos; /data já nasce com esse dono, e o volume nomeado herda a
# permissão na primeira montagem.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown 10001:10001 /data

WORKDIR /app

# Dependências antes do código: mudar o código não reinstala nada.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Só o pacote (com web/ e o app.css já gerado). Banco, PDFs e .env ficam de fora.
COPY pricetrail/ pricetrail/

USER 10001:10001
EXPOSE 8000

# Abre o SQLite e roda SELECT 1 (GET /health). Sem curl/wget na imagem.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD ["python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["gunicorn", "--config", "python:pricetrail.gunicorn_conf", "pricetrail.wsgi:create()"]
