from pathlib import Path

import streamlit as st
import yaml

from telco_ai_investigator_v1.core.registry import (
    RegistryManager,
)
from telco_ai_investigator_v1.core.orchestrator import (
    Orchestrator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_DIR = (
    PROJECT_ROOT
    / "src"
    / "telco_ai_investigator_v1"
)

AGENTS_FILE = (
    PACKAGE_DIR
    / "config"
    / "agents.yaml"
)


st.set_page_config(
    page_title="Agent Framework Admin",
    page_icon="🧠",
    layout="wide",
)


def load_registry():

    registry = RegistryManager(
        PROJECT_ROOT
    )

    registry.load()

    return registry


def update_agent_enabled(
    agent_id: str,
    enabled: bool,
):

    config = yaml.safe_load(
        AGENTS_FILE.read_text()
    )

    config[
        "agents"
    ][
        agent_id
    ][
        "enabled"
    ] = enabled

    AGENTS_FILE.write_text(
        yaml.safe_dump(
            config,
            sort_keys=False,
        )
    )


registry = load_registry()

summary = registry.summary()

orchestrator = Orchestrator(
    registry
)


st.title("Investigation Framework Admin")

tabs = st.tabs(
    [
        "Overview",
        "Agents",
        "Tools",
        "Flow",
    ]
)


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------

with tabs[0]:

    col1, col2, col3, col4 = st.columns(
        4
    )

    col1.metric(
        "Registered Agents",
        summary.registered_agents,
    )

    col2.metric(
        "Enabled Agents",
        summary.enabled_agents,
    )

    col3.metric(
        "In Service",
        summary.in_service_agents,
    )

    col4.metric(
        "Registered Tools",
        summary.registered_tools,
    )

    st.subheader("Agent Health")

    for agent in registry.agents.agents.values():

        if agent.in_service:
            status = "🟢 IN SERVICE"

        elif not agent.enabled:
            status = "⚪ DISABLED"

        else:
            status = "🔴 DEGRADED"

        st.write(
            f"**{agent.name}** — "
            f"{status} — "
            f"{agent.health_message}"
        )


# ---------------------------------------------------------
# AGENTS
# ---------------------------------------------------------

with tabs[1]:

    st.subheader("Registered Agents")

    for agent in registry.agents.agents.values():

        with st.expander(
            f"{agent.name} ({agent.agent_id})"
        ):

            left, right = st.columns(
                [2, 1]
            )

            with left:

                st.write(
                    f"**Version:** {agent.version}"
                )

                st.write(
                    f"**Prompt:** "
                    f"{agent.prompt_file}"
                )

                st.write(
                    "**Tools:**"
                )

                for tool_id in agent.tools:
                    st.write(
                        f"- `{tool_id}`"
                    )

                st.write(
                    "**Required context:**"
                )

                for item in agent.required_context:
                    st.write(
                        f"- `{item}`"
                    )

            with right:

                enabled = st.toggle(
                    "Enabled",
                    value=agent.enabled,
                    key=(
                        f"enabled_"
                        f"{agent.agent_id}"
                    ),
                )

                if enabled != agent.enabled:

                    update_agent_enabled(
                        agent.agent_id,
                        enabled,
                    )

                    st.rerun()

                st.metric(
                    "Max Tool Calls",
                    agent.max_tool_calls,
                )

                st.metric(
                    "Input Token Budget",
                    agent.max_input_tokens,
                )

                st.metric(
                    "Output Token Budget",
                    agent.max_output_tokens,
                )

                if agent.in_service:
                    st.success(
                        "IN SERVICE"
                    )

                elif not agent.enabled:
                    st.info(
                        "DISABLED"
                    )

                else:
                    st.error(
                        agent.health_message
                    )


# ---------------------------------------------------------
# TOOLS
# ---------------------------------------------------------

with tabs[2]:

    st.subheader("Tool Registry")

    for tool in registry.tools.tools.values():

        used_by = [
            agent.agent_id
            for agent
            in registry.agents.agents.values()
            if tool.tool_id in agent.tools
        ]

        with st.expander(
            f"{tool.name} ({tool.tool_id})"
        ):

            st.write(
                f"**Category:** "
                f"{tool.category}"
            )

            st.write(
                f"**Version:** "
                f"{tool.version}"
            )

            st.write(
                f"**Implementation:** "
                f"`{tool.implementation}`"
            )

            st.write(
                f"**Scope:** "
                f"`{tool.required_scope or 'None'}`"
            )

            st.write(
                "**Used by:** "
                + (
                    ", ".join(used_by)
                    if used_by
                    else "None"
                )
            )

            st.write(
                "**Tags:** "
                + ", ".join(tool.tags)
            )

            if tool.healthy:
                st.success(
                    "HEALTHY"
                )
            else:
                st.error(
                    tool.health_message
                )


# ---------------------------------------------------------
# FLOW
# ---------------------------------------------------------

with tabs[3]:

    st.subheader(
        "Current Investigation Flow"
    )

    context = {
        "window_id": "example"
    }

    selected = (
        orchestrator.select_agents(
            context
        )
    )

    lines = [
        "digraph G {",
        'rankdir="TB";',
        'node [shape=box];',
        '"Incident" -> "Orchestrator";',
    ]

    for agent in selected:

        lines.append(
            f'"Orchestrator" -> '
            f'"{agent.name}";'
        )

        lines.append(
            f'"{agent.name}" -> "RCA Agent";'
        )

    lines.extend(
        [
            '"RCA Agent" -> "Validator";',
            '"Validator" -> "Final Findings";',
            "}",
        ]
    )

    st.graphviz_chart(
        "\n".join(lines),
        use_container_width=True,
    )