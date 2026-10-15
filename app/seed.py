"""Datos demo: se cargan al primer arranque si la BD está vacía y SEED_DEMO=true."""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta

from .logic import generate_round_robin

# Colegios ficticios de Lima
SCHOOLS = [
    ("Colegio San Martín de Porres", "San Juan de Lurigancho"),
    ("I.E. Las Palmeras", "Surco"),
    ("Colegio Virgen del Carmen", "Comas"),
    ("I.E. Simón Bolívar", "La Victoria"),
    ("Colegio Santa Rosa", "San Isidro"),
    ("I.E. José de San Martín", "Breña"),
    ("Colegio Micaela Bastidas", "Villa El Salvador"),
    ("I.E. Horacio Zevallos", "Ate"),
]

FIRST_NAMES = [
    "Mateo", "Santiago", "Thiago", "Benjamín", "Luciano", "Gael", "Dylan",
    "Adriano", "Fabricio", "Rodrigo", "Diego", "Sebastián", "Joaquín", "Alonso",
    "Rafael", "Nicolás", "Emiliano", "Leonardo", "Valentino", "Bruno",
]
LAST_NAMES = [
    "Quispe", "Flores", "Rojas", "Vargas", "Mendoza", "Huamán", "Ramos",
    "Castro", "Cáceres", "Palacios", "Chávez", "Ríos", "Salazar", "Ponce",
]


def _rng() -> random.Random:
    return random.Random(2026)


_EVENT_SQL = (
    "INSERT INTO match_events (match_id, player_id, team_id, kind, minute) "
    "VALUES (?,?,?,?,?)"
)


def seed(conn: sqlite3.Connection) -> None:
    rng = _rng()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO tournaments (name, category, gender, season, active) VALUES (?,?,?,?,1)",
        ("Copa Escolar de Fulbito 2026", "Sub-14", "Masculino", "2026"),
    )
    tid = cur.lastrowid

    school_ids = []
    for name, dist in SCHOOLS:
        cur.execute("INSERT INTO schools (name, district) VALUES (?,?)", (name, dist))
        school_ids.append(cur.lastrowid)

    group_ids = []
    for gname in ("Grupo A", "Grupo B"):
        cur.execute(
            "INSERT INTO groups (tournament_id, name) VALUES (?,?)", (tid, gname)
        )
        group_ids.append(cur.lastrowid)

    # 2 grupos x 4 equipos
    team_ids_by_group: dict[int, list[int]] = {g: [] for g in group_ids}
    for idx, sid in enumerate(school_ids):
        gid = group_ids[idx // 4]
        team_name = SCHOOLS[idx][0].replace("Colegio ", "").replace("I.E. ", "")
        cur.execute(
            "INSERT INTO teams (school_id, tournament_id, name, group_id) VALUES (?,?,?,?)",
            (sid, tid, team_name, gid),
        )
        team_id = cur.lastrowid
        team_ids_by_group[gid].append(team_id)
        # 8 jugadores por equipo
        used_dorsals: set[int] = set()
        for _ in range(8):
            fn = rng.choice(FIRST_NAMES)
            ln = rng.choice(LAST_NAMES)
            d = rng.randint(1, 20)
            while d in used_dorsals:
                d = rng.randint(1, 20)
            used_dorsals.add(d)
            cur.execute(
                "INSERT INTO players (team_id, name, dorsal, dni) VALUES (?,?,?,?)",
                (team_id, f"{fn} {ln}", d, None),
            )

    base_date = datetime(2026, 4, 4, 9, 0)
    canchas = ["Cancha 1", "Cancha 2"]

    for gi, gid in enumerate(group_ids):
        tids = team_ids_by_group[gid]
        fixture = generate_round_robin(tids)
        for fm in fixture:
            kickoff = base_date + timedelta(
                days=(fm.jornada - 1) * 7, hours=gi * 2 + (fm.home_team_id % 2)
            )
            cur.execute(
                """INSERT INTO matches
                   (tournament_id, group_id, stage, jornada, home_team_id,
                    away_team_id, kickoff, cancha, played)
                   VALUES (?,?,?,?,?,?,?,?,0)""",
                (
                    tid, gid, "grupos", fm.jornada, fm.home_team_id,
                    fm.away_team_id, kickoff.isoformat(timespec="minutes"),
                    canchas[gi % len(canchas)],
                ),
            )

    conn.commit()

    # Jugar las primeras 2 jornadas con resultados y eventos
    played_matches = cur.execute(
        "SELECT * FROM matches WHERE tournament_id = ? AND jornada <= 2 ORDER BY id",
        (tid,),
    ).fetchall()

    for m in played_matches:
        hg = rng.randint(0, 5)
        ag = rng.randint(0, 5)
        cur.execute(
            "UPDATE matches SET home_goals=?, away_goals=?, played=1 WHERE id=?",
            (hg, ag, m["id"]),
        )
        for team_id, goals in ((m["home_team_id"], hg), (m["away_team_id"], ag)):
            squad = cur.execute(
                "SELECT id FROM players WHERE team_id = ?", (team_id,)
            ).fetchall()
            for _ in range(goals):
                scorer = rng.choice(squad)["id"]
                cur.execute(
                    _EVENT_SQL,
                    (m["id"], scorer, team_id, "gol", rng.randint(1, 40)),
                )
            # algunas tarjetas
            for _ in range(rng.randint(0, 2)):
                p = rng.choice(squad)["id"]
                kind = "amarilla" if rng.random() < 0.85 else "roja"
                cur.execute(
                    _EVENT_SQL,
                    (m["id"], p, team_id, kind, rng.randint(1, 40)),
                )

    conn.commit()
