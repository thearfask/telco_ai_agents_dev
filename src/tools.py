from __future__ import annotations

import json
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import duckdb

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from pydantic import BaseModel

from prompts import (
    SQL_PLANNER_PROMPT,
    SQL_REPAIR_PROMPT,
)


# ============================================================
# PATHS
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_FILE = PROJECT_ROOT / "telco.duckdb"

KNOWLEDGE_FILE = (
    PROJECT_ROOT
    / "config"
    / "kpi_reference.md"
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


MODEL = "gpt-5.4-nano"

MAX_RESULT_ROWS = 100


# ============================================================
# RUNTIME CREDENTIAL
#
# Never enters LangGraph investigation state.
# ============================================================


_API_KEY: ContextVar[str | None] = ContextVar(
    "openai_api_key",
    default=None,
)


def set_runtime_api_key(
    api_key: str,
) -> None:
    _API_KEY.set(api_key)


def get_runtime_api_key() -> str:
    api_key = _API_KEY.get()

    if not api_key:
        raise RuntimeError(
            "OpenAI API key is not configured for this runtime."
        )

    return api_key


# ============================================================
# LLM
# ============================================================


def create_llm(
    *,
    max_completion_tokens: int = 1600,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL,
        api_key=get_runtime_api_key(),
        temperature=0,
        reasoning_effort="low",
        max_completion_tokens=max_completion_tokens,
        use_responses_api=True,
    )


# ============================================================
# SQL MODELS
# ============================================================


class SQLPlan(BaseModel):
    can_answer: bool
    sql: str | None = None
    reason: str | None = None


# ============================================================
# DATABASE
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


# ============================================================
# SCHEMA
# ============================================================


def get_schema(
    allowed_tables: set[str],
) -> str:
    con = _connect()

    try:
        existing_tables = {
            row[0]
            for row in con.execute(
                "SHOW TABLES"
            ).fetchall()
        }

        parts = []

        for table in sorted(allowed_tables):
            if table not in existing_tables:
                continue

            rows = con.execute(
                f'DESCRIBE "{table}"'
            ).fetchall()

            columns = [
                f"{row[0]} {row[1]}"
                for row in rows
            ]

            parts.append(
                f"{table}("
                + ", ".join(columns)
                + ")"
            )

        return "\n".join(parts)

    finally:
        con.close()


# ============================================================
# SQL GENERATION
# ============================================================


def _sql_model():
    return create_llm(
        max_completion_tokens=1600,
    ).with_structured_output(
        SQLPlan,
        method="json_schema",
    )


def generate_sql(
    *,
    question: str,
    schema: str,
) -> SQLPlan:
    prompt = f"""
{SQL_PLANNER_PROMPT}

DATABASE SCHEMA|
{schema}

QUESTION|
{question}
"""

    return _sql_model().invoke(prompt)


def repair_sql(
    *,
    question: str,
    schema: str,
    failed_sql: str,
    database_error: str,
) -> SQLPlan:
    prompt = f"""
{SQL_REPAIR_PROMPT}

DATABASE SCHEMA|
{schema}

ORIGINAL QUESTION|
{question}

FAILED SQL|
{failed_sql}

DUCKDB ERROR|
{database_error}
"""

    return _sql_model().invoke(prompt)


# ============================================================
# SQL SAFETY
# ============================================================


FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "attach",
    "detach",
    "copy",
    "export",
    "import",
    "truncate",
    "pragma",
    "call",
}


