from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import duckdb
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_FILE = PROJECT_ROOT / "telco.duckdb"

MODEL = os.getenv(
    "POC_MODEL",
    "gpt-5.4-nano",
)

MAX_RESULT_ROWS = 100


# ============================================================
# STRUCTURED MODEL OUTPUT
# ============================================================

class SQLPlan(BaseModel):
    can_answer: bool
    sql: str | None = None
    reason: str | None = None


# ============================================================
# DATABASE
# ============================================================

def _connect():
    return duckdb.connect(
        str(DB_FILE),
        read_only=True,
    )


# ============================================================
# SCHEMA DISCOVERY
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

        schema_parts: list[str] = []

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

            schema_parts.append(
                f"{table}("
                + ", ".join(columns)
                + ")"
            )

        return "\n".join(schema_parts)

    finally:
        con.close()


# ============================================================
# SQL GENERATOR
# ============================================================

def _build_model():

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=1600,
    )

    return llm.with_structured_output(
        SQLPlan,
        method="json_schema",
    )


def generate_sql(
    *,
    question: str,
    schema: str,
) -> SQLPlan:

    model = _build_model()

    prompt = f"""
        ROLE|DUCKDB_SQL_PLANNER

        Your only task is to translate the user's question
        into ONE read-only DuckDB SQL query.

        DATABASE SCHEMA|
        {schema}

        RULES|
        - Use only tables and columns in DATABASE SCHEMA.
        - Never invent tables.
        - Never invent columns.
        - SELECT or WITH...SELECT only.
        - Never use SELECT *.
        - DuckDB SQL syntax only.
        - Prefer database aggregation over returning raw rows.
        - If calculations apply to a complete window, use all matching rows.
        - Do not arbitrarily LIMIT rows before aggregation.
        - Do not calculate or explain the answer yourself.
        
        SQL COMPLEXITY RULES
        1. Generate DuckDB SQL only.
        2. Prefer the simplest query that answers the question.
        3. Prefer one SELECT over nested queries.
        4. Use CTEs only when necessary.
        5. Never place a window function inside an aggregate expression.
        6. If window calculations are required:
            CTE 1 -> calculate window functions
            outer SELECT -> aggregate them
        7. Use DuckDB syntax:
            quantile_cont(column, 0.95)
        8. Never invent functions.
        9. Never invent tables or columns.
        10. Do not calculate evidence that was not requested.

        DUCKDB FUNCTION SYNTAX|
        Average:
        AVG(column)

        Minimum:
        MIN(column)

        Maximum:
        MAX(column)

        Percentile:
        quantile_cont(column, 0.95)

        Correlation:
        corr(column_a, column_b)

        Conditional count:
        SUM(CASE WHEN condition THEN 1 ELSE 0 END)

        Conditional percentage:
        100.0 * SUM(CASE WHEN condition THEN 1 ELSE 0 END) / COUNT(*)

        Equal sample buckets:
        NTILE(8) OVER (ORDER BY sample_index)

        IMPORTANT|
        For percentile calculations use:
        quantile_cont(metric_column, percentile)

        Do NOT use:
        quantile_cont(percentile)(metric_column)

        If the schema cannot answer the question:
        can_answer=false and sql=null.

        QUESTION|
        {question}
        """

    return model.invoke(prompt)



