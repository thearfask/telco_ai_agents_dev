from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INTELLIGENCE_ROOT = (
    PROJECT_ROOT
    / "domain_intelligence"
)

METRIC_CATALOG_FILE = (
    INTELLIGENCE_ROOT
    / "metric_catalog.json"
)

DIAGNOSTIC_PATTERNS_FILE = (
    INTELLIGENCE_ROOT
    / "diagnostic_patterns.json"
)

RUNBOOK_ROOT = (
    INTELLIGENCE_ROOT
    / "runbooks"
)


def _normalize(
    value: str,
) -> str:

    return re.sub(
        r"[^a-z0-9]+",
        "_",
        value.lower(),
    ).strip("_")


def _tokens(
    value: str,
) -> set[str]:

    return {
        token
        for token
        in re.findall(
            r"[a-z0-9]+",
            value.lower(),
        )
        if len(token) > 1
    }


def _load_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing intelligence file: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        result = json.load(handle)

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            f"Expected JSON object: {path}"
        )

    return result


@lru_cache(maxsize=1)
def load_metric_catalog():
    return _load_json(
        METRIC_CATALOG_FILE
    )


@lru_cache(maxsize=1)
def load_patterns():
    return _load_json(
        DIAGNOSTIC_PATTERNS_FILE
    )


# ============================================================
# STRICT METRIC RESOLUTION
# ============================================================


def _metric_records() -> list[dict]:

    catalog = load_metric_catalog()

    records = []

    for (
        table_name,
        table_config,
    ) in catalog.get(
        "tables",
        {},
    ).items():

        for (
            metric_name,
            config,
        ) in table_config.get(
            "fields",
            {},
        ).items():

            if not isinstance(
                config,
                dict,
            ):
                continue

            records.append(
                {
                    "table": table_name,
                    "metric": metric_name,
                    **config,
                }
            )

    return records


def _requested_direction(
    concept: str,
) -> str | None:

    lowered = concept.lower()

    if (
        "uplink" in lowered
        or re.search(
            r"\bul[_\s]",
            lowered,
        )
    ):
        return "uplink"

    if (
        "downlink" in lowered
        or re.search(
            r"\bdl[_\s]",
            lowered,
        )
    ):
        return "downlink"

    return None


def resolve_metrics(
    concepts: list[str],
    max_results: int = 8,
) -> dict:

    records = _metric_records()

    resolved = []

    unresolved = []

    used = set()

    for request in concepts:

        request_norm = _normalize(
            request
        )

        request_tokens = _tokens(
            request
        )

        direction = (
            _requested_direction(
                request
            )
        )

        matches = []

        for record in records:

            record_direction = (
                record.get(
                    "direction"
                )
            )

            if (
                direction
                and record_direction
                and record_direction
                != direction
            ):
                continue

            metric = str(
                record.get(
                    "metric",
                    "",
                )
            )

            concept = str(
                record.get(
                    "concept",
                    "",
                )
            )

            metric_norm = _normalize(
                metric
            )

            concept_norm = _normalize(
                concept
            )

            score = 0
            match_type = None

            # Exact physical metric mentioned.
            if (
                metric_norm
                and metric_norm
                in request_norm
            ):
                score = 1000
                match_type = (
                    "exact_metric"
                )

            elif (
                concept_norm
                and concept_norm
                == request_norm
            ):
                score = 900
                match_type = (
                    "exact_concept"
                )

            else:

                searchable = " ".join(
                    [
                        metric,
                        concept,
                        str(
                            record.get(
                                "meaning",
                                "",
                            )
                        ),
                        " ".join(
                            record.get(
                                "supports",
                                [],
                            )
                        ),
                    ]
                )

                overlap = len(
                    request_tokens
                    & _tokens(
                        searchable
                    )
                )

                if overlap >= 2:
                    score = (
                        overlap * 50
                    )
                    match_type = (
                        "semantic_token_match"
                    )

            if score:

                # Prefer sample-level measurement fields
                # for time-resolved requests.
                if (
                    "time" in request.lower()
                    and record.get(
                        "table"
                    )
                    == "telemetry_measurements"
                ):
                    score += 50

                matches.append(
                    (
                        score,
                        match_type,
                        record,
                    )
                )

        matches.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        if not matches:
            unresolved.append(
                request
            )
            continue

        # One primary mapping per requested concept.
        score, match_type, record = (
            matches[0]
        )

        key = (
            record.get(
                "table"
            ),
            record.get(
                "metric"
            ),
        )

        if key in used:
            continue

        used.add(
            key
        )

        resolved.append(
            {
                "requested_concept": request,
                "match_type": match_type,
                "table": record.get(
                    "table"
                ),
                "metric": record.get(
                    "metric"
                ),
                "concept": record.get(
                    "concept"
                ),
                "unit": record.get(
                    "unit"
                ),
                "direction": record.get(
                    "direction"
                ),
                "meaning": record.get(
                    "meaning"
                ),
                "supports": record.get(
                    "supports",
                    [],
                )[:3],
                "does_not_prove": (
                    record.get(
                        "does_not_prove",
                        [],
                    )[:4]
                ),
                "caution": record.get(
                    "caution"
                ),
            }
        )

        if len(
            resolved
        ) >= max_results:
            break

    return {
        "status": (
            "completed"
            if resolved
            else "unresolved"
        ),
        "resolved_metrics": (
            resolved
        ),
        "unresolved_concepts": (
            unresolved
        ),
    }


