from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from langchain_core.tools import tool
from pydantic import BaseModel

from sqlglot import (
    exp,
    parse,
)
from sqlglot.errors import (
    ParseError,
)

from config import get_runtime_config
from intelligence import (
    find_patterns,
    resolve_metrics,
    search_runbooks,
)
from llm import get_llm
from prompts import SQL_REPAIR_PROMPT


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_FILE = (
    PROJECT_ROOT
    / "telco.duckdb"
)

LOG_FILE = (
    PROJECT_ROOT
    / "data"
    / "logs.jsonl"
)

TOPOLOGY_FILE = (
    PROJECT_ROOT
    / "data"
    / "topology.jsonl"
)


TELEMETRY_TABLES = {
    "telemetry_windows",
    "telemetry_summary",
    "telemetry_measurements",
}


# ============================================================
# DB
# ============================================================


def _connect():
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"DuckDB database not found: {DB_FILE}"
        )

    return duckdb.connect(
        str(DB_FILE),
        read_only=True,
    )


def get_schema(
    allowed_tables: set[str],
) -> str:

    con = _connect()

    try:

        existing = {
            row[0]
            for row in con.execute(
                "SHOW TABLES"
            ).fetchall()
        }

        sections = []

        for table in sorted(
            allowed_tables
        ):

            if table not in existing:
                continue

            rows = con.execute(
                f'DESCRIBE "{table}"'
            ).fetchall()

            columns = [
                f"{row[0]} {row[1]}"
                for row in rows
            ]

            sections.append(
                f"{table}("
                + ", ".join(
                    columns
                )
                + ")"
            )

        return "\n".join(
            sections
        )

    finally:
        con.close()


# ============================================================
# SQL AST VALIDATION
# ============================================================


FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
)


def parse_sql(
    sql: str,
) -> exp.Expression:

    if not sql.strip():
        raise ValueError(
            "SQL is empty."
        )

    try:

        trees = parse(
            sql,
            read="duckdb",
        )

    except ParseError as exc:

        raise ValueError(
            f"Invalid DuckDB SQL: {exc}"
        ) from exc

    if len(trees) != 1:
        raise ValueError(
            "Exactly one SQL statement is allowed."
        )

    tree = trees[0]

    if tree is None:
        raise ValueError(
            "SQL parser returned no statement."
        )

    return tree


def _cte_names(
    tree: exp.Expression,
) -> set[str]:

    return {
        cte.alias_or_name.lower()
        for cte in tree.find_all(
            exp.CTE
        )
        if cte.alias_or_name
    }


def _physical_tables(
    tree: exp.Expression,
) -> set[str]:

    ctes = _cte_names(
        tree
    )

    tables = set()

    for table in tree.find_all(
        exp.Table
    ):

        name = (
            table.name
            .strip()
            .lower()
        )

        if (
            name
            and name not in ctes
        ):
            tables.add(
                name
            )

    return tables


