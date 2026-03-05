import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
    FOOTBALL_DATA_API_KEY: str = os.getenv("FOOTBALL_DATA_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/sheik.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "sheik_admin_2026")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # The Odds API
    ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"
    ODDS_REGIONS: str = "eu"
    ODDS_MARKETS: str = "h2h,totals"

    # Football-Data.org
    FOOTBALL_API_BASE_URL: str = "https://api.football-data.org/v4"

    # Ligas suportadas (códigos football-data.org)
    SUPPORTED_LEAGUES: dict = {
        "BSA": "Brasileirão Série A",
        "BSB": "Brasileirão Série B",
        "PL": "Premier League",
        "ELC": "Championship",
        "PD": "La Liga",
        "SA": "Serie A",
        "BL1": "Bundesliga",
        "FL1": "Ligue 1",
        "DED": "Eredivisie",
        "PPL": "Liga Portugal",
        "CL": "Champions League",
        "EL": "Europa League",
        "CLI": "Copa Libertadores",
        "MLS": "MLS",
        "ARG": "Liga Argentina",
        "MEX": "Liga MX",
    }

    # Mapeamento código liga → The Odds API sport key
    ODDS_SPORT_KEYS: dict = {
        "BSA": "soccer_brazil_campeonato",
        "BSB": "soccer_brazil_serie_b",
        "PL": "soccer_epl",
        "ELC": "soccer_efl_champ",
        "PD": "soccer_spain_la_liga",
        "SA": "soccer_italy_serie_a",
        "BL1": "soccer_germany_bundesliga",
        "FL1": "soccer_france_ligue_one",
        "DED": "soccer_netherlands_eredivisie",
        "PPL": "soccer_portugal_primeira_liga",
        "CL": "soccer_uefa_champs_league",
        "EL": "soccer_uefa_europa_league",
        "CLI": "soccer_conmebol_copa_libertadores",
        "MLS": "soccer_usa_mls",
        "ARG": "soccer_argentina_primera_division",
        "MEX": "soccer_mexico_ligamx",
    }


settings = Settings()
