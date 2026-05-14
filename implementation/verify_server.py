from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from implementation.init_db import create_database
from implementation.mcp_server import aggregate, database_schema, insert, search, table_schema


def run_verification() -> dict[str, object]:
    create_database(reset=True, seed_limit=2000)

    valid_search = search(
        table="tft_matches",
        filters=[{"column": "Ranked", "op": "=", "value": 1}],
        order_by="gameDuration",
        descending=False,
    )
    valid_insert = insert(
        table="tft_matches",
        values={
            "gameId": "LOCAL_DEMO_GAME",
            "gameDuration": 1234.5,
            "level": 8,
            "lastRound": 30,
            "Ranked": 1,
            "ingameDuration": 1200.0,
            "combination": "{}",
            "champion": "{}",
        },
    )
    valid_aggregate = aggregate(
        table="tft_matches",
        metric="avg",
        column="level",
        group_by="Ranked",
    )

    invalid_error = None
    try:
        search(table="missing_table")
    except Exception as exc:  # noqa: BLE001 - verification wants the message
        invalid_error = str(exc)

    return {
        "database_created": True,
        "valid_search_rows": valid_search["row_count"],
        "inserted_row_id": valid_insert["inserted_id"],
        "aggregate_groups": len(valid_aggregate["rows"]),
        "full_schema_available": bool(json.loads(database_schema())),
        "table_schema_available": bool(json.loads(table_schema("tft_matches"))),
        "invalid_error": invalid_error,
    }


if __name__ == "__main__":
    print(json.dumps(run_verification(), indent=2))