def validate_sql(
    sql: str,
    allowed_tables: set[str],
    required_window_ids: list[str] | None = None,
) -> str:

    tree = parse_sql(
        sql
    )

    for node_type in (
        FORBIDDEN_NODES
    ):
        if tree.find(
            node_type
        ):
            raise ValueError(
                "Read-only SQL required. "
                f"Forbidden node: {node_type.__name__}"
            )

    if not isinstance(
        tree,
        (
            exp.Select,
            exp.Union,
            exp.Intersect,
            exp.Except,
        ),
    ):
        raise ValueError(
            "Only SELECT queries are allowed."
        )

    tables = _physical_tables(
        tree
    )

    allowed = {
        table.lower()
        for table in allowed_tables
    }

    unauthorized = (
        tables
        - allowed
    )

    if unauthorized:
        raise ValueError(
            "Unauthorized table(s): "
            + ", ".join(
                sorted(
                    unauthorized
                )
            )
        )

    required_window_ids = (
        required_window_ids
        or []
    )

    if required_window_ids:

        literals = {
            str(
                literal.this
            ).upper()
            for literal in tree.find_all(
                exp.Literal
            )
            if literal.is_string
        }

        missing = {
            window.upper()
            for window
            in required_window_ids
            if window.upper()
            not in literals
        }

        if missing:
            raise ValueError(
                "SQL dropped required "
                "window scope: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )

        # If telemetry measurements are used,
        # window_id must appear in the AST.
        if (
            "telemetry_measurements"
            in tables
        ):

            columns = {
                column.name.lower()
                for column
                in tree.find_all(
                    exp.Column
                )
                if column.name
            }

            if (
                "window_id"
                not in columns
            ):
                raise ValueError(
                    "telemetry_measurements must "
                    "be directly scoped by window_id."
                )

    return tree.sql(
        dialect="duckdb",
        pretty=True,
    )


def validate_with_duckdb(
    sql: str,
) -> None:

    con = _connect()

    try:
        con.execute(
            f"EXPLAIN {sql}"
        )

    finally:
        con.close()


def execute_sql(
    sql: str,
) -> dict[str, Any]:

    max_rows = int(
        get_runtime_config().get(
            "max_sql_result_rows",
            150,
        )
    )

    con = _connect()

    try:

        bounded_sql = f"""
        SELECT *
        FROM (
            {sql}
        ) AS bounded_result
        LIMIT {max_rows}
        """

        result = con.execute(
            bounded_sql
        )

        columns = [
            item[0]
            for item
            in result.description
        ]

        rows = result.fetchall()

        return {
            "columns": columns,
            "rows": [
                dict(
                    zip(
                        columns,
                        row,
                    )
                )
                for row in rows
            ],
            "row_count": len(
                rows
            ),
            "truncated_at": (
                max_rows
                if len(rows)
                >= max_rows
                else None
            ),
        }

    finally:
        con.close()


# ============================================================
# SQL REPAIR
# ============================================================


class SQLRepairResult(BaseModel):

    can_answer: bool

    sql: str | None = None

    reason: str | None = None


def repair_sql(
    *,
    purpose: str,
    original_sql: str,
    error: str,
    schema: str,
    window_ids: list[str],
) -> SQLRepairResult:

    model = (
        get_llm(
            "sql"
        )
        .with_structured_output(
            SQLRepairResult,
            method="json_schema",
        )
    )

    prompt = f"""
{SQL_REPAIR_PROMPT}

EVIDENCE GOAL|
{purpose}

REQUIRED WINDOW IDS|
{window_ids}

ALLOWED SCHEMA|
{schema}

FAILED SQL|
{original_sql}

ERROR|
{error}
"""

    return model.invoke(
        prompt
    )


def run_guarded_sql(
    *,
    sql: str,
    purpose: str,
    allowed_tables: set[str],
    window_ids: list[str],
) -> dict:

    schema = get_schema(
        allowed_tables
    )

    try:

        validated = validate_sql(
            sql,
            allowed_tables,
            required_window_ids=(
                window_ids
            ),
        )

        validate_with_duckdb(
            validated
        )

        result = execute_sql(
            validated
        )

        return {
            "status": "completed",
            "repair_used": False,
            "sql": validated,
            "result": result,
        }

    except Exception as first_error:

        repair_limit = int(
            get_runtime_config().get(
                "max_sql_repair_attempts",
                1,
            )
        )

        if repair_limit < 1:

            return {
                "status": "failed",
                "error": str(
                    first_error
                ),
                "repair_used": False,
            }

        try:

            repaired = repair_sql(
                purpose=purpose,
                original_sql=sql,
                error=str(
                    first_error
                ),
                schema=schema,
                window_ids=(
                    window_ids
                ),
            )

            if (
                not repaired.can_answer
                or not repaired.sql
            ):

                return {
                    "status": "failed",
                    "error": str(
                        first_error
                    ),
                    "repair_used": True,
                    "repair_reason": (
                        repaired.reason
                    ),
                }

            validated = validate_sql(
                repaired.sql,
                allowed_tables,
                required_window_ids=(
                    window_ids
                ),
            )

            validate_with_duckdb(
                validated
            )

            result = execute_sql(
                validated
            )

            return {
                "status": "completed",
                "repair_used": True,
                "sql": validated,
                "result": result,
            }

        except Exception as repair_error:

            return {
                "status": "failed",
                "repair_used": True,
                "initial_error": str(
                    first_error
                ),
                "repair_error": str(
                    repair_error
                ),
            }


# ============================================================
# TELEMETRY AGENT TOOLS
# ============================================================


@tool
def telemetry_schema() -> str:
    """
    Return the physical telemetry tables and columns currently
    available in DuckDB.

    Use for schema discovery.
    Do not use SQL for schema discovery.
    """

    return get_schema(
        TELEMETRY_TABLES
    )


@tool
def telemetry_metrics(
    concepts: list[str],
) -> str:
    """
    Resolve engineering concepts into authoritative telemetry metrics.

    Use when you know the engineering evidence required but need the
    correct physical metric and its semantics.

    This is knowledge, not incident evidence.
    """

    return json.dumps(
        resolve_metrics(
            concepts
        ),
        default=str,
    )


@tool
def telemetry_patterns(
    query: str,
) -> str:
    """
    Retrieve compact diagnostic patterns for competing telemetry
    hypotheses.

    Use when multiple mechanisms could explain the incident and you
    need evidence that supports or contradicts them.

    This is knowledge, not incident evidence.
    """

    return json.dumps(
        find_patterns(
            query=query,
            domain="telemetry",
            top_k=3,
        ),
        default=str,
    )


@tool
def telemetry_runbook(
    query: str,
) -> str:
    """
    Retrieve deeper telemetry troubleshooting guidance.

    Use only when procedural engineering guidance is genuinely needed.

    This is knowledge, not incident evidence.
    """

    return json.dumps(
        search_runbooks(
            query=query,
            domain="telemetry",
            top_k=3,
        ),
        default=str,
    )


@tool
def telemetry_sql(
    purpose: str,
    sql: str,
    window_ids: list[str],
) -> str:
    """
    Retrieve actual operational telemetry evidence.

    Provide one focused read-only DuckDB query.

    The tool automatically:
    - parses SQL with SQLGlot;
    - enforces allowed tables;
    - enforces window scope;
    - validates with DuckDB;
    - performs one bounded repair attempt when necessary.

    Do not use for schema discovery.
    """

    return json.dumps(
        run_guarded_sql(
            sql=sql,
            purpose=purpose,
            allowed_tables=(
                TELEMETRY_TABLES
            ),
            window_ids=(
                window_ids
            ),
        ),
        default=str,
    )


TELEMETRY_TOOLS = [
    telemetry_patterns,
    telemetry_metrics,
    telemetry_runbook,
    telemetry_schema,
    telemetry_sql,
]


# ============================================================
# ALARM TOOL
# ============================================================


@tool
def alarm_logs(
    query: str,
    window_ids: list[str] | None = None,
) -> str:
    """
    Search operational alarm/log records when a local log dataset exists.
    """

    if not LOG_FILE.exists():

        return json.dumps(
            {
                "status": "unavailable",
                "reason": (
                    "Operational log dataset "
                    "is not configured."
                ),
            }
        )

    wanted = set(
        window_ids
        or []
    )

    query_terms = {
        value.lower()
        for value
        in query.split()
    }

    hits = []

    with LOG_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:

        for line in handle:

            try:
                row = json.loads(
                    line
                )
            except Exception:
                continue

            if (
                wanted
                and row.get(
                    "window_id"
                )
                not in wanted
            ):
                continue

            searchable = json.dumps(
                row
            ).lower()

            score = sum(
                1
                for term
                in query_terms
                if term in searchable
            )

            if score:
                hits.append(
                    (
                        score,
                        row,
                    )
                )

    hits.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return json.dumps(
        {
            "status": "completed",
            "results": [
                item[1]
                for item
                in hits[:30]
            ],
        },
        default=str,
    )


ALARM_TOOLS = [
    alarm_logs,
]


# ============================================================
# TOPOLOGY TOOL
# ============================================================


@tool
def topology_graph(
    node_ids: list[str],
) -> str:
    """
    Return observed topology relationships for supplied node IDs.
    """

    if not TOPOLOGY_FILE.exists():

        return json.dumps(
            {
                "status": "unavailable",
                "reason": (
                    "Topology dataset "
                    "is not configured."
                ),
            }
        )

    wanted = set(
        node_ids
    )

    results = []

    with TOPOLOGY_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:

        for line in handle:

            try:
                row = json.loads(
                    line
                )
            except Exception:
                continue

            if (
                row.get("src")
                in wanted
                or row.get("dst")
                in wanted
            ):
                results.append(
                    row
                )

    return json.dumps(
        {
            "status": "completed",
            "results": (
                results[:30]
            ),
        },
        default=str,
    )


TOPOLOGY_TOOLS = [
    topology_graph,
]