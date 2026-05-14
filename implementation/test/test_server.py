from __future__ import annotations

import json
import unittest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database
from implementation.mcp_server import aggregate, database_schema, insert, search, table_schema


class SQLiteLabTests(unittest.TestCase):
    def setUp(self) -> None:
        create_database(reset=True, seed_limit=2000)
        self.adapter = SQLiteAdapter()

    def test_list_tables(self) -> None:
        self.assertEqual(
            self.adapter.list_tables(),
            ["tft_matches"],
        )

    def test_search_with_filters_ordering_and_pagination(self) -> None:
        result = search(
            table="tft_matches",
            filters=[{"column": "Ranked", "op": "=", "value": 1}],
            columns=["gameId", "gameDuration", "Ranked"],
            order_by="gameDuration",
            descending=False,
            limit=1,
            offset=0,
        )

        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["rows"][0]["Ranked"], 1)

    def test_insert_returns_inserted_payload(self) -> None:
        result = insert(
            table="tft_matches",
            values={
                "gameId": "LOCAL_TEST_GAME",
                "gameDuration": 1111.0,
                "level": 9,
                "lastRound": 33,
                "Ranked": 1,
                "ingameDuration": 1100.0,
                "combination": "{}",
                "champion": "{}",
            },
        )

        self.assertIsInstance(result["inserted_id"], int)
        self.assertEqual(result["values"]["gameId"], "LOCAL_TEST_GAME")

    def test_aggregate_average_by_group(self) -> None:
        result = aggregate(
            table="tft_matches",
            metric="avg",
            column="level",
            group_by="Ranked",
        )

        self.assertGreaterEqual(len(result["rows"]), 1)

    def test_schema_resources_are_readable(self) -> None:
        full_schema = json.loads(database_schema())
        table_schema_data = json.loads(table_schema("tft_matches"))

        self.assertIn("tft_matches", full_schema)
        self.assertEqual(table_schema_data["table"], "tft_matches")

    def test_invalid_table_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            search(table="unknown")

    def test_invalid_operator_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            search(
                table="tft_matches",
                filters=[{"column": "score", "op": "between", "value": [1, 2]}],
            )

    def test_empty_insert_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            insert(table="tft_matches", values={})

    def test_invalid_aggregate_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            aggregate(table="tft_matches", metric="median", column="level")


if __name__ == "__main__":
    unittest.main()
