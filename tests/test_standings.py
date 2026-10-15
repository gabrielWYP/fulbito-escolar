from app.logic import MatchResult, compute_standings


def test_points_and_record():
    teams = [(1, "A"), (2, "B"), (3, "C")]
    matches = [
        MatchResult(1, 2, 3, 1),  # A gana
        MatchResult(2, 3, 2, 2),  # empate
        MatchResult(1, 3, 0, 0),  # empate
    ]
    table = compute_standings(teams, matches)
    by_id = {s.team_id: s for s in table}

    a = by_id[1]
    assert (a.pj, a.pg, a.pe, a.pp) == (2, 1, 1, 0)
    assert a.pts == 4
    assert a.gf == 3 and a.gc == 1 and a.dg == 2

    b = by_id[2]
    assert b.pts == 1  # una derrota, un empate
    assert (b.pg, b.pe, b.pp) == (0, 1, 1)


def test_order_by_points():
    teams = [(1, "A"), (2, "B")]
    matches = [MatchResult(1, 2, 5, 0)]
    table = compute_standings(teams, matches)
    assert table[0].team_id == 1
    assert table[0].pts == 3
    assert table[1].pts == 0


def test_tiebreak_dg_then_gf():
    # Dos equipos empatan en puntos: desempata DG, luego GF.
    teams = [(1, "Alfa"), (2, "Beta"), (3, "Gamma"), (4, "Delta")]
    # Alfa y Beta ganan su partido pero con distinto marcador vs Gamma/Delta
    matches = [
        MatchResult(1, 3, 4, 0),  # Alfa +4
        MatchResult(2, 4, 2, 0),  # Beta +2
    ]
    table = compute_standings(teams, matches)
    # Alfa y Beta: 3 pts cada uno. Alfa tiene mejor DG -> primero.
    assert table[0].team_id == 1
    assert table[1].team_id == 2


def test_tiebreak_gf_when_dg_equal():
    # Ambos ganan 1 partido (3 pts) con el mismo DG (+3 y +1 difieren),
    # así que forzamos mismo DG con distinto GF.
    table = compute_standings(
        [(1, "Uno"), (2, "Dos"), (3, "Tres"), (4, "Cuatro")],
        [
            MatchResult(1, 3, 3, 2),  # Uno +1, GF3
            MatchResult(2, 4, 1, 0),  # Dos +1, GF1
        ],
    )
    ids = [s.team_id for s in table]
    # Uno y Dos: 3 pts y DG +1; desempata GF -> Uno (3) antes que Dos (1)
    assert ids[0] == 1
    assert ids[1] == 2


def test_tiebreak_name_alphabetical_last_resort():
    # Dos equipos idénticos en todo: desempata por nombre.
    teams = [(1, "Zeta"), (2, "Alfa")]
    table = compute_standings(teams, [])  # ningún partido jugado
    assert table[0].team_id == 2  # Alfa antes que Zeta
    assert table[0].pts == 0 and table[1].pts == 0