def repair_sql(
    *,
    question: str,
    schema: str,
    failed_sql: str,
    database_error: str,
) -> SQLPlan:

    model = _build_model()

    prompt = f"""
ROLE|DUCKDB_SQL_REPAIR

Your only task is to repair ONE failed
read-only DuckDB SQL query.

DATABASE SCHEMA|
{schema}

ORIGINAL QUESTION|
{question}

FAILED SQL|
{failed_sql}

DUCKDB ERROR|
{database_error}

RULES|
- Fix only what is necessary.
- DuckDB SQL syntax only.
- Use only supplied tables and columns.
- Never invent columns or tables.
- SELECT or WITH...SELECT only.
- Never use SELECT *.
- Do not explain the repair.
- Return the corrected SQL through SQLPlan.

DUCKDB EXAMPLES|

Percentile:
quantile_cont(column, 0.95)

Correlation:
corr(column_a, column_b)

Equal buckets:
NTILE(8) OVER (ORDER BY sample_index)

Conditional percentage:
100.0 * SUM(
    CASE WHEN condition THEN 1 ELSE 0 END
) / COUNT(*)
"""

    return model.invoke(prompt)

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
        raise ValueError(
            "Empty SQL query."
        )

    cleaned = sql.strip().rstrip(";")
    lowered = cleaned.lower()

    # SELECT / CTE only
    if not (
        lowered.startswith("select")
        or lowered.startswith("with")
    ):
        raise ValueError(
            "Only SELECT queries are allowed."
        )

    # Single statement only
    if ";" in cleaned:
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    # Dangerous operations
    for keyword in FORBIDDEN_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            lowered,
        ):
            raise ValueError(
                f"Forbidden SQL keyword: {keyword}"
            )

    # --------------------------------------------------------
    # CTE discovery
    # --------------------------------------------------------

    cte_names = {
        name.lower()
        for name in re.findall(
            r"""
            (?:WITH|,)
            \s*
            ([a-zA-Z_][a-zA-Z0-9_]*)
            \s+AS\s*\(
            """,
            cleaned,
            flags=(
                re.IGNORECASE
                | re.VERBOSE
            ),
        )
    }

    # --------------------------------------------------------
    # Physical table references
    # --------------------------------------------------------

    referenced_tables: set[str] = set()

    for match in re.finditer(
        r"""
        \b(?:FROM|JOIN)\s+
        (?:
            ["`]
            ([a-zA-Z_][a-zA-Z0-9_]*)
            ["`]
            |
            ([a-zA-Z_][a-zA-Z0-9_]*)
        )
        """,
        cleaned,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    ):

        table_name = (
            match.group(1)
            or match.group(2)
        )

        if table_name:
            referenced_tables.add(
                table_name.lower()
            )

    physical_tables = (
        referenced_tables
        - cte_names
    )

    allowed_lower = {
        table.lower()
        for table in allowed_tables
    }

    invalid_tables = (
        physical_tables
        - allowed_lower
    )

    if invalid_tables:
        raise ValueError(
            "Unauthorized table(s): "
            + ", ".join(
                sorted(invalid_tables)
            )
        )

    return cleaned


# ============================================================
# DUCKDB VALIDATION
# ============================================================

def validate_with_duckdb(
    sql: str,
) -> None:

    con = _connect()

    try:
        # DuckDB validates syntax, columns, joins, functions, etc.
        con.execute(
            f"EXPLAIN {sql}"
        )

    finally:
        con.close()


# ============================================================
# EXECUTION
# ============================================================

def execute_sql(
    sql: str,
) -> dict[str, Any]:

    con = _connect()

    try:
        # Bound only the FINAL output.
        # The inner SQL can still process all matching rows.
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


# ============================================================
# PUBLIC TOOL
# ============================================================


def sql_tool(
    *,
    question: str,
    allowed_tables: set[str],
) -> dict[str, Any]:

    schema = get_schema(
        allowed_tables
    )

    if not schema:

        return {
            "status": "failed",
            "stage": "schema",
            "error": "No allowed tables found.",
        }

    # ========================================================
    # ATTEMPT 1 — GENERATE
    # ========================================================

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
                or "Question cannot be answered "
                   "from the available schema."
            ),
        }

    if not plan.sql:

        return {
            "status": "failed",
            "stage": "generation",
            "error": "Planner returned no SQL.",
        }

    original_sql = plan.sql

    # ========================================================
    # ATTEMPT 1 — VALIDATE
    # ========================================================

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

        # ====================================================
        # ONE REPAIR ATTEMPT
        # ====================================================

        try:

            repaired_plan = repair_sql(
                question=question,
                schema=schema,
                failed_sql=original_sql,
                database_error=str(
                    first_error
                ),
            )

        except Exception as repair_error:

            return {
                "status": "failed",
                "stage": "repair_generation",
                "sql": original_sql,
                "error": str(repair_error),
            }

        if (
            not repaired_plan.can_answer
            or not repaired_plan.sql
        ):

            return {
                "status": "failed",
                "stage": "repair",
                "sql": original_sql,
                "error": str(first_error),
            }

        try:

            validated_sql = validate_sql(
                sql=repaired_plan.sql,
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
                "original_sql": original_sql,
                "sql": repaired_plan.sql,
                "error": str(second_error),
                "repair_used": True,
            }

    # ========================================================
    # EXECUTE
    # ========================================================

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

