from __future__ import annotations

import sqlite3
from pathlib import Path
import csv


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "sqlite_lab.db"
CSV_PATH = BASE_DIR.parent / "TFT_Challenger_MatchData.csv"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tft_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gameId TEXT NOT NULL,
    gameDuration REAL NOT NULL,
    level INTEGER NOT NULL,
    lastRound INTEGER NOT NULL,
    Ranked INTEGER NOT NULL,
    ingameDuration REAL NOT NULL,
    combination TEXT NOT NULL,
    champion TEXT NOT NULL
);
"""


def create_database(
    db_path: str | Path = DB_PATH,
    reset: bool = False,
    seed_limit: int | None = 5000,
    csv_path: str | Path = CSV_PATH,
) -> str:
    """Create the SQLite database and seed it from the TFT CSV dataset.

    `seed_limit` controls how many CSV rows are imported (None imports all rows).
    """
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if reset and path.exists():
        path.unlink()

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")

        if reset:
            connection.executescript(
                """
                DROP TABLE IF EXISTS tft_matches;
                """
            )

        connection.executescript(SCHEMA_SQL)

        seed_count = connection.execute("SELECT COUNT(*) FROM tft_matches").fetchone()[0]
        if seed_count == 0:
            _seed_from_csv(
                connection,
                csv_path=csv_path,
                limit=seed_limit,
            )

        connection.commit()

    return str(path)

def _seed_from_csv(
    connection: sqlite3.Connection,
    csv_path: str | Path,
    limit: int | None,
    batch_size: int = 1000,
) -> None:
    source_path = Path(csv_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"CSV not found: {source_path}")

    rows: list[tuple[object, ...]] = []
    inserted = 0

    # Some CSV files include a UTF-8 BOM; `utf-8-sig` strips it automatically.
    with source_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            if limit is not None and inserted >= limit:
                break

            rows.append(
                (
                    record["gameId"],
                    float(record["gameDuration"]),
                    int(record["level"]),
                    int(record["lastRound"]),
                    int(record["Ranked"]),
                    float(record["ingameDuration"]),
                    record["combination"],
                    record["champion"],
                )
            )
            inserted += 1

            if len(rows) >= batch_size:
                connection.executemany(
                    """
                    INSERT INTO tft_matches (
                        gameId, gameDuration, level, lastRound, Ranked,
                        ingameDuration, combination, champion
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                rows.clear()

    if rows:
        connection.executemany(
            """
            INSERT INTO tft_matches (
                gameId, gameDuration, level, lastRound, Ranked,
                ingameDuration, combination, champion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


if __name__ == "__main__":
    print(create_database())
