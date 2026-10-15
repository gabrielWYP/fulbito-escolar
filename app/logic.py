"""Lógica de dominio pura: tabla de posiciones y generación de fixture.

Separada de la BD a propósito para poder testearla sin estado.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Standing:
    team_id: int
    name: str
    pj: int = 0   # partidos jugados
    pg: int = 0   # ganados
    pe: int = 0   # empatados
    pp: int = 0   # perdidos
    gf: int = 0   # goles a favor
    gc: int = 0   # goles en contra

    @property
    def dg(self) -> int:  # diferencia de goles
        return self.gf - self.gc

    @property
    def pts(self) -> int:
        return self.pg * 3 + self.pe * 1

    def as_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "pj": self.pj,
            "pg": self.pg,
            "pe": self.pe,
            "pp": self.pp,
            "gf": self.gf,
            "gc": self.gc,
            "dg": self.dg,
            "pts": self.pts,
        }


@dataclass
class MatchResult:
    home_team_id: int
    away_team_id: int
    home_goals: int
    away_goals: int


def compute_standings(
    teams: list[tuple[int, str]], matches: list[MatchResult]
) -> list[Standing]:
    """Calcula la tabla. 3 pts victoria, 1 empate, 0 derrota.

    Desempate: Pts > DG > GF > nombre (alfabético, estable).
    `teams` es una lista de (team_id, name). `matches` solo partidos jugados.
    """
    table: dict[int, Standing] = {
        tid: Standing(team_id=tid, name=name) for tid, name in teams
    }
    for m in matches:
        home = table.get(m.home_team_id)
        away = table.get(m.away_team_id)
        if home is None or away is None:
            continue
        home.pj += 1
        away.pj += 1
        home.gf += m.home_goals
        home.gc += m.away_goals
        away.gf += m.away_goals
        away.gc += m.home_goals
        if m.home_goals > m.away_goals:
            home.pg += 1
            away.pp += 1
        elif m.home_goals < m.away_goals:
            away.pg += 1
            home.pp += 1
        else:
            home.pe += 1
            away.pe += 1

    return sorted(
        table.values(),
        key=lambda s: (-s.pts, -s.dg, -s.gf, s.name.lower()),
    )


@dataclass
class FixtureMatch:
    jornada: int
    home_team_id: int | None  # None = BYE (descansa)
    away_team_id: int | None


def generate_round_robin(team_ids: list[int]) -> list[FixtureMatch]:
    """Fixture todos-contra-todos a una rueda (método del círculo).

    Maneja número impar de equipos insertando un BYE (None). Un partido
    contra el BYE significa que ese equipo descansa en esa jornada
    (no se emite como partido real).
    """
    teams: list[int | None] = list(team_ids)
    if len(teams) < 2:
        return []
    if len(teams) % 2 == 1:
        teams.append(None)  # BYE

    n = len(teams)
    rounds = n - 1
    half = n // 2
    fixtures: list[FixtureMatch] = []
    arr = teams[:]

    for r in range(rounds):
        for i in range(half):
            a = arr[i]
            b = arr[n - 1 - i]
            if a is None or b is None:
                continue  # descansa, no es partido real
            # Alternar localía por jornada para repartir local/visita
            if r % 2 == 0:
                home, away = a, b
            else:
                home, away = b, a
            fixtures.append(FixtureMatch(jornada=r + 1, home_team_id=home, away_team_id=away))
        # Rotación del método del círculo: fija el primero, rota el resto
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]

    return fixtures