def validate_sql(
    *,
    sql: str,
    allowed_tables: set[str],
) -> str:
    if not sql:
        raise ValueError("Empty SQL query.")

    cleaned = sql.strip().rstrip(";")
    lowered = cleaned.lower()

    if not (
        lowered.startswith("select")
        or lowered.startswith("with")
    ):
        raise ValueError(
            "Only SELECT queries are allowed."
        )

    if ";" in cleaned:
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(
            rf"\b{keyword}\b",
            lowered,
        ):
            raise ValueError(
                f"Forbidden SQL keyword: {keyword}"
            )

    cte_names = {
        name.lower()
        for name in re.findall(
            r"(?:WITH|,)\s*"
            r"([a-zA-Z_][a-zA-Z0-9_]*)"
            r"\s+AS\s*\(",
            cleaned,
            flags=re.IGNORECASE,
        )
    }

    referenced_tables = set()

    for match in re.finditer(
        r'\b(?:FROM|JOIN)\s+'
        r'(?:"([a-zA-Z_][a-zA-Z0-9_]*)"'
        r'|([a-zA-Z_][a-zA-Z0-9_]*))',
        cleaned,
        flags=re.IGNORECASE,
    ):
        table = (
            match.group(1)
            or match.group(2)
        )

        if table:
            referenced_tables.add(
                table.lower()
            )

    physical_tables = (
        referenced_tables
        - cte_names
    )

    allowed_lower = {
        table.lower()
        for table in allowed_tables
    }

    invalid = (
        physical_tables
        - allowed_lower
    )

    if invalid:
        raise ValueError(
            "Unauthorized table(s): "
            + ", ".join(sorted(invalid))
        )

    return cleaned


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


# ============================================================
# SQL EXECUTION
# ============================================================


def execute_sql(
    sql: str,
) -> dict[str, Any]:
    con = _connect()

    try:
        bounded_sql = f"""
        SELECT *
        FROM (
            {sql}
        ) AS final_query
        LIMIT {MAX_RESULT_ROWS}
        """

        result = con.execute(
            bounded_sql
        )

        columns = [
            column[0]
            for column in result.description
        ]

        rows = result.fetchall()

        return {
            "columns": columns,
            "rows": [
                dict(zip(columns, row))
                for row in rows
            ],
            "row_count": len(rows),
        }

    finally:
        con.close()


def sql_tool(
    *,
    question: str,
    allowed_tables: set[str],
) -> dict[str, Any]:
    try:
        schema = get_schema(
            allowed_tables
        )
    except Exception as exc:
        return {
            "status": "failed",
            "stage": "schema",
            "error": str(exc),
        }

    if not schema:
        return {
            "status": "unsupported",
            "reason": (
                "None of the requested tables exist "
                "in the current DuckDB database."
            ),
        }

    try:
        plan = generate_sql(
            question=question,
            schema=schema,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "stage": "generation",
            "error": str(exc),
        }

    if not plan.can_answer:
        return {
            "status": "unsupported",
            "reason": (
                plan.reason
                or "The available schema cannot answer this question."
            ),
        }

    if not plan.sql:
        return {
            "status": "failed",
            "stage": "generation",
            "error": "SQL planner returned no SQL.",
        }

    original_sql = plan.sql

    try:
        validated_sql = validate_sql(
            sql=original_sql,
            allowed_tables=allowed_tables,
        )

        validate_with_duckdb(
            validated_sql
        )

        repair_used = False

    except Exception as first_error:
        try:
            repaired = repair_sql(
                question=question,
                schema=schema,
                failed_sql=original_sql,
                database_error=str(first_error),
            )

            if (
                not repaired.can_answer
                or not repaired.sql
            ):
                return {
                    "status": "failed",
                    "stage": "repair",
                    "sql": original_sql,
                    "error": str(first_error),
                }

            validated_sql = validate_sql(
                sql=repaired.sql,
                allowed_tables=allowed_tables,
            )

            validate_with_duckdb(
                validated_sql
            )

            repair_used = True

        except Exception as second_error:
            return {
                "status": "failed",
                "stage": "validation_after_repair",
                "sql": original_sql,
                "error": str(second_error),
                "repair_used": True,
            }

    try:
        result = execute_sql(
            validated_sql
        )
    except Exception as exc:
        return {
            "status": "failed",
            "stage": "execution",
            "sql": validated_sql,
            "error": str(exc),
            "repair_used": repair_used,
        }

    return {
        "status": "completed",
        "sql": validated_sql,
        "repair_used": repair_used,
        "result": result,
    }


# ============================================================
# KNOWLEDGE SEARCH
#
# This is NOT vector RAG yet.
# It searches the real project knowledge document.
# ============================================================


