import httpx
import logging
from app.config import settings
from app.models.schemas import MatchOdds

logger = logging.getLogger(__name__)


class OddsService:
    """Integração com The Odds API para obter odds em tempo real."""

    PLACEHOLDER_KEYS = {"cole_sua_chave_the_odds_api_aqui", ""}

    def __init__(self):
        self.base_url = settings.ODDS_API_BASE_URL
        raw_key = settings.ODDS_API_KEY
        self.api_key = raw_key if raw_key not in self.PLACEHOLDER_KEYS else ""

    async def get_sports(self) -> list[dict]:
        """Lista todos os esportes disponíveis."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/sports",
                params={"apiKey": self.api_key},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_odds(
        self, sport_key: str = "soccer", regions: str = "us,uk,eu"
    ) -> list[dict]:
        """Obtém odds de partidas para um esporte."""
        if not self.api_key:
            logger.warning("ODDS_API_KEY não configurada — retornando dados de exemplo")
            return self._sample_odds()

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/sports/{sport_key}/odds",
                    params={
                        "apiKey": self.api_key,
                        "regions": regions,
                        "markets": "h2h,totals",
                        "oddsFormat": "decimal",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                remaining = resp.headers.get("x-requests-remaining", "?")
                logger.info(f"Odds API — requisições restantes: {remaining}")
                return resp.json()
        except Exception as e:
            logger.warning(f"Erro ao buscar odds: {e} — usando dados de exemplo")
            return self._sample_odds()

    def parse_odds(self, raw_event: dict) -> list[MatchOdds]:
        """Converte dados brutos da API em MatchOdds."""
        odds_list = []
        for bk in raw_event.get("bookmakers", []):
            h2h = next(
                (m for m in bk.get("markets", []) if m["key"] == "h2h"), None
            )
            totals = next(
                (m for m in bk.get("markets", []) if m["key"] == "totals"), None
            )

            if not h2h:
                continue

            outcomes = {o["name"]: o["price"] for o in h2h["outcomes"]}
            home = raw_event.get("home_team", "")
            away = raw_event.get("away_team", "")

            over_25 = None
            under_25 = None
            if totals:
                for o in totals.get("outcomes", []):
                    if o.get("name") == "Over" and o.get("point") == 2.5:
                        over_25 = o["price"]
                    elif o.get("name") == "Under" and o.get("point") == 2.5:
                        under_25 = o["price"]

            odds_list.append(
                MatchOdds(
                    bookmaker=bk["title"],
                    home_win=outcomes.get(home, 0),
                    draw=outcomes.get("Draw", 0),
                    away_win=outcomes.get(away, 0),
                    over_25=over_25,
                    under_25=under_25,
                )
            )
        return odds_list

    def find_value_bets(
        self, odds_list: list[MatchOdds], real_probs: dict[str, float]
    ) -> list[dict]:
        """Identifica value bets comparando odds com probabilidade real calculada."""
        value_bets = []
        for odds in odds_list:
            markets = {
                "home_win": (odds.home_win, real_probs.get("home_win", 0)),
                "draw": (odds.draw, real_probs.get("draw", 0)),
                "away_win": (odds.away_win, real_probs.get("away_win", 0)),
            }
            for market, (odd, real_prob) in markets.items():
                if odd <= 0:
                    continue
                implied_prob = 1 / odd
                if real_prob > implied_prob:
                    edge = real_prob - implied_prob
                    value_bets.append(
                        {
                            "bookmaker": odds.bookmaker,
                            "market": market,
                            "odd": odd,
                            "implied_prob": round(implied_prob * 100, 1),
                            "real_prob": round(real_prob * 100, 1),
                            "edge": round(edge * 100, 1),
                        }
                    )
        value_bets.sort(key=lambda x: x["edge"], reverse=True)
        return value_bets

    def _sample_odds(self) -> list[dict]:
        """Dados de exemplo para desenvolvimento sem API key."""
        return [
            {
                "id": "sample1",
                "sport_key": "soccer_brazil_campeonato",
                "commence_time": "2026-03-08T20:00:00Z",
                "home_team": "Flamengo",
                "away_team": "Palmeiras",
                "bookmakers": [
                    {
                        "key": "bet365",
                        "title": "Bet365",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Flamengo", "price": 2.10},
                                    {"name": "Draw", "price": 3.30},
                                    {"name": "Palmeiras", "price": 3.50},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": 1.85, "point": 2.5},
                                    {"name": "Under", "price": 2.00, "point": 2.5},
                                ],
                            },
                        ],
                    },
                    {
                        "key": "betano",
                        "title": "Betano",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Flamengo", "price": 2.15},
                                    {"name": "Draw", "price": 3.25},
                                    {"name": "Palmeiras", "price": 3.40},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "id": "sample2",
                "sport_key": "soccer_brazil_campeonato",
                "commence_time": "2026-03-08T18:30:00Z",
                "home_team": "Corinthians",
                "away_team": "São Paulo",
                "bookmakers": [
                    {
                        "key": "bet365",
                        "title": "Bet365",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Corinthians", "price": 2.50},
                                    {"name": "Draw", "price": 3.10},
                                    {"name": "São Paulo", "price": 2.90},
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": 1.90, "point": 2.5},
                                    {"name": "Under", "price": 1.95, "point": 2.5},
                                ],
                            },
                        ],
                    },
                ],
            },
        ]


odds_service = OddsService()
