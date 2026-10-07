import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.lab_registry import LAB_AGENTS, WORKFLOW_PHASES, get_agent_contract, validate_lab_contracts


def test_lab_registry_contains_deck_agents():
    assert [agent.name for agent in LAB_AGENTS] == [
        "Supervisor Agent",
        "Data Profiler Agent",
        "STTM Agent",
        "Bronze Agent",
        "Silver Agent",
        "Gold Agent",
        "Reporter Agent",
    ]


def test_lab_registry_entry_points_import_cleanly():
    assert validate_lab_contracts() == []


def test_workflow_phases_match_human_approval_gates():
    assert [phase.supervisor_entry_point for phase in WORKFLOW_PHASES] == [
        "run_until_bronze_sttm",
        "run_bronze_to_silver_sttm",
        "run_silver_to_gold_sttm",
        "run_gold_and_report",
    ]
    assert [phase.approval_gate for phase in WORKFLOW_PHASES] == [
        "bronze_sttm_approved",
        "silver_sttm_approved",
        "gold_sttm_approved",
        None,
    ]


def test_get_agent_contract_returns_tooling_details():
    reporter = get_agent_contract("Reporter Agent")

    assert reporter.module == "agents.reporter"
    assert "execute_query_tool" in reporter.tools
    assert reporter.entry_points == ("generate_report",)