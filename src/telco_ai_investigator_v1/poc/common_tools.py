from __future__ import annotations

import json

from langchain_core.tools import tool

from .graph_tools import (
    query_graph_raw,
)

from .log_tools import (
    search_logs_raw,
)

from .rag_tools import (
    search_knowledge_raw,
)

from .sql_tool import (
    sql_tool,
)


# Add tables here as sources become available.
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

    Use this for:
    - measurements
    - aggregates
    - counts
    - percentages
    - comparisons
    - percentiles
    - simple correlations
    - compact temporal buckets

    Do not use this for engineering documentation or general
    knowledge.

    Ask the smallest analytical question that can resolve the
    current evidence gap.
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
    Retrieve engineering knowledge from the domain knowledge base.

    Use this for:
    - KPI meaning
    - engineering interpretation
    - runbooks
    - troubleshooting guidance
    - alarm definitions
    - known patterns
    - historical engineering knowledge

    Retrieved knowledge is NOT proof that the current incident
    has the same root cause.
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
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 15,
) -> str:
    """
    Search operational logs and events.

    Use this for:
    - errors
    - warnings
    - event sequences
    - protocol events
    - component messages
    - events around an incident time/window
    """

    result = search_logs_raw(
        query=query,
        window_ids=window_ids,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    return json.dumps(
        result,
        default=str,
        separators=(",", ":"),
    )


@tool
def query_graph(
    node_ids: list[str],
    max_hops: int = 2,
) -> str:
    """
    Query network topology relationships.

    Use this for:
    - what serves a component
    - upstream/downstream dependencies
    - shared infrastructure
    - blast-radius relationships
    - component containment/connectivity
    """

    result = query_graph_raw(
        node_ids=node_ids,
        max_hops=max_hops,
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