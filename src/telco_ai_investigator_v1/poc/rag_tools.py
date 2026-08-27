from __future__ import annotations

import math
import os
import re
from pathlib import Path


# ============================================================
# BUILT-IN POC KNOWLEDGE
# ============================================================


DEFAULT_DOCUMENTS = [
    {
        "source": "radio_kpi_guide",
        "section": "RSRP",
        "text": """
RSRP represents received reference-signal power.

Values around -70 to -80 dBm generally represent strong received
signal conditions. Around -90 to -100 dBm is weaker but may remain
usable depending on system context. Values below roughly -110 dBm
indicate poor received signal conditions.

RSRP is an observation of received signal strength. RSRP alone
cannot determine why signal strength is poor. Potential mechanisms
require other evidence such as topology, interference indicators,
hardware status, mobility, configuration, or environmental factors.
""",
    },
    {
        "source": "radio_kpi_guide",
        "section": "BLER",
        "text": """
BLER measures block decoding failure rate.

Elevated BLER indicates degraded transmission reliability.
BLER is an impairment indicator and should not itself be reported
as the physical root cause.

Downlink and uplink BLER should be interpreted separately.
Persistence claims require distributional, threshold-frequency,
or temporal evidence rather than only average and maximum values.
""",
    },
    {
        "source": "capacity_guide",
        "section": "PRB utilization",
        "text": """
PRB utilization represents radio resource usage.

Relative differences between two PRB values do not establish
congestion. Congestion or saturation requires high absolute resource
utilization or corroborating evidence such as scheduling pressure,
queue growth, admission limitations, throughput collapse, or other
capacity indicators.

Low absolute PRB utilization argues against resource saturation as
the dominant cause of degradation.
""",
    },
    {
        "source": "radio_kpi_guide",
        "section": "MCS",
        "text": """
MCS describes modulation and coding selection.

Low or decreasing MCS can reflect conservative link adaptation or
degraded channel conditions. MCS alone cannot identify the physical
reason for degradation.

Correlation between MCS and BLER should be interpreted cautiously.
Correlation does not prove causation, and comparisons should use
appropriate baselines or distributions.
""",
    },
    {
        "source": "radio_kpi_guide",
        "section": "SNR",
        "text": """
SNR represents signal quality relative to noise.

Low SNR may support degraded RF quality. Healthy average SNR does
not prove that all interference mechanisms are absent because short
bursts or other effects may not be represented by an aggregate.

Temporal claims require appropriately granular evidence.
""",
    },
    {
        "source": "investigation_principles",
        "section": "Evidence discipline",
        "text": """
Separate observation, domain interpretation, hypothesis, and root
cause.

Observation is directly measured or logged evidence.
Domain interpretation explains what the observation means.
A hypothesis is a plausible explanation.
Root cause should only be stated when evidence sufficiently
distinguishes it from alternatives.

Never infer causality from correlation alone.
Never claim persistence, intermittency, periodicity, or burstiness
from AVG/MIN/MAX alone.
""",
    },
    {
        "source": "investigation_principles",
        "section": "Cross-domain RCA",
        "text": """
Operational measurements establish what happened.

Engineering knowledge and historical cases can suggest which
hypotheses are plausible, but retrieved knowledge does not prove
that the same root cause applies to the current incident.

Alarm evidence, topology relationships, logs, telemetry and
configuration should be correlated before claiming a physical cause.
""",
    },
]


# ============================================================
# DOCUMENT LOADING
# ============================================================


def _external_documents() -> list[dict]:

    root = Path(
        os.getenv(
            "POC_KNOWLEDGE_DIR",
            "knowledge",
        )
    )

    if not root.exists():
        return []

    documents = []

    for path in root.rglob("*.md"):

        try:
            text = path.read_text(
                encoding="utf-8"
            )
        except Exception:
            continue

        # Keep chunks deliberately simple for the POC.
        chunks = re.split(
            r"\n(?=#{1,3}\s)",
            text,
        )

        for index, chunk in enumerate(chunks):

            chunk = chunk.strip()

            if not chunk:
                continue

            documents.append(
                {
                    "source": str(path),
                    "section": f"chunk-{index + 1}",
                    "text": chunk[:5000],
                }
            )

    return documents


def _documents() -> list[dict]:

    return (
        DEFAULT_DOCUMENTS
        + _external_documents()
    )


# ============================================================
# SIMPLE LOCAL RETRIEVER
#
# Later replace only this function with Databricks Vector Search.
# ============================================================


def _tokens(
    text: str,
) -> list[str]:

    return re.findall(
        r"[a-z0-9_]+",
        text.lower(),
    )


def search_knowledge_raw(
    query: str,
    top_k: int = 4,
) -> dict:

    docs = _documents()

    if not docs:

        return {
            "status": "unavailable",
            "reason": "Knowledge base is empty.",
            "results": [],
        }

    top_k = max(
        1,
        min(
            int(top_k),
            6,
        ),
    )

    query_tokens = set(
        _tokens(query)
    )

    if not query_tokens:

        return {
            "status": "completed",
            "results": [],
        }

    document_tokens = [
        set(
            _tokens(
                doc["text"]
            )
        )
        for doc in docs
    ]

    # Small IDF-style weighting.
    idf = {}

    for token in query_tokens:

        count = sum(
            token in tokens
            for tokens in document_tokens
        )

        idf[token] = math.log(
            (len(docs) + 1)
            / (count + 1)
        ) + 1.0

    scored = []

    for doc, tokens in zip(
        docs,
        document_tokens,
    ):

        overlap = (
            query_tokens
            & tokens
        )

        score = sum(
            idf[token]
            for token in overlap
        )

        if score <= 0:
            continue

        scored.append(
            (
                score,
                doc,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    results = []

    for score, doc in scored[:top_k]:

        results.append(
            {
                "source": doc["source"],
                "section": doc["section"],
                "score": round(
                    float(score),
                    4,
                ),
                "content": doc["text"][:1800],
            }
        )

    return {
        "status": "completed",
        "results": results,
    }