# ============================================================
# DIAGNOSTIC PATTERNS
# ============================================================


def find_patterns(
    query: str,
    domain: str = "telemetry",
    top_k: int = 3,
) -> dict:

    catalog = load_patterns()

    query_tokens = _tokens(
        query
    )

    results = []

    for pattern in catalog.get(
        "patterns",
        [],
    ):

        if not isinstance(
            pattern,
            dict,
        ):
            continue

        pattern_domain = (
            pattern.get(
                "domain"
            )
            or catalog.get(
                "domain"
            )
        )

        if (
            pattern_domain
            and pattern_domain
            != domain
        ):
            continue

        searchable = json.dumps(
            {
                "id": pattern.get(
                    "hypothesis_id"
                ),
                "name": pattern.get(
                    "name"
                ),
                "description": pattern.get(
                    "description"
                ),
                "aliases": pattern.get(
                    "aliases",
                    [],
                ),
                "symptoms": pattern.get(
                    "applicable_symptoms",
                    [],
                ),
            }
        )

        overlap = len(
            query_tokens
            & _tokens(
                searchable
            )
        )

        if overlap == 0:
            continue

        results.append(
            {
                "score": overlap,
                "hypothesis_id": (
                    pattern.get(
                        "hypothesis_id"
                    )
                ),
                "name": pattern.get(
                    "name"
                ),
                "description": pattern.get(
                    "description"
                ),
                "supporting_evidence": (
                    pattern.get(
                        "supporting_evidence",
                        [],
                    )[:4]
                ),
                "contradicting_evidence": (
                    pattern.get(
                        "contradicting_evidence",
                        [],
                    )[:4]
                ),
                "data_limitations": (
                    pattern.get(
                        "data_limitations",
                        [],
                    )[:3]
                ),
            }
        )

    results.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    return {
        "status": (
            "completed"
            if results
            else "unresolved"
        ),
        "results": (
            results[:top_k]
        ),
    }


# ============================================================
# RUNBOOK SEARCH
# ============================================================


def search_runbooks(
    query: str,
    domain: str = "telemetry",
    top_k: int = 3,
) -> dict:

    directory = (
        RUNBOOK_ROOT
        / domain
    )

    if not directory.exists():

        return {
            "status": "unavailable",
            "results": [],
        }

    query_tokens = _tokens(
        query
    )

    hits = []

    for path in directory.glob(
        "*.md"
    ):

        text = path.read_text(
            encoding="utf-8"
        )

        score = len(
            query_tokens
            & _tokens(
                path.stem
                + " "
                + text
            )
        )

        if not score:
            continue

        # Deliberately small RAG-like chunk for now.
        hits.append(
            {
                "score": score,
                "source": path.name,
                "content": (
                    text[:2500]
                ),
            }
        )

    hits.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    return {
        "status": (
            "completed"
            if hits
            else "unresolved"
        ),
        "results": (
            hits[:top_k]
        ),
    }