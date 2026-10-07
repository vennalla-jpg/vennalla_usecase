"""Engineering lab agent registry.

This module captures the agent and workflow contract described in
``Accelerate with AI_Engineering Lab Session.pptx``. It gives demos, tests, and
readiness checks one small place to verify that the codebase still exposes the
agents, entry points, tools, and handoffs expected by the lab deck.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Iterable


@dataclass(frozen=True)
class AgentContract:
    """A lab-deck agent mapped to its implementation contract."""

    name: str
    module: str
    purpose: str
    entry_points: tuple[str, ...]
    tools: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowPhase:
    """A human-in-the-loop pipeline phase from the lab deck."""

    phase: str
    supervisor_entry_point: str
    agents: tuple[str, ...]
    produces: tuple[str, ...]
    approval_gate: str | None = None


LAB_AGENTS: tuple[AgentContract, ...] = (
    AgentContract(
        name="Supervisor Agent",
        module="agents.orchestrator",
        purpose="Plans each phase, dispatches specialist agents, verifies outputs, and updates PipelineState.",
        entry_points=(
            "run_until_bronze_sttm",
            "run_bronze_to_silver_sttm",
            "run_silver_to_gold_sttm",
            "run_gold_and_report",
        ),
        tools=("profiler_agent_tool", "sttm_agent_tool", "bronze_agent_tool", "silver_agent_tool", "gold_agent_tool", "reporter_agent_tool"),
    ),
    AgentContract(
        name="Data Profiler Agent",
        module="agents.profiler",
        purpose="Profiles raw CSV files and produces machine-readable structure, semantic, join-key, and quality notes.",
        entry_points=("profile_dataset", "profile_multiple_datasets"),
        tools=("inspect_files_tool", "profiler_tool"),
    ),
    AgentContract(
        name="STTM Agent",
        module="agents.sttm_generator",
        purpose="Generates Bronze, Silver, and Gold source-to-target mappings from the current pipeline context.",
        entry_points=("generate_bronze_sttm", "generate_silver_sttm", "generate_gold_sttm"),
        tools=("inspect_context_tool", "generate_bronze_sttm_tool", "generate_silver_sttm_tool", "generate_gold_sttm_tool"),
    ),
    AgentContract(
        name="Bronze Agent",
        module="agents.bronze_agent",
        purpose="Executes approved Bronze STTM rules and lands raw CSV data as Bronze Parquet files.",
        entry_points=("execute_bronze",),
        tools=("inspect_task_tool", "bronze_ingestion_tool"),
    ),
    AgentContract(
        name="Silver Agent",
        module="agents.silver_agent",
        purpose="Executes approved Silver STTM rules for cleansing, typing, deduplication, and surrogate keys.",
        entry_points=("execute_silver",),
        tools=("inspect_task_tool", "silver_ingestion_tool"),
    ),
    AgentContract(
        name="Gold Agent",
        module="agents.gold_agent",
        purpose="Executes approved Gold STTM rules to materialise analytics-ready Gold Parquet tables.",
        entry_points=("execute_gold",),
        tools=("inspect_task_tool", "gold_ingestion_tool"),
    ),
    AgentContract(
        name="Reporter Agent",
        module="agents.reporter",
        purpose="Analyzes Gold tables with SQL and renders an executive HTML report answering the business question.",
        entry_points=("generate_report",),
        tools=("inspect_gold_tables_tool", "load_gold_data_tool", "execute_query_tool"),
    ),
)


WORKFLOW_PHASES: tuple[WorkflowPhase, ...] = (
    WorkflowPhase(
        phase="Phase 1 - Profile and Bronze STTM",
        supervisor_entry_point="run_until_bronze_sttm",
        agents=("Data Profiler Agent", "STTM Agent"),
        produces=("profile_path", "sttm_bronze_path"),
        approval_gate="bronze_sttm_approved",
    ),
    WorkflowPhase(
        phase="Phase 2 - Bronze Execution and Silver STTM",
        supervisor_entry_point="run_bronze_to_silver_sttm",
        agents=("Bronze Agent", "STTM Agent"),
        produces=("bronze_output_paths", "sttm_silver_path"),
        approval_gate="silver_sttm_approved",
    ),
    WorkflowPhase(
        phase="Phase 3 - Silver Execution and Gold STTM",
        supervisor_entry_point="run_silver_to_gold_sttm",
        agents=("Silver Agent", "STTM Agent"),
        produces=("silver_output_paths", "sttm_gold_path"),
        approval_gate="gold_sttm_approved",
    ),
    WorkflowPhase(
        phase="Phase 4 - Gold Execution and Report",
        supervisor_entry_point="run_gold_and_report",
        agents=("Gold Agent", "Reporter Agent"),
        produces=("gold_output_paths", "report_path"),
    ),
)


def get_agent_contract(name: str) -> AgentContract:
    """Return an agent contract by display name."""
    for contract in LAB_AGENTS:
        if contract.name == name:
            return contract
    raise KeyError(f"Unknown lab agent: {name}")


def validate_lab_contracts(contracts: Iterable[AgentContract] = LAB_AGENTS) -> list[str]:
    """Return missing module or entry-point problems for the lab registry."""
    problems: list[str] = []
    for contract in contracts:
        try:
            module = import_module(contract.module)
        except Exception as exc:
            problems.append(f"{contract.name}: cannot import {contract.module}: {exc}")
            continue
        for entry_point in contract.entry_points:
            if not callable(getattr(module, entry_point, None)):
                problems.append(f"{contract.name}: missing callable {contract.module}.{entry_point}")
    return problems