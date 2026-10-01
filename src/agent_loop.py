from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from src.agent import (
    ChangeProposal,
    ImpactReport,
    propose_change,
    generate_impact_report,
)
from src.verifier import DeterministicVerifier, VerificationResult
from src.lineage_engine import LineageEngine
from src.table_baseline import TableBaseline


class AgentExecutionResult(BaseModel):
    """Complete execution record of the autonomous data engineering agent."""
    user_request: str
    proposal: ChangeProposal
    derivation_blast: List[str]
    relational_blast: List[str]
    table_blast: List[str]
    verification_passed: bool
    verification_uncertain: bool = False
    verification_issues: List[str]
    verification_warnings: List[str]
    impact_report: ImpactReport


class AutonomousDataAgent:
    """
    Autonomous agent orchestrator connecting structured LLM change proposals,
    Ripple lineage analysis, deterministic rule verification, and audited impact reporting.
    """

    def __init__(self, schema: Dict[str, Any], queries: List[Dict[str, str]] | None = None):
        self.schema = schema
        self.lineage_engine = LineageEngine(schema=schema)
        self.table_baseline = TableBaseline(schema=schema)
        self.verifier = DeterministicVerifier(schema=schema)

        if queries:
            for q in queries:
                self.lineage_engine.add_query(q["sql"], q["target_table"])
                self.table_baseline.add_query(q["sql"], q["target_table"])

    def execute_change_request(
        self, 
        user_request: str, 
        schema_yaml_str: str, 
        model: str = "gemini-2.5-flash"
    ) -> AgentExecutionResult:
        proposal = propose_change(user_request, schema_yaml_str, model=model)

        target_node = f"table:{proposal.target_table}.{proposal.target_column}"

        derivation_set = self.lineage_engine.get_derivation_blast_radius(target_node)
        relational_set = self.lineage_engine.get_relational_blast_radius(target_node)
        table_set = self.table_baseline.get_blast_radius(target_node)

        v_result = self.verifier.verify(
            proposal=proposal,
            derivation_blast=derivation_set,
            relational_blast=relational_set,
            table_blast=table_set,
            unresolved_constructs=self.lineage_engine.unresolved_constructs,
        )

        derivation_list = sorted(list(derivation_set))
        table_list = sorted(list(table_set))

        report = generate_impact_report(
            proposal=proposal,
            derivation_blast=derivation_list,
            table_blast=table_list,
            verification_results=v_result.to_dict(),
            model=model,
        )

        return AgentExecutionResult(
            user_request=user_request,
            proposal=proposal,
            derivation_blast=derivation_list,
            relational_blast=sorted(list(relational_set)),
            table_blast=table_list,
            verification_passed=v_result.passed,
            verification_uncertain=v_result.uncertain,
            verification_issues=v_result.issues,
            verification_warnings=v_result.warnings,
            impact_report=report,
        )
