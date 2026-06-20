"""Snowflake connector — pre-built tools over a Snowflake SQL connection.

Unlike the REST connectors, Snowflake is a SQL warehouse, so this uses the official
``snowflake-connector-python`` driver (an **optional** dependency) rather than httpx.
Install it with: ``pip install "roscoe[snowflake]"``.

```yaml
connectors:
  snowflake:
    account: ${SNOWFLAKE_ACCOUNT}
    user: ${SNOWFLAKE_USER}
    password: ${SNOWFLAKE_PASSWORD}
    warehouse: ${SNOWFLAKE_WAREHOUSE}
    database: ${SNOWFLAKE_DATABASE}
    schema: ${SNOWFLAKE_SCHEMA}
```

A live connection can be injected (``connection=...``) for tests, so the driver isn't
needed to exercise the tools.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

#: Max rows returned by a query tool (keeps results context-sized).
MAX_ROWS = 100


class SnowflakeConnector:
    """Tools: run_query, list_tables, describe_table."""

    def __init__(self, config: dict[str, Any], *, connection: Any | None = None) -> None:
        self.config = config
        self._conn = connection if connection is not None else self._connect()

    def _connect(self) -> Any:
        for key in ("account", "user"):
            if not self.config.get(key):
                raise ValueError(f"snowflake connector config missing required key '{key}'.")
        try:
            import snowflake.connector  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "The Snowflake connector needs the optional driver. Install it with "
                '`pip install "roscoe[snowflake]"`.'
            ) from exc

        return snowflake.connector.connect(
            account=self.config["account"],
            user=self.config["user"],
            password=self.config.get("password"),
            warehouse=self.config.get("warehouse"),
            database=self.config.get("database"),
            schema=self.config.get("schema"),
        )

    def _execute(self, sql: str) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            if cur.description is None:
                return []
            columns = [col[0] for col in cur.description]
            rows = cur.fetchmany(MAX_ROWS)
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cur.close()

    @property
    def tools(self) -> list[StructuredTool]:
        def run_query(sql: str) -> list[dict]:
            """Run a read-only SQL query and return up to 100 rows as dicts."""
            return self._execute(sql)

        def list_tables() -> list[dict]:
            """List tables in the configured database/schema."""
            return self._execute("SHOW TABLES")

        def describe_table(table: str) -> list[dict]:
            """Describe the columns of a table."""
            return self._execute(f"DESCRIBE TABLE {table}")

        return [
            StructuredTool.from_function(run_query, description=run_query.__doc__),
            StructuredTool.from_function(list_tables, description=list_tables.__doc__),
            StructuredTool.from_function(describe_table, description=describe_table.__doc__),
        ]

    def close(self) -> None:
        self._conn.close()
