import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_home_public(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Copa Escolar de Fulbito" in r.text


def test_security_headers(client):
    r = client.get("/")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "frame-ancestors 'none'" in r.headers.get("content-security-policy", "")
    assert r.headers.get("x-frame-options") == "DENY"


def test_admin_requires_auth(client):
    # Sin cookie de sesión, /admin redirige a login (sin seguir el redirect)
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_admin_post_requires_auth(client):
    r = client.post(
        "/admin/torneos",
        data={"name": "X", "category": "Sub-14", "gender": "Masculino",
              "season": "2026", "csrf_token": "whatever"},
        follow_redirects=False,
    )
    # No autenticado -> redirect al login, no se crea nada
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_login_rejects_without_csrf(client):
    r = client.post("/admin/login", data={"password": "secreto-test", "csrf_token": "malo"})
    assert r.status_code == 400


def test_login_wrong_password(client):
    # Obtener token CSRF del formulario de login
    client.get("/admin/login")
    csrf = client.cookies.get("fulbito_csrf")
    r = client.post(
        "/admin/login",
        data={"password": "incorrecta", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 401


def test_login_success_then_admin_access(client):
    client.get("/admin/login")
    csrf = client.cookies.get("fulbito_csrf")
    r = client.post(
        "/admin/login",
        data={"password": "secreto-test", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin"
    assert client.cookies.get("fulbito_session")
    # Ahora /admin responde 200
    r2 = client.get("/admin")
    assert r2.status_code == 200
    assert "Panel de administración" in r2.text


def test_authed_post_rejects_bad_csrf(client):
    # Autenticar
    client.get("/admin/login")
    csrf = client.cookies.get("fulbito_csrf")
    client.post("/admin/login", data={"password": "secreto-test", "csrf_token": csrf},
                follow_redirects=False)
    # POST con CSRF inválido debe ser 400 aunque esté autenticado
    r = client.post(
        "/admin/torneos",
        data={"name": "Torneo Nuevo", "category": "Sub-12", "gender": "Mixto",
              "season": "2027", "csrf_token": "token-invalido"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_authed_create_tournament(client):
    client.get("/admin/login")
    csrf = client.cookies.get("fulbito_csrf")
    client.post("/admin/login", data={"password": "secreto-test", "csrf_token": csrf},
                follow_redirects=False)
    csrf = client.cookies.get("fulbito_csrf")
    r = client.post(
        "/admin/torneos",
        data={"name": "Torneo Prueba", "category": "Sub-17", "gender": "Femenino",
              "season": "2026", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Aparece en la home pública
    assert "Torneo Prueba" in client.get("/").text


def test_404_page(client):
    r = client.get("/torneo/999999")
    assert r.status_code == 404
    assert "404" in r.text
