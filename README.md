# Copa Escolar de Fulbito ⚽

Aplicación web para gestionar un campeonato escolar de futsal ("fulbito"):
fixture, resultados, tablas de posiciones, goleadores y fair play, con un panel
de administración protegido por contraseña.

Hecho con **FastAPI + Jinja2 + SQLite** (sin paso de build de Node). UI en
español (Perú), responsive (mobile-first), con tema claro/oscuro y accesible.

## Características

### Público (sin login)
- Portada con los torneos activos.
- Vista de torneo con pestañas: **Posiciones** (por grupo: PJ, PG, PE, PP, GF,
  GC, DG, Pts — 3/1/0 puntos, desempate Pts > DG > GF > nombre), **Fixture /
  calendario** por fecha (jornada), **Goleadores** y **Fair Play** (tarjetas
  amarillas y rojas).
- Páginas de equipo (con plantel), colegio y listado de colegios.

### Administración (login con contraseña)
- CRUD de torneos (nombre, categoría Sub-12/Sub-14/Sub-17, género, temporada),
  colegios, equipos, jugadores (nombre, dorsal, DNI opcional) y grupos.
- Generación automática de fixture todos-contra-todos (método del círculo, con
  BYE para número impar de equipos).
- Programación de fecha/hora y cancha por partido.
- Registro de resultado con goleadores y tarjetas.
- Creación manual de llaves (semifinal / final) desde equipos clasificados.

### Datos demo
En el primer arranque, si la BD está vacía y `SEED_DEMO=true` (por defecto), se
crea un torneo demo con 2 grupos de 4 equipos de colegios de Lima (ficticios),
jugadores y algunos partidos jugados.

## Ejecutar localmente

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

export ADMIN_PASSWORD=cambia-esto
export SESSION_SECRET=una-clave-larga-y-secreta
export DATA_DIR=./data        # dónde se guarda fulbito.db

uvicorn app.main:app --reload --port 8080
# Abrir http://127.0.0.1:8080
```

### Tests y lint

```bash
ruff check .
pytest -q
```

## Docker

```bash
docker build -t fulbito-escolar:local .
docker run -d --rm -p 127.0.0.1:8080:8080 \
  -e ADMIN_PASSWORD=cambia-esto -e SESSION_SECRET=secreto \
  --read-only --tmpfs /tmp --tmpfs /data:uid=10001 \
  fulbito-escolar:local
```

La imagen escucha en `0.0.0.0:8080`, corre como usuario no-root (uid/gid 10001)
y es compatible con `readOnlyRootFilesystem` (solo escribe en `DATA_DIR` y
`/tmp`). `GET /health` devuelve `{"status":"ok"}` y verifica el acceso a la BD.

## Variables de entorno

| Variable         | Requerida | Defecto         | Descripción |
|------------------|-----------|-----------------|-------------|
| `ADMIN_PASSWORD` | En prod   | — (admin off)   | Contraseña del panel. Sin ella, la administración queda deshabilitada. |
| `SESSION_SECRET` | En prod   | efímero         | Clave para firmar la cookie de sesión. Sin ella, las sesiones no sobreviven a un reinicio. |
| `DATA_DIR`       | No        | `/data`         | Carpeta de datos; la BD vive en `DATA_DIR/fulbito.db`. |
| `DB_PATH`        | No        | `DATA_DIR/fulbito.db` | Ruta explícita del archivo SQLite. |
| `SEED_DEMO`      | No        | `true`          | Si `true` y la BD está vacía, carga datos demo al arrancar. |

## Seguridad

- Cookie de sesión firmada (itsdangerous), `HttpOnly`, `SameSite=Lax`, y
  `Secure` cuando `X-Forwarded-Proto: https`.
- Protección CSRF en todos los formularios que cambian estado.
- Comparación de contraseña en tiempo constante y rate limiting de login
  (en memoria).
- Solo SQL parametrizado.
- Cabeceras de seguridad: CSP sin scripts inline, `X-Content-Type-Options`,
  `Referrer-Policy`, `frame-ancestors 'none'`.
