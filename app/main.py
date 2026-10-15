"""Aplicación FastAPI - Copa Escolar de Fulbito."""
from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from . import db, queries, security
from .logic import generate_round_robin

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def _run_seed_if_needed() -> None:
    db.init_db()
    seed_demo = os.environ.get("SEED_DEMO", "true").lower() in ("1", "true", "yes")
    if seed_demo and db.is_empty():
        from . import seed as seed_mod

        conn = db.connect()
        try:
            seed_mod.seed(conn)
        finally:
            conn.close()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _run_seed_if_needed()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Copa Escolar de Fulbito", docs_url=None, redoc_url=None, lifespan=_lifespan
    )
    app.add_middleware(SecurityHeadersMiddleware)

    static_dir = BASE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ---- helpers de request ----
    def get_conn():
        conn = db.connect()
        try:
            yield conn
        finally:
            conn.close()

    def client_ip(request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def is_admin(request: Request) -> bool:
        return security.valid_session(request.cookies.get(security.SESSION_COOKIE))

    def is_https(request: Request) -> bool:
        return request.headers.get("x-forwarded-proto", "").lower() == "https"

    def render(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
        ctx.setdefault("admin", is_admin(request))
        ctx.setdefault("admin_enabled", security.ADMIN_ENABLED)
        return templates.TemplateResponse(request, name, ctx, status_code=status_code)

    def set_csrf(response: Response, request: Request) -> str:
        token = request.cookies.get(security.CSRF_COOKIE) or security.new_csrf_token()
        response.set_cookie(
            security.CSRF_COOKIE, token, httponly=False, samesite="lax",
            secure=is_https(request), max_age=security.SESSION_MAX_AGE,
        )
        return token

    def require_admin(request: Request):
        if not is_admin(request):
            return RedirectResponse("/admin/login", status_code=303)
        return None

    def check_csrf(request: Request, form_token: str) -> bool:
        return security.csrf_ok(request.cookies.get(security.CSRF_COOKIE), form_token)

    # ============ HEALTH ============
    @app.get("/health")
    def health():
        if db.db_ok():
            return {"status": "ok"}
        return Response(
            content='{"status":"error"}', status_code=503, media_type="application/json"
        )

    # ============ PÚBLICO ============
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        tours = queries.active_tournaments(conn)
        return render(request, "home.html", tournaments=tours)

    @app.get("/torneo/{tid}", response_class=HTMLResponse)
    def tournament_view(tid: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        t = queries.get_tournament(conn, tid)
        if not t:
            return render(request, "404.html", status_code=404)
        groups = queries.groups_of(conn, tid)
        standings = {g["id"]: queries.standings_for_group(conn, g["id"]) for g in groups}
        matches = queries.matches_of_tournament(conn, tid)
        scorers = queries.top_scorers(conn, tid)
        fp = queries.fairplay(conn, tid)
        return render(
            request, "tournament.html", t=t, groups=groups, standings=standings,
            matches=matches, scorers=scorers, fairplay=fp,
        )

    @app.get("/equipo/{team_id}", response_class=HTMLResponse)
    def team_view(team_id: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        team = queries.get_team(conn, team_id)
        if not team:
            return render(request, "404.html", status_code=404)
        players = queries.players_of_team(conn, team_id)
        return render(request, "team.html", team=team, players=players)

    @app.get("/colegio/{sid}", response_class=HTMLResponse)
    def school_view(sid: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        school = queries.get_school(conn, sid)
        if not school:
            return render(request, "404.html", status_code=404)
        teams = queries.teams_of_school(conn, sid)
        return render(request, "school.html", school=school, teams=teams)

    @app.get("/colegios", response_class=HTMLResponse)
    def schools_view(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        return render(request, "schools.html", schools=queries.all_schools(conn))

    # ============ AUTH ADMIN ============
    @app.get("/admin/login", response_class=HTMLResponse)
    def login_form(request: Request):
        if is_admin(request):
            return RedirectResponse("/admin", status_code=303)
        resp = render(request, "login.html", error=None)
        set_csrf(resp, request)
        return resp

    @app.post("/admin/login")
    def login(request: Request, password: str = Form(...), csrf_token: str = Form(...)):
        ip = client_ip(request)
        if not check_csrf(request, csrf_token):
            return render(request, "login.html", error="Token CSRF inválido.", status_code=400)
        if security.rate_limited(ip):
            return render(request, "login.html",
                          error="Demasiados intentos. Espera unos minutos.", status_code=429)
        if not security.ADMIN_ENABLED:
            return render(request, "login.html",
                          error="Administración deshabilitada (sin ADMIN_PASSWORD).", status_code=403)
        if security.verify_password(password):
            security.reset_attempts(ip)
            resp = RedirectResponse("/admin", status_code=303)
            resp.set_cookie(
                security.SESSION_COOKIE, security.make_session(), httponly=True,
                samesite="lax", secure=is_https(request), max_age=security.SESSION_MAX_AGE,
            )
            return resp
        security.record_attempt(ip)
        return render(request, "login.html", error="Contraseña incorrecta.", status_code=401)

    @app.post("/admin/logout")
    def logout(request: Request, csrf_token: str = Form(...)):
        if not check_csrf(request, csrf_token):
            return render(request, "login.html", error="Token CSRF inválido.", status_code=400)
        resp = RedirectResponse("/", status_code=303)
        resp.delete_cookie(security.SESSION_COOKIE)
        return resp

    # ============ ADMIN PANEL ============
    @app.get("/admin", response_class=HTMLResponse)
    def admin_home(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        resp = render(
            request, "admin/index.html",
            tournaments=queries.all_tournaments(conn),
            schools=queries.all_schools(conn),
        )
        set_csrf(resp, request)
        return resp

    # ---- Torneos ----
    @app.post("/admin/torneos")
    def create_tournament(
        request: Request, name: str = Form(...), category: str = Form(...),
        gender: str = Form(...), season: str = Form(...), csrf_token: str = Form(...),
        conn: sqlite3.Connection = Depends(get_conn),
    ):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        conn.execute(
            "INSERT INTO tournaments (name, category, gender, season, active) VALUES (?,?,?,?,1)",
            (name, category, gender, season),
        )
        conn.commit()
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/torneos/{tid}/toggle")
    def toggle_tournament(tid: int, request: Request, csrf_token: str = Form(...),
                          conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        conn.execute("UPDATE tournaments SET active = 1 - active WHERE id = ?", (tid,))
        conn.commit()
        return RedirectResponse("/admin", status_code=303)

    # ---- Colegios ----
    @app.post("/admin/colegios")
    def create_school(request: Request, name: str = Form(...),
                      district: str = Form(""), csrf_token: str = Form(...),
                      conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        conn.execute("INSERT INTO schools (name, district) VALUES (?,?)", (name, district or None))
        conn.commit()
        return RedirectResponse("/admin", status_code=303)

    # ---- Gestión de un torneo (grupos, equipos, jugadores, fixture, resultados) ----
    @app.get("/admin/torneo/{tid}", response_class=HTMLResponse)
    def admin_tournament(tid: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        t = queries.get_tournament(conn, tid)
        if not t:
            return render(request, "404.html", status_code=404)
        resp = render(
            request, "admin/tournament.html", t=t,
            groups=queries.groups_of(conn, tid),
            teams=queries.teams_of_tournament(conn, tid),
            schools=queries.all_schools(conn),
            matches=queries.matches_of_tournament(conn, tid),
        )
        set_csrf(resp, request)
        return resp

    @app.post("/admin/torneo/{tid}/grupos")
    def create_group(tid: int, request: Request, name: str = Form(...),
                     csrf_token: str = Form(...), conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        conn.execute("INSERT INTO groups (tournament_id, name) VALUES (?,?)", (tid, name))
        conn.commit()
        return RedirectResponse(f"/admin/torneo/{tid}", status_code=303)

    @app.post("/admin/torneo/{tid}/equipos")
    def create_team(tid: int, request: Request, school_id: int = Form(...),
                    name: str = Form(...), group_id: str = Form(""),
                    csrf_token: str = Form(...), conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        gid = int(group_id) if group_id else None
        conn.execute(
            "INSERT INTO teams (school_id, tournament_id, name, group_id) VALUES (?,?,?,?)",
            (school_id, tid, name, gid),
        )
        conn.commit()
        return RedirectResponse(f"/admin/torneo/{tid}", status_code=303)

    @app.post("/admin/equipo/{team_id}/jugadores")
    def create_player(team_id: int, request: Request, name: str = Form(...),
                      dorsal: str = Form(""), dni: str = Form(""),
                      csrf_token: str = Form(...), conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        team = queries.get_team(conn, team_id)
        if not team:
            return Response("Equipo no existe", status_code=404)
        d = int(dorsal) if dorsal.strip() else None
        conn.execute(
            "INSERT INTO players (team_id, name, dorsal, dni) VALUES (?,?,?,?)",
            (team_id, name, d, dni or None),
        )
        conn.commit()
        return RedirectResponse(f"/admin/torneo/{team['tournament_id']}", status_code=303)

    @app.post("/admin/grupo/{group_id}/fixture")
    def gen_fixture(group_id: int, request: Request, csrf_token: str = Form(...),
                    conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        grp = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        if not grp:
            return Response("Grupo no existe", status_code=404)
        tid = grp["tournament_id"]
        team_ids = [r["id"] for r in queries.teams_of_group(conn, group_id)]
        # borra fixture previo del grupo
        conn.execute("DELETE FROM matches WHERE group_id = ? AND stage = 'grupos'", (group_id,))
        for fm in generate_round_robin(team_ids):
            conn.execute(
                """INSERT INTO matches (tournament_id, group_id, stage, jornada,
                   home_team_id, away_team_id, played) VALUES (?,?, 'grupos', ?,?,?,0)""",
                (tid, group_id, fm.jornada, fm.home_team_id, fm.away_team_id),
            )
        conn.commit()
        return RedirectResponse(f"/admin/torneo/{tid}", status_code=303)

    @app.post("/admin/partido/{mid}/programar")
    def schedule_match(mid: int, request: Request, kickoff: str = Form(""),
                       cancha: str = Form(""), csrf_token: str = Form(...),
                       conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        m = queries.get_match(conn, mid)
        if not m:
            return Response("Partido no existe", status_code=404)
        conn.execute(
            "UPDATE matches SET kickoff = ?, cancha = ? WHERE id = ?",
            (kickoff or None, cancha or None, mid),
        )
        conn.commit()
        return RedirectResponse(f"/admin/torneo/{m['tournament_id']}", status_code=303)

    @app.get("/admin/partido/{mid}", response_class=HTMLResponse)
    def match_form(mid: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        m = queries.get_match(conn, mid)
        if not m:
            return render(request, "404.html", status_code=404)
        home_players = queries.players_of_team(conn, m["home_team_id"]) if m["home_team_id"] else []
        away_players = queries.players_of_team(conn, m["away_team_id"]) if m["away_team_id"] else []
        events = conn.execute(
            """SELECT e.*, p.name AS player_name FROM match_events e
               LEFT JOIN players p ON p.id = e.player_id WHERE e.match_id = ? ORDER BY e.id""",
            (mid,),
        ).fetchall()
        resp = render(request, "admin/match.html", m=m, home_players=home_players,
                      away_players=away_players, events=events)
        set_csrf(resp, request)
        return resp

    @app.post("/admin/partido/{mid}/resultado")
    def set_result(mid: int, request: Request, home_goals: int = Form(...),
                   away_goals: int = Form(...), csrf_token: str = Form(...),
                   conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        m = queries.get_match(conn, mid)
        if not m:
            return Response("Partido no existe", status_code=404)
        conn.execute(
            "UPDATE matches SET home_goals = ?, away_goals = ?, played = 1 WHERE id = ?",
            (home_goals, away_goals, mid),
        )
        conn.commit()
        return RedirectResponse(f"/admin/partido/{mid}", status_code=303)

    @app.post("/admin/partido/{mid}/evento")
    def add_event(mid: int, request: Request, player_id: int = Form(...),
                  kind: str = Form(...), minute: str = Form(""),
                  csrf_token: str = Form(...), conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        if kind not in ("gol", "amarilla", "roja"):
            return Response("Tipo de evento inválido", status_code=400)
        p = conn.execute("SELECT team_id FROM players WHERE id = ?", (player_id,)).fetchone()
        if not p:
            return Response("Jugador no existe", status_code=404)
        mn = int(minute) if minute.strip() else None
        conn.execute(
            "INSERT INTO match_events (match_id, player_id, team_id, kind, minute) VALUES (?,?,?,?,?)",
            (mid, player_id, p["team_id"], kind, mn),
        )
        conn.commit()
        return RedirectResponse(f"/admin/partido/{mid}", status_code=303)

    @app.post("/admin/torneo/{tid}/llave")
    def create_knockout(tid: int, request: Request, name: str = Form(...),
                        home_team_id: int = Form(...), away_team_id: int = Form(...),
                        stage: str = Form("semifinal"), csrf_token: str = Form(...),
                        conn: sqlite3.Connection = Depends(get_conn)):
        guard = require_admin(request)
        if guard:
            return guard
        if not check_csrf(request, csrf_token):
            return Response("CSRF inválido", status_code=400)
        if stage not in ("semifinal", "final"):
            return Response("Etapa inválida", status_code=400)
        conn.execute(
            """INSERT INTO matches (tournament_id, group_id, stage, jornada,
               home_team_id, away_team_id, played) VALUES (?, NULL, ?, NULL, ?, ?, 0)""",
            (tid, stage, home_team_id, away_team_id),
        )
        conn.commit()
        return RedirectResponse(f"/admin/torneo/{tid}", status_code=303)

    return app


app = create_app()
