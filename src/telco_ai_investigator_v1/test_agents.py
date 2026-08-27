import json
from pathlib import Path

from telco_ai_investigator_v1.core.orchestrator import (
    Orchestrator,
)
from telco_ai_investigator_v1.core.registry import (
    RegistryManager,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


def main():

    registry = RegistryManager(
        PROJECT_ROOT
    )

    registry.load()

    orchestrator = Orchestrator(
        registry=registry,
        project_root=PROJECT_ROOT,
    )

    context = {
        "window_id": "WIN-001287",
    }

    print("\nEXECUTION PLAN\n")

    plan = orchestrator.execution_plan(
        context
    )

    print(
        json.dumps(
            plan,
            indent=2,
        )
    )

    print("\nRUNNING AGENTS\n")

    state = orchestrator.investigate(
        context
    )

    print(
        f"Investigation: "
        f"{state.investigation_id}"
    )

    print(
        f"Selected agents: "
        f"{state.selected_agents}"
    )

    print("\nRESULTS\n")

    for (
        agent_id,
        result,
    ) in state.agent_results.items():

        print(
            f"\n{'=' * 60}"
        )

        print(
            f"AGENT: {agent_id}"
        )

        print(
            f"STATUS: {result.status}"
        )

        print(
            f"TOOL CALLS: "
            f"{result.tool_calls_used}"
        )

        if result.error:

            print(
                f"ERROR: "
                f"{result.error}"
            )

            continue

        print("\nFindings:")

        for finding in (
            result.findings
        ):

            print(
                json.dumps(
                    finding,
                    indent=2,
                )
            )

        print("\nHypotheses:")

        for hypothesis in (
            result.hypotheses
        ):

            print(
                json.dumps(
                    hypothesis,
                    indent=2,
                )
            )

        print(
            "\nMissing evidence:"
        )

        for item in (
            result.missing_evidence
        ):

            print(
                f"- {item}"
            )


if __name__ == "__main__":
    main()