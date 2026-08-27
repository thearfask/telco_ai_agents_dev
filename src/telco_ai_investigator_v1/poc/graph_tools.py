from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from pathlib import Path


TOPOLOGY_FILE = os.getenv(
    "POC_TOPOLOGY_FILE",
    "data/topology_edges.jsonl",
)


def _load_edges() -> list[dict]:

    path = Path(
        TOPOLOGY_FILE
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


def query_graph_raw(
    node_ids: list[str],
    max_hops: int = 2,
) -> dict:

    edges = _load_edges()

    if not edges:

        return {
            "status": "unavailable",
            "reason": (
                f"No topology graph found at {TOPOLOGY_FILE}"
            ),
            "results": [],
        }

    max_hops = max(
        1,
        min(
            int(max_hops),
            3,
        ),
    )

    graph = defaultdict(
        list
    )

    for edge in edges:

        src = str(
            edge.get("src", "")
        )

        dst = str(
            edge.get("dst", "")
        )

        relation = str(
            edge.get(
                "relation",
                "connected_to",
            )
        )

        if not src or not dst:
            continue

        graph[src].append(
            (
                dst,
                relation,
            )
        )

        graph[dst].append(
            (
                src,
                relation,
            )
        )

    queue = deque()

    visited = set()

    for node in node_ids:

        queue.append(
            (
                node,
                0,
            )
        )

        visited.add(
            node
        )

    results = []

    while queue:

        node, depth = queue.popleft()

        if depth >= max_hops:
            continue

        for neighbor, relation in graph.get(
            node,
            [],
        ):

            results.append(
                {
                    "from": node,
                    "relation": relation,
                    "to": neighbor,
                    "hop": depth + 1,
                }
            )

            if neighbor not in visited:

                visited.add(
                    neighbor
                )

                queue.append(
                    (
                        neighbor,
                        depth + 1,
                    )
                )

    return {
        "status": "completed",
        "results": results[:30],
    }