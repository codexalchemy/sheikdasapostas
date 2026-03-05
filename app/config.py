import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
    FOOTBALL_DATA_API_KEY: str = os.getenv("FOOTBALL_DATA_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/sheik.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # The Odds API
    ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"
    ODDS_REGIONS: str = "us,uk,eu"
    ODDS_MARKETS: str = "h2h,spreads,totals"

    # Football-Data.org
    FOOTBALL_API_BASE_URL: str = "https://api.football-data.org/v4"

    # Ligas suportadas (códigos football-data.org)
    SUPPORTED_LEAGUES: dict = {
        "PL": "Premier League",
        "PD": "La Liga",
        "SA": "Serie A",
        "BL1": "Bundesliga",
        "FL1": "Ligue 1",
        "BSA": "Brasileirão Série A",
        "CL": "Champions League",
    }


settings = Settings()
