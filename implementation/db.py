from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

try:
    from implementation.init_db import DB_PATH, create_database
except ImportError:  # pragma: no cover - support running as a plain script
    from init_db import DB_PATH, create_database


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    """SQLite adapter with identifier validation and parameterized queries."""

    SUPPORTED_OPERATORS = {
        "=": "=",
        "==": "=",
        "eq": "=",
        "!=": "!=",
        "ne": "!=",
        ">": ">",
        "gt": ">",
        ">=": ">=",
        "gte": ">=",
        "<": "<",
        "lt": "<",
        "<=": "<=",
        "lte": "<=",
        "like": "LIKE",
        "in": "IN",
    }

    AGGREGATES = {"count", "avg", "sum", "min", "max"}

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = Path(create_database(db_path)).resolve()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def list_tables(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        table_name = self._validate_table(table)
        with self.connect() as connection:
            rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": bool(row["notnull"]),
                "default_value": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table_name = self._validate_table(table)
        column_names = self._validate_columns(table_name, columns)
        where_sql, parameters = self._build_where_clause(table_name, filters)

        limit_value = self._coerce_non_negative_int(limit, "limit")
        offset_value = self._coerce_non_negative_int(offset, "offset")

        query = f"SELECT {', '.join(column_names)} FROM {table_name}"
        if where_sql:
            query += f" WHERE {where_sql}"

        if order_by:
            order_column = self._validate_column(table_name, order_by)
            direction = "DESC" if descending else "ASC"
            query += f" ORDER BY {order_column} {direction}"

        query += " LIMIT ? OFFSET ?"
        parameters.extend([limit_value, offset_value])

        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return {
            "table": table_name,
            "columns": column_names,
            "filters": filters or [],
            "limit": limit_value,
            "offset": offset_value,
            "order_by": order_by,
            "descending": bool(descending),
            "row_count": len(rows),
            "rows": [dict(row) for row in rows],
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table_name = self._validate_table(table)

        if not isinstance(values, dict) or not values:
            raise ValidationError("insert requires a non-empty values object")

        allowed_columns = {
            column["name"]
            for column in self.get_table_schema(table_name)
            if not column["primary_key"]
        }

        invalid_columns = sorted(set(values) - allowed_columns)
        if invalid_columns:
            raise ValidationError(
                f"unknown columns for table '{table_name}': {', '.join(invalid_columns)}"
            )

        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        query = (
            f"INSERT INTO {table_name} ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )

        with self.connect() as connection:
            cursor = connection.execute(query, [values[column] for column in columns])
            inserted_id = cursor.lastrowid
            connection.commit()
            inserted_row = connection.execute(
                f"SELECT * FROM {table_name} WHERE id = ?",
                [inserted_id],
            ).fetchone()

        return {
            "table": table_name,
            "inserted_id": inserted_id,
            "values": dict(inserted_row) if inserted_row is not None else values,
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        table_name = self._validate_table(table)
        metric_name = str(metric).lower()
        if metric_name not in self.AGGREGATES:
            raise ValidationError(
                f"unsupported metric '{metric}'. Allowed: {', '.join(sorted(self.AGGREGATES))}"
            )

        if metric_name == "count":
            metric_target = "*" if column is None else self._validate_column(table_name, column)
        else:
            if column is None:
                raise ValidationError(f"metric '{metric_name}' requires a column")
            metric_target = self._validate_column(table_name, column)

        group_columns = self._normalize_group_by(table_name, group_by)
        where_sql, parameters = self._build_where_clause(table_name, filters)

        select_parts = []
        if group_columns:
            select_parts.extend(group_columns)
        select_parts.append(f"{metric_name.upper()}({metric_target}) AS value")

        query = f"SELECT {', '.join(select_parts)} FROM {table_name}"
        if where_sql:
            query += f" WHERE {where_sql}"
        if group_columns:
            query += f" GROUP BY {', '.join(group_columns)}"

        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return {
            "table": table_name,
            "metric": metric_name,
            "column": column,
            "group_by": group_columns,
            "filters": filters or [],
            "rows": [dict(row) for row in rows],
        }

    def database_schema(self) -> dict[str, list[dict[str, Any]]]:
        return {table: self.get_table_schema(table) for table in self.list_tables()}

    def _validate_table(self, table: str) -> str:
        if not isinstance(table, str) or not table.strip():
            raise ValidationError("table name must be a non-empty string")

        table_name = table.strip()
        if table_name not in self.list_tables():
            raise ValidationError(f"unknown table '{table_name}'")
        return table_name

    def _validate_columns(self, table: str, columns: list[str] | None) -> list[str]:
        if columns is None:
            return [column["name"] for column in self.get_table_schema(table)]

        if not isinstance(columns, list) or not columns:
            raise ValidationError("columns must be a non-empty list when provided")

        return [self._validate_column(table, column) for column in columns]

    def _validate_column(self, table: str, column: str) -> str:
        if not isinstance(column, str) or not column.strip():
            raise ValidationError("column names must be non-empty strings")

        allowed = {item["name"] for item in self.get_table_schema(table)}
        normalized = column.strip()
        if normalized not in allowed:
            raise ValidationError(f"unknown column '{normalized}' for table '{table}'")
        return normalized

    def _build_where_clause(
        self,
        table: str,
        filters: list[dict[str, Any]] | None,
    ) -> tuple[str, list[Any]]:
        if filters is None:
            return "", []
        if not isinstance(filters, list):
            raise ValidationError("filters must be a list of filter objects")

        clauses: list[str] = []
        parameters: list[Any] = []
        for filter_item in filters:
            if not isinstance(filter_item, dict):
                raise ValidationError("each filter must be an object")

            column = self._validate_column(table, filter_item.get("column"))
            operator_key = str(filter_item.get("op", "=")).lower()
            operator = self.SUPPORTED_OPERATORS.get(operator_key)
            if operator is None:
                raise ValidationError(f"unsupported operator '{filter_item.get('op')}'")

            value = filter_item.get("value")
            if operator == "IN":
                if not isinstance(value, list) or not value:
                    raise ValidationError("operator 'in' requires a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{column} IN ({placeholders})")
                parameters.extend(value)
            else:
                clauses.append(f"{column} {operator} ?")
                parameters.append(value)

        return " AND ".join(clauses), parameters

    def _normalize_group_by(
        self,
        table: str,
        group_by: str | list[str] | None,
    ) -> list[str]:
        if group_by is None:
            return []
        if isinstance(group_by, str):
            return [self._validate_column(table, group_by)]
        if isinstance(group_by, list) and group_by:
            return [self._validate_column(table, column) for column in group_by]
        raise ValidationError("group_by must be a string or a non-empty list")

    def _coerce_non_negative_int(self, value: Any, field_name: str) -> int:
        try:
            coerced = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{field_name} must be an integer") from exc
        if coerced < 0:
            raise ValidationError(f"{field_name} must be >= 0")
        return coerced
