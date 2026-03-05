import aiosqlite
import os
from app.config import settings


async def get_db():
    os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)
    db = await aiosqlite.connect(settings.DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS cached_matches (
            match_id TEXT PRIMARY KEY,
            competition TEXT,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
            status TEXT,
            data_json TEXT,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cached_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            bookmaker TEXT,
            home_win REAL,
            draw REAL,
            away_win REAL,
            over_25 REAL,
            under_25 REAL,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES cached_matches(match_id)
        );

        CREATE TABLE IF NOT EXISTS predictions_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            prediction_type TEXT,
            predicted_outcome TEXT,
            confidence REAL,
            actual_outcome TEXT,
            correct INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES cached_matches(match_id)
        );

        CREATE TABLE IF NOT EXISTS team_elo (
            team_name TEXT PRIMARY KEY,
            elo_rating REAL DEFAULT 1500.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()
    await db.close()
