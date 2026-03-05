import httpx
import logging
import time
from app.config import settings
from app.models.schemas import TeamStats

logger = logging.getLogger(__name__)

CACHE_TTL = 1800  # 30 minutos — free tier 10 req/min, economizar ao máximo


class FootballService:
    """Integração com Football-Data.org para dados de competições e times."""

    PLACEHOLDER_KEYS = {"cole_sua_chave_football_data_aqui", ""}

    def __init__(self):
        self.base_url = settings.FOOTBALL_API_BASE_URL
        raw_key = settings.FOOTBALL_DATA_API_KEY
        self.api_key = raw_key if raw_key not in self.PLACEHOLDER_KEYS else ""
        self.headers = {"X-Auth-Token": self.api_key} if self.api_key else {}
        self._cache: dict[str, tuple[float, object]] = {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=15)
        return self._client

    def _get_cached(self, key: str):
        entry = self._cache.get(key)
        if entry and (time.time() - entry[0]) < CACHE_TTL:
            logger.info(f"Football cache HIT para '{key}'")
            return entry[1]
        return None

    def _set_cache(self, key: str, data) -> None:
        self._cache[key] = (time.time(), data)

    async def get_competitions(self) -> list[dict]:
        """Lista competições disponíveis."""
        client = await self._get_client()
        resp = await client.get(f"{self.base_url}/competitions")
        resp.raise_for_status()
        return resp.json().get("competitions", [])

    async def get_standings(self, competition_code: str) -> list[dict]:
        """Obtém classificação de uma competição."""
        if not self.api_key:
            logger.warning("FOOTBALL_DATA_API_KEY não configurada — retornando exemplo")
            return self._sample_standings(competition_code)

        cache_key = f"standings:{competition_code}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/competitions/{competition_code}/standings"
            )
            resp.raise_for_status()
            data = resp.json()
            standings = data.get("standings", [])
            total = next((s for s in standings if s.get("type") == "TOTAL"), None)
            table = total.get("table", []) if total else []
            self._set_cache(cache_key, table)
            return table
        except Exception as e:
            logger.warning(f"Erro ao buscar standings ({competition_code}): {e} — usando dados de exemplo")
            return self._sample_standings(competition_code)

    async def get_matches(
        self, competition_code: str, status: str = "SCHEDULED,TIMED"
    ) -> list[dict]:
        """Obtém partidas de uma competição."""
        if not self.api_key:
            return self._sample_matches()

        cache_key = f"matches:{competition_code}:{status}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/competitions/{competition_code}/matches",
                params={"status": status},
            )
            resp.raise_for_status()
            matches = resp.json().get("matches", [])
            result = matches if matches else self._sample_matches()
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"Erro ao buscar matches ({competition_code}): {e} — usando dados de exemplo")
            return self._sample_matches()

    async def get_head2head(self, match_id: int) -> dict:
        """Obtém histórico de confrontos diretos."""
        if not self.api_key:
            return {"numberOfMatches": 0, "totalGoals": 0}

        cache_key = f"h2h:{match_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/matches/{match_id}")
            resp.raise_for_status()
            h2h = resp.json().get("head2head", {})
            self._set_cache(cache_key, h2h)
            return h2h
        except Exception as e:
            logger.warning(f"Erro ao buscar head2head ({match_id}): {e}")
            return {"numberOfMatches": 0, "totalGoals": 0}

    async def get_recent_results(self, competition_code: str) -> list[dict]:
        """Busca partidas concluídas para form guide e livescore."""
        if not self.api_key:
            return []

        cache_key = f"finished:{competition_code}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/competitions/{competition_code}/matches",
                params={"status": "FINISHED", "limit": 60},
            )
            resp.raise_for_status()
            matches = resp.json().get("matches", [])
            self._set_cache(cache_key, matches)
            return matches
        except Exception as e:
            logger.warning(f"Erro ao buscar resultados recentes ({competition_code}): {e}")
            return []

    async def get_live_matches(self) -> list[dict]:
        """Busca partidas ao vivo de todas as competições."""
        if not self.api_key:
            return []

        cache_key = "live_matches"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/matches",
                params={"status": "IN_PLAY"},
            )
            resp.raise_for_status()
            matches = resp.json().get("matches", [])
            # Cache curto para live (60s)
            self._cache[cache_key] = (time.time() - CACHE_TTL + 60, matches)
            return matches
        except Exception as e:
            logger.warning(f"Erro ao buscar jogos ao vivo: {e}")
            return []

    def get_team_form(self, team_name: str, finished_matches: list[dict], n: int = 5) -> list[str]:
        """Extrai últimos N resultados de um time. Retorna ['W','D','L',...]."""
        results = []
        for m in reversed(finished_matches):
            h = m.get("homeTeam", {}).get("name", "")
            a = m.get("awayTeam", {}).get("name", "")
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            hg = ft.get("home")
            ag = ft.get("away")
            if hg is None or ag is None:
                continue
            is_home = team_name.lower() in h.lower() or h.lower() in team_name.lower()
            is_away = team_name.lower() in a.lower() or a.lower() in team_name.lower()
            if is_home:
                results.append("W" if hg > ag else "D" if hg == ag else "L")
            elif is_away:
                results.append("W" if ag > hg else "D" if ag == hg else "L")
            if len(results) >= n:
                break
        return results

    def parse_team_stats(self, table_entry: dict) -> TeamStats:
        """Converte entrada da tabela em TeamStats."""
        team = table_entry.get("team", {})
        played = table_entry.get("playedGames", 0)
        gf = table_entry.get("goalsFor", 0)
        ga = table_entry.get("goalsAgainst", 0)

        return TeamStats(
            name=team.get("name", "Desconhecido"),
            played=played,
            won=table_entry.get("won", 0),
            draw=table_entry.get("draw", 0),
            lost=table_entry.get("lost", 0),
            goals_for=gf,
            goals_against=ga,
            points=table_entry.get("points", 0),
            position=table_entry.get("position", 0),
            avg_goals_scored=round(gf / played, 2) if played > 0 else 0,
            avg_goals_conceded=round(ga / played, 2) if played > 0 else 0,
        )

    async def get_team_stats(
        self, team_name: str, competition_code: str
    ) -> TeamStats | None:
        """Busca stats de um time na classificação."""
        standings = await self.get_standings(competition_code)
        for entry in standings:
            name = entry.get("team", {}).get("name", "")
            if team_name.lower() in name.lower() or name.lower() in team_name.lower():
                return self.parse_team_stats(entry)
        return None

    def _sample_standings(self, competition: str) -> list[dict]:
        """Dados de exemplo para desenvolvimento sem API key."""
        teams = [
            ("Flamengo", 30, 18, 6, 6, 52, 30, 60),
            ("Palmeiras", 30, 17, 8, 5, 48, 25, 59),
            ("São Paulo", 30, 15, 7, 8, 40, 32, 52),
            ("Corinthians", 30, 14, 6, 10, 38, 35, 48),
            ("Botafogo", 30, 13, 8, 9, 42, 33, 47),
            ("Atlético-MG", 30, 12, 9, 9, 39, 31, 45),
            ("Internacional", 30, 12, 8, 10, 36, 30, 44),
            ("Grêmio", 30, 11, 9, 10, 35, 34, 42),
        ]
        table = []
        for i, (name, pg, w, d, l, gf, ga, pts) in enumerate(teams, 1):
            table.append(
                {
                    "position": i,
                    "team": {"id": i, "name": name},
                    "playedGames": pg,
                    "won": w,
                    "draw": d,
                    "lost": l,
                    "goalsFor": gf,
                    "goalsAgainst": ga,
                    "goalDifference": gf - ga,
                    "points": pts,
                }
            )
        return table

    def _sample_matches(self) -> list[dict]:
        return [
            {
                "id": 1001,
                "utcDate": "2026-03-08T20:00:00Z",
                "status": "SCHEDULED",
                "homeTeam": {"name": "Flamengo"},
                "awayTeam": {"name": "Palmeiras"},
                "competition": {"name": "Brasileirão Série A", "code": "BSA"},
            },
            {
                "id": 1002,
                "utcDate": "2026-03-08T18:30:00Z",
                "status": "SCHEDULED",
                "homeTeam": {"name": "Corinthians"},
                "awayTeam": {"name": "São Paulo"},
                "competition": {"name": "Brasileirão Série A", "code": "BSA"},
            },
        ]


football_service = FootballService()