def search_knowledge_raw(
    query: str,
    top_k: int = 4,
) -> dict:
    if not KNOWLEDGE_FILE.exists():
        return {
            "status": "unavailable",
            "reason": (
                f"Knowledge file not found: "
                f"{KNOWLEDGE_FILE}"
            ),
            "results": [],
        }

    text = KNOWLEDGE_FILE.read_text(
        encoding="utf-8"
    )

    sections = re.split(
        r"\n(?=#{1,4}\s)",
        text,
    )

    query_tokens = set(
        re.findall(
            r"[a-z0-9_]+",
            query.lower(),
        )
    )

    scored = []

    for section in sections:
        section = section.strip()

        if not section:
            continue

        tokens = set(
            re.findall(
                r"[a-z0-9_]+",
                section.lower(),
            )
        )

        score = len(
            query_tokens & tokens
        )

        if score:
            scored.append(
                (score, section)
            )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    top_k = max(
        1,
        min(int(top_k), 5),
    )

    results = [
        {
            "source": str(KNOWLEDGE_FILE),
            "score": score,
            "content": section[:2500],
        }
        for score, section
        in scored[:top_k]
    ]

    return {
        "status": "completed",
        "retrieval_type": "keyword",
        "results": results,
    }


# ============================================================
# LOG SEARCH
# ============================================================


def search_logs_raw(
    query: str,
    window_ids: list[str] | None = None,
    limit: int = 15,
) -> dict:
    if not LOG_FILE.exists():
        return {
            "status": "unavailable",
            "reason": (
                "No operational log dataset has been configured."
            ),
            "results": [],
        }

    query_tokens = set(
        re.findall(
            r"[a-z0-9_]+",
            query.lower(),
        )
    )

    wanted_windows = set(
        window_ids or []
    )

    matches = []

    with LOG_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue

            if (
                wanted_windows
                and row.get("window_id")
                not in wanted_windows
            ):
                continue

            searchable = json.dumps(
                row,
                default=str,
            ).lower()

            tokens = set(
                re.findall(
                    r"[a-z0-9_]+",
                    searchable,
                )
            )

            score = len(
                query_tokens & tokens
            )

            if query_tokens and score == 0:
                continue

            matches.append(
                (score, row)
            )

    matches.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    rows = [
        row
        for _, row
        in matches[:limit]
    ]

    return {
        "status": "completed",
        "row_count": len(rows),
        "results": rows,
    }


# ============================================================
# TOPOLOGY
# ============================================================


def query_graph_raw(
    node_ids: list[str],
) -> dict:
    if not TOPOLOGY_FILE.exists():
        return {
            "status": "unavailable",
            "reason": (
                "No topology dataset has been configured."
            ),
            "results": [],
        }

    wanted = set(node_ids)

    results = []

    with TOPOLOGY_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue

            if (
                row.get("src") in wanted
                or row.get("dst") in wanted
            ):
                results.append(row)

    return {
        "status": "completed",
        "results": results[:30],
    }


# ============================================================
# LANGCHAIN TOOLS
# ============================================================


SQL_TABLES = {
    "telemetry_windows",
    "telemetry_summary",
    "telemetry_measurements",
    "alarms",
    "alarm_events",
    "topology_nodes",
    "topology_edges",
}


@tool
def query_sql(
    question: str,
) -> str:
    """
    Query structured operational data using read-only DuckDB SQL.
    """
    result = sql_tool(
        question=question,
        allowed_tables=SQL_TABLES,
    )

    return json.dumps(
        result,
        default=str,
        separators=(",", ":"),
    )


@tool
def search_knowledge(
    query: str,
    top_k: int = 4,
) -> str:
    """
    Search the project's engineering knowledge reference.
    """
    result = search_knowledge_raw(
        query=query,
        top_k=top_k,
    )

    return json.dumps(
        result,
        default=str,
        separators=(",", ":"),
    )


@tool
def search_logs(
    query: str,
    window_ids: list[str] | None = None,
) -> str:
    """
    Search operational logs when a log dataset is available.
    """
    result = search_logs_raw(
        query=query,
        window_ids=window_ids,
    )

    return json.dumps(
        result,
        default=str,
        separators=(",", ":"),
    )


@tool
def query_graph(
    node_ids: list[str],
) -> str:
    """
    Query topology relationships when topology data is available.
    """
    result = query_graph_raw(
        node_ids=node_ids,
    )

    return json.dumps(
        result,
        default=str,
        separators=(",", ":"),
    )


COMMON_TOOLS = [
    query_sql,
    search_knowledge,
    search_logs,
    query_graph,
]