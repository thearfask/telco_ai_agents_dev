from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


LOG_FILE = os.getenv(
    "POC_LOG_FILE",
    "data/poc_logs.jsonl",
)


def _parse_time(
    value: str | None,
) -> datetime | None:

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value
        )
    except Exception:
        return None


def _load_logs() -> list[dict]:

    path = Path(
        LOG_FILE
    )

    if not path.exists():
        return []

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        for line in handle:

            line = line.strip()

            if not line:
                continue

            try:
                rows.append(
                    json.loads(line)
                )
            except Exception:
                continue

    return rows


def _tokens(
    value: str,
) -> set[str]:

    return set(
        re.findall(
            r"[a-z0-9_]+",
            value.lower(),
        )
    )


def search_logs_raw(
    query: str,
    window_ids: list[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 15,
) -> dict:

    rows = _load_logs()

    if not rows:

        return {
            "status": "unavailable",
            "reason": (
                f"No log dataset found at {LOG_FILE}"
            ),
            "results": [],
        }

    limit = max(
        1,
        min(
            int(limit),
            20,
        ),
    )

    wanted_windows = set(
        window_ids or []
    )

    start = _parse_time(
        start_time
    )

    end = _parse_time(
        end_time
    )

    query_tokens = _tokens(
        query
    )

    matches = []

    for row in rows:

        if wanted_windows:

            if (
                row.get("window_id")
                not in wanted_windows
            ):
                continue

        event_time = _parse_time(
            row.get("timestamp")
        )

        if (
            start
            and event_time
            and event_time < start
        ):
            continue

        if (
            end
            and event_time
            and event_time > end
        ):
            continue

        searchable = " ".join(
            str(
                row.get(key, "")
            )
            for key in (
                "message",
                "event_type",
                "severity",
                "source",
                "component_id",
            )
        )

        row_tokens = _tokens(
            searchable
        )

        score = len(
            query_tokens
            & row_tokens
        )

        if query_tokens and score == 0:
            continue

        matches.append(
            (
                score,
                row,
            )
        )

    matches.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    results = [
        row
        for _, row
        in matches[:limit]
    ]

    return {
        "status": "completed",
        "row_count": len(results),
        "results": results,
    }