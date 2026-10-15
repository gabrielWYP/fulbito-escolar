# syntax=docker/dockerfile:1

# ---- Etapa build: instala dependencias en un venv aislado ----
FROM python:3.12-slim AS build
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Etapa runtime: imagen mínima, no-root, read-only friendly ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATA_DIR=/data \
    SEED_DEMO=true

# Usuario/grupo no-root fijo (uid/gid 10001)
RUN groupadd -g 10001 fulbito \
 && useradd -u 10001 -g 10001 -m -s /usr/sbin/nologin fulbito

COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY app ./app

# Directorio de datos escribible por el usuario no-root (montado tmpfs/volumen en runtime)
RUN mkdir -p /data && chown -R 10001:10001 /data /app

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

# Detrás de reverse proxy (Traefik -> Cloudflare): honrar X-Forwarded-*
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
