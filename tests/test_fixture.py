from app.logic import generate_round_robin


def _pairs(fixtures):
    return {frozenset((f.home_team_id, f.away_team_id)) for f in fixtures}


def test_even_teams_round_robin():
    team_ids = [1, 2, 3, 4]
    fx = generate_round_robin(team_ids)
    # n=4 -> 3 jornadas, 2 partidos por jornada = 6 partidos
    assert len(fx) == 6
    assert max(f.jornada for f in fx) == 3
    # Cada par aparece exactamente una vez (una rueda)
    pairs = _pairs(fx)
    assert len(pairs) == 6
    # Cada jornada tiene 2 partidos (sin repetir equipo)
    for j in range(1, 4):
        jornada = [f for f in fx if f.jornada == j]
        assert len(jornada) == 2
        teams_in_round = [f.home_team_id for f in jornada] + [f.away_team_id for f in jornada]
        assert sorted(teams_in_round) == [1, 2, 3, 4]


def test_odd_teams_have_bye():
    team_ids = [1, 2, 3]
    fx = generate_round_robin(team_ids)
    # n=3 -> 3 jornadas; cada jornada un equipo descansa, 1 partido real
    assert max(f.jornada for f in fx) == 3
    assert len(fx) == 3  # 3 partidos reales (3 pares únicos)
    # Nunca aparece un BYE (None) en un partido emitido
    for f in fx:
        assert f.home_team_id is not None
        assert f.away_team_id is not None
    pairs = _pairs(fx)
    assert pairs == {frozenset((1, 2)), frozenset((1, 3)), frozenset((2, 3))}


def test_single_team_no_matches():
    assert generate_round_robin([1]) == []
    assert generate_round_robin([]) == []


def test_all_pairs_covered_six_teams():
    team_ids = list(range(1, 7))
    fx = generate_round_robin(team_ids)
    # n=6 -> 5 jornadas x 3 = 15 partidos, 15 pares únicos
    assert len(fx) == 15
    assert len(_pairs(fx)) == 15
    assert max(f.jornada for f in fx) == 5
