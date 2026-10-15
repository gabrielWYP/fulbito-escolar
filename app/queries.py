"""Consultas de lectura/escritura (todas parametrizadas)."""
from __future__ import annotations

import sqlite3

from .logic import MatchResult, Standing, compute_standings


def active_tournaments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tournaments WHERE active = 1 ORDER BY season DESC, name"
    ).fetchall()


def all_tournaments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tournaments ORDER BY active DESC, season DESC, name"
    ).fetchall()


def get_tournament(conn: sqlite3.Connection, tid: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tournaments WHERE id = ?", (tid,)).fetchone()


def groups_of(conn: sqlite3.Connection, tid: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM groups WHERE tournament_id = ? ORDER BY name", (tid,)
    ).fetchall()


def teams_of_tournament(conn: sqlite3.Connection, tid: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.*, s.name AS school_name
           FROM teams t JOIN schools s ON s.id = t.school_id
           WHERE t.tournament_id = ? ORDER BY t.name""",
        (tid,),
    ).fetchall()


def teams_of_group(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.*, s.name AS school_name
           FROM teams t JOIN schools s ON s.id = t.school_id
           WHERE t.group_id = ? ORDER BY t.name""",
        (group_id,),
    ).fetchall()


def get_team(conn: sqlite3.Connection, team_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT t.*, s.name AS school_name, s.id AS school_id
           FROM teams t JOIN schools s ON s.id = t.school_id
           WHERE t.id = ?""",
        (team_id,),
    ).fetchone()


def players_of_team(conn: sqlite3.Connection, team_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM players WHERE team_id = ? ORDER BY dorsal IS NULL, dorsal, name",
        (team_id,),
    ).fetchall()


def all_schools(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM schools ORDER BY name").fetchall()


def get_school(conn: sqlite3.Connection, sid: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM schools WHERE id = ?", (sid,)).fetchone()


def teams_of_school(conn: sqlite3.Connection, sid: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.*, tt.name AS tournament_name, tt.category
           FROM teams t JOIN tournaments tt ON tt.id = t.tournament_id
           WHERE t.school_id = ? ORDER BY tt.season DESC, t.name""",
        (sid,),
    ).fetchall()


def matches_of_tournament(
    conn: sqlite3.Connection, tid: int, played: bool | None = None
) -> list[sqlite3.Row]:
    q = """SELECT m.*,
                  ht.name AS home_name, at.name AS away_name,
                  g.name AS group_name
           FROM matches m
           LEFT JOIN teams ht ON ht.id = m.home_team_id
           LEFT JOIN teams at ON at.id = m.away_team_id
           LEFT JOIN groups g ON g.id = m.group_id
           WHERE m.tournament_id = ?"""
    params: list = [tid]
    if played is not None:
        q += " AND m.played = ?"
        params.append(1 if played else 0)
    q += " ORDER BY m.jornada, m.kickoff IS NULL, m.kickoff, m.id"
    return conn.execute(q, params).fetchall()


def get_match(conn: sqlite3.Connection, mid: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT m.*, ht.name AS home_name, at.name AS away_name
           FROM matches m
           LEFT JOIN teams ht ON ht.id = m.home_team_id
           LEFT JOIN teams at ON at.id = m.away_team_id
           WHERE m.id = ?""",
        (mid,),
    ).fetchone()


def standings_for_group(conn: sqlite3.Connection, group_id: int) -> list[Standing]:
    teams = [(r["id"], r["name"]) for r in teams_of_group(conn, group_id)]
    rows = conn.execute(
        """SELECT home_team_id, away_team_id, home_goals, away_goals
           FROM matches
           WHERE group_id = ? AND played = 1
             AND home_goals IS NOT NULL AND away_goals IS NOT NULL""",
        (group_id,),
    ).fetchall()
    results = [
        MatchResult(r["home_team_id"], r["away_team_id"], r["home_goals"], r["away_goals"])
        for r in rows
    ]
    return compute_standings(teams, results)


def top_scorers(conn: sqlite3.Connection, tid: int, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT p.name AS player_name, t.name AS team_name,
                  t.id AS team_id, COUNT(*) AS goles
           FROM match_events e
           JOIN players p ON p.id = e.player_id
           JOIN teams t ON t.id = e.team_id
           JOIN matches m ON m.id = e.match_id
           WHERE m.tournament_id = ? AND e.kind = 'gol'
           GROUP BY p.id
           ORDER BY goles DESC, p.name
           LIMIT ?""",
        (tid, limit),
    ).fetchall()


def fairplay(conn: sqlite3.Connection, tid: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.id AS team_id, t.name AS team_name,
                  SUM(CASE WHEN e.kind = 'amarilla' THEN 1 ELSE 0 END) AS amarillas,
                  SUM(CASE WHEN e.kind = 'roja' THEN 1 ELSE 0 END) AS rojas
           FROM teams t
           LEFT JOIN match_events e ON e.team_id = t.id
           LEFT JOIN matches m ON m.id = e.match_id AND m.tournament_id = t.tournament_id
           WHERE t.tournament_id = ?
           GROUP BY t.id
           ORDER BY (COALESCE(SUM(CASE WHEN e.kind='amarilla' THEN 1 ELSE 0 END),0)
                     + COALESCE(SUM(CASE WHEN e.kind='roja' THEN 1 ELSE 0 END),0) * 2) DESC,
                    t.name""",
        (tid,),
    ).fetchall()
