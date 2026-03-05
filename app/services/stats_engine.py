import math
import logging
from scipy.stats import poisson
from app.models.schemas import TeamStats, PoissonPrediction

logger = logging.getLogger(__name__)

# Média de gols por jogo em ligas top (referência global ~2.6-2.8)
LEAGUE_AVG_GOALS = 2.7


class StatsEngine:
    """Motor de modelos estatísticos para previsão de resultados."""

    def poisson_prediction(
        self,
        home_stats: TeamStats,
        away_stats: TeamStats,
        league_avg: float = LEAGUE_AVG_GOALS,
    ) -> PoissonPrediction:
        """
        Calcula probabilidades usando distribuição de Poisson.

        O modelo estima os gols esperados de cada time baseado em:
        - Força ofensiva do time (gols marcados vs média da liga)
        - Força defensiva do oponente (gols sofridos vs média da liga)
        - Fator casa (~0.2 gols de vantagem)
        """
        home_avg = league_avg / 2  # média de gols por time por jogo

        # Força ofensiva e defensiva relativa
        home_attack = home_stats.avg_goals_scored / home_avg if home_avg > 0 else 1
        home_defense = home_stats.avg_goals_conceded / home_avg if home_avg > 0 else 1
        away_attack = away_stats.avg_goals_scored / home_avg if home_avg > 0 else 1
        away_defense = away_stats.avg_goals_conceded / home_avg if home_avg > 0 else 1

        # Gols esperados (lambda) com fator casa
        home_factor = 1.15  # vantagem de jogar em casa
        home_expected = home_attack * away_defense * home_avg * home_factor
        away_expected = away_attack * home_defense * home_avg / home_factor

        # Limitar valores extremos
        home_expected = max(0.3, min(4.0, home_expected))
        away_expected = max(0.3, min(4.0, away_expected))

        # Calcular probabilidades com Poisson
        max_goals = 7
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0
        over_25_prob = 0.0
        btts_prob = 0.0
        score_probs: dict[str, float] = {}

        for i in range(max_goals):
            for j in range(max_goals):
                prob = (
                    poisson.pmf(i, home_expected) * poisson.pmf(j, away_expected)
                )
                score_key = f"{i}-{j}"
                score_probs[score_key] = round(prob * 100, 2)

                if i > j:
                    home_win_prob += prob
                elif i == j:
                    draw_prob += prob
                else:
                    away_win_prob += prob

                if i + j > 2:
                    over_25_prob += prob

                if i > 0 and j > 0:
                    btts_prob += prob

        # Top 5 placares mais prováveis
        sorted_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)
        top_scores = dict(sorted_scores[:10])

        return PoissonPrediction(
            home_goals_expected=round(home_expected, 2),
            away_goals_expected=round(away_expected, 2),
            home_win_prob=round(home_win_prob, 4),
            draw_prob=round(draw_prob, 4),
            away_win_prob=round(away_win_prob, 4),
            over_25_prob=round(over_25_prob, 4),
            under_25_prob=round(1 - over_25_prob, 4),
            btts_prob=round(btts_prob, 4),
            score_probabilities=top_scores,
        )

    def calculate_elo(
        self,
        home_elo: float,
        away_elo: float,
        home_goals: int,
        away_goals: int,
        k_factor: float = 32,
    ) -> tuple[float, float]:
        """
        Atualiza ratings ELO após uma partida.

        Retorna (new_home_elo, new_away_elo).
        """
        # Expectativa de resultado
        home_expected = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))
        away_expected = 1 - home_expected

        # Resultado real
        if home_goals > away_goals:
            home_result = 1.0
            away_result = 0.0
        elif home_goals == away_goals:
            home_result = 0.5
            away_result = 0.5
        else:
            home_result = 0.0
            away_result = 1.0

        # Fator de margem de gols
        goal_diff = abs(home_goals - away_goals)
        if goal_diff <= 1:
            margin_factor = 1
        elif goal_diff == 2:
            margin_factor = 1.5
        else:
            margin_factor = (11 + goal_diff) / 8

        new_home = home_elo + k_factor * margin_factor * (home_result - home_expected)
        new_away = away_elo + k_factor * margin_factor * (away_result - away_expected)

        return round(new_home, 1), round(new_away, 1)

    def elo_win_probability(
        self, home_elo: float, away_elo: float, home_advantage: float = 65
    ) -> dict[str, float]:
        """Calcula probabilidades de resultado baseado em ELO."""
        adjusted_home = home_elo + home_advantage
        home_exp = 1 / (1 + 10 ** ((away_elo - adjusted_home) / 400))

        # Distribuição típica: ~26% empates em futebol
        draw_factor = 0.26
        home_win = home_exp * (1 - draw_factor)
        away_win = (1 - home_exp) * (1 - draw_factor)

        return {
            "home_win": round(home_win, 4),
            "draw": round(draw_factor, 4),
            "away_win": round(away_win, 4),
        }


stats_engine = StatsEngine()
