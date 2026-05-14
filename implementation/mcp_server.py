from __future__ import annotations

import json
from typing import Any, Callable

try:
    from implementation.db import SQLiteAdapter, ValidationError
except ImportError:  # pragma: no cover - support running as a plain script
    from db import SQLiteAdapter, ValidationError

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - fallback for environments without fastmcp
    class FastMCP:  # type: ignore[override]
        """Small fallback so local tests can import the module without fastmcp."""

        def __init__(self, name: str):
            self.name = name
            self.tools: dict[str, Callable[..., Any]] = {}
            self.resources: dict[str, Callable[..., Any]] = {}

        def tool(self, name: str):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.tools[name] = func
                return func

            return decorator

        def resource(self, uri: str):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.resources[uri] = func
                return func

            return decorator

        def run(self) -> None:
            raise RuntimeError(
                "fastmcp is not installed. Install it before running the MCP server."
            )


mcp = FastMCP("SQLite Lab MCP Server")
_ADAPTER: SQLiteAdapter | None = None


def _get_adapter() -> SQLiteAdapter:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = SQLiteAdapter()
    return _ADAPTER


@mcp.tool(name="search")
def search(
    table: str,
    filters: list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    return _get_adapter().search(
        table=table,
        filters=filters,
        columns=columns,
        limit=limit,
        offset=offset,
        order_by=order_by,
        descending=descending,
    )


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    return _get_adapter().insert(table=table, values=values)


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: str | list[str] | None = None,
) -> dict[str, Any]:
    return _get_adapter().aggregate(
        table=table,
        metric=metric,
        column=column,
        filters=filters,
        group_by=group_by,
    )


@mcp.resource("schema://database")
def database_schema() -> str:
    return json.dumps(_get_adapter().database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    adapter = _get_adapter()
    return json.dumps(
        {
            "table": adapter._validate_table(table_name),
            "columns": adapter.get_table_schema(table_name),
        },
        indent=2,
    )


if __name__ == "__main__":
    try:
        mcp.run()
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
