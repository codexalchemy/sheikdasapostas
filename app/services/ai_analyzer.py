import logging
from openai import AsyncOpenAI
from app.config import settings
from app.models.schemas import MatchData, PoissonPrediction

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Usa IA generativa para produzir análises detalhadas de partidas."""

    PLACEHOLDER_KEYS = {"cole_sua_chave_openai_aqui", ""}

    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        self.client = (
            AsyncOpenAI(api_key=api_key)
            if api_key and api_key not in self.PLACEHOLDER_KEYS
            else None
        )

    async def analyze_match(
        self,
        match: MatchData,
        poisson: PoissonPrediction | None = None,
        value_bets: list[dict] | None = None,
    ) -> dict:
        """
        Envia dados completos da partida para a IA e obtém análise.
        Retorna dict com: analysis, confidence, recommended_bet, recommended_market.
        """
        prompt = self._build_prompt(match, poisson, value_bets)

        if not self.client:
            logger.warning("OpenAI não configurada — gerando análise local")
            return self._local_analysis(match, poisson, value_bets)

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é o Sheik das Apostas, um analista esportivo especialista. "
                            "Analise os dados fornecidos e dê uma previsão detalhada mas concisa. "
                            "Sempre justifique com dados. Responda em português do Brasil. "
                            "Formato da resposta:\n"
                            "ANÁLISE: (2-3 parágrafos de análise)\n"
                            "CONFIANÇA: (número de 0 a 100)\n"
                            "APOSTA RECOMENDADA: (ex: Vitória do Flamengo)\n"
                            "MERCADO: (ex: 1x2, Over 2.5, BTTS Sim)"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )
            text = response.choices[0].message.content or ""
            return self._parse_ai_response(text)
        except Exception as e:
            logger.error(f"Erro na análise com IA: {e}")
            return self._local_analysis(match, poisson, value_bets)

    def _build_prompt(
        self,
        match: MatchData,
        poisson: PoissonPrediction | None,
        value_bets: list[dict] | None,
    ) -> str:
        parts = [
            f"## Partida: {match.home_team} vs {match.away_team}",
            f"Competição: {match.competition}",
            f"Data: {match.date}",
        ]

        if match.home_stats:
            h = match.home_stats
            parts.append(
                f"\n### {h.name} (Mandante)\n"
                f"Posição: {h.position}° | {h.points} pts | "
                f"{h.won}V {h.draw}E {h.lost}D | "
                f"Gols: {h.goals_for} pró / {h.goals_against} contra | "
                f"Média: {h.avg_goals_scored} gols/jogo marcados, "
                f"{h.avg_goals_conceded} sofridos"
            )

        if match.away_stats:
            a = match.away_stats
            parts.append(
                f"\n### {a.name} (Visitante)\n"
                f"Posição: {a.position}° | {a.points} pts | "
                f"{a.won}V {a.draw}E {a.lost}D | "
                f"Gols: {a.goals_for} pró / {a.goals_against} contra | "
                f"Média: {a.avg_goals_scored} gols/jogo marcados, "
                f"{a.avg_goals_conceded} sofridos"
            )

        if poisson:
            parts.append(
                f"\n### Modelo Poisson\n"
                f"Gols esperados: {match.home_team} {poisson.home_goals_expected} x "
                f"{poisson.away_goals_expected} {match.away_team}\n"
                f"Probabilidades: Casa {poisson.home_win_prob*100:.1f}% | "
                f"Empate {poisson.draw_prob*100:.1f}% | "
                f"Fora {poisson.away_win_prob*100:.1f}%\n"
                f"Over 2.5: {poisson.over_25_prob*100:.1f}% | "
                f"BTTS: {poisson.btts_prob*100:.1f}%\n"
                f"Placares mais prováveis: {poisson.score_probabilities}"
            )

        if match.odds:
            odds_text = "\n### Odds das Casas\n"
            for o in match.odds[:5]:
                odds_text += (
                    f"{o.bookmaker}: Casa {o.home_win} | "
                    f"Empate {o.draw} | Fora {o.away_win}"
                )
                if o.over_25:
                    odds_text += f" | Over 2.5: {o.over_25} | Under 2.5: {o.under_25}"
                odds_text += "\n"
            parts.append(odds_text)

        if value_bets:
            vb_text = "\n### Value Bets Detectadas\n"
            for vb in value_bets[:5]:
                vb_text += (
                    f"{vb['bookmaker']} - {vb['market']}: "
                    f"odd {vb['odd']} (implícita {vb['implied_prob']}% vs "
                    f"real {vb['real_prob']}% = edge {vb['edge']}%)\n"
                )
            parts.append(vb_text)

        parts.append(
            "\nCom base em todos esses dados, faça sua análise e recomendação."
        )
        return "\n".join(parts)

    def _parse_ai_response(self, text: str) -> dict:
        result = {
            "analysis": text,
            "confidence": 50,
            "recommended_bet": "",
            "recommended_market": "",
        }

        lines = text.split("\n")
        analysis_lines = []
        for line in lines:
            upper = line.strip().upper()
            if upper.startswith("CONFIANÇA:") or upper.startswith("CONFIANCA:"):
                try:
                    num = "".join(c for c in line.split(":", 1)[1] if c.isdigit() or c == ".")
                    result["confidence"] = min(100, max(0, float(num)))
                except (ValueError, IndexError):
                    pass
            elif upper.startswith("APOSTA RECOMENDADA:"):
                result["recommended_bet"] = line.split(":", 1)[1].strip()
            elif upper.startswith("MERCADO:"):
                result["recommended_market"] = line.split(":", 1)[1].strip()
            elif upper.startswith("ANÁLISE:") or upper.startswith("ANALISE:"):
                analysis_lines.append(line.split(":", 1)[1].strip())
            else:
                analysis_lines.append(line)

        result["analysis"] = "\n".join(analysis_lines).strip()
        return result

    def _local_analysis(
        self,
        match: MatchData,
        poisson: PoissonPrediction | None,
        value_bets: list[dict] | None,
    ) -> dict:
        """Análise simplificada quando a IA não está disponível."""
        analysis_parts = []
        confidence = 50
        recommended_bet = "Sem recomendação"
        recommended_market = "1x2"

        if poisson:
            probs = {
                "Casa": poisson.home_win_prob,
                "Empate": poisson.draw_prob,
                "Fora": poisson.away_win_prob,
            }
            best = max(probs, key=probs.get)  # type: ignore[arg-type]
            best_prob = probs[best]

            analysis_parts.append(
                f"📊 **Modelo Poisson** projeta {match.home_team} "
                f"{poisson.home_goals_expected} x {poisson.away_goals_expected} "
                f"{match.away_team}."
            )
            analysis_parts.append(
                f"Probabilidades calculadas: Casa {poisson.home_win_prob*100:.1f}% | "
                f"Empate {poisson.draw_prob*100:.1f}% | "
                f"Fora {poisson.away_win_prob*100:.1f}%."
            )

            if best == "Casa":
                recommended_bet = f"Vitória do {match.home_team}"
            elif best == "Fora":
                recommended_bet = f"Vitória do {match.away_team}"
            else:
                recommended_bet = "Empate"

            confidence = round(best_prob * 100)

            if poisson.over_25_prob > 0.55:
                analysis_parts.append(
                    f"⚽ Over 2.5 com {poisson.over_25_prob*100:.1f}% de probabilidade — "
                    f"jogo tende a ter gols."
                )
            if poisson.btts_prob > 0.55:
                analysis_parts.append(
                    f"🎯 Ambas marcam (BTTS) com {poisson.btts_prob*100:.1f}% — "
                    f"os dois times devem balançar a rede."
                )

        if value_bets:
            best_vb = value_bets[0]
            analysis_parts.append(
                f"\n💰 **Value Bet** detectada: {best_vb['market']} na "
                f"{best_vb['bookmaker']} (odd {best_vb['odd']}, "
                f"edge de {best_vb['edge']}%)."
            )

        if match.home_stats and match.away_stats:
            h, a = match.home_stats, match.away_stats
            if h.position < a.position:
                analysis_parts.append(
                    f"\n📋 {h.name} está melhor posicionado ({h.position}° vs "
                    f"{a.position}°) com {h.points} vs {a.points} pontos."
                )
            else:
                analysis_parts.append(
                    f"\n📋 {a.name} está melhor posicionado ({a.position}° vs "
                    f"{h.position}°) com {a.points} vs {h.points} pontos."
                )

        return {
            "analysis": "\n".join(analysis_parts) if analysis_parts else "Dados insuficientes para análise detalhada.",
            "confidence": confidence,
            "recommended_bet": recommended_bet,
            "recommended_market": recommended_market,
        }


ai_analyzer = AIAnalyzer()
