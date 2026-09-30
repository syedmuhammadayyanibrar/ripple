import os
from enum import Enum
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

load_dotenv()


class ChangeType(str, Enum):
    RENAME = "RENAME"
    DROP = "DROP"
    ALTER_TYPE = "ALTER_TYPE"
    MODIFY_LOGIC = "MODIFY_LOGIC"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeProposal(BaseModel):
    target_table: str = Field(description="Table name being modified.")
    target_column: str = Field(description="Column name being modified, renamed, or dropped.")
    change_type: ChangeType = Field(description="Type of data model change.")
    old_value: Optional[str] = Field(default=None, description="Old column name, type, or expression.")
    new_value: Optional[str] = Field(default=None, description="New column name, type, or expression.")
    sql_statement: str = Field(description="Executable SQL migration statement.")
    intent_summary: str = Field(description="Short rationale for the proposed change.")


class ImpactReport(BaseModel):
    summary: str = Field(description="High-level summary of the proposed change and its consequences.")
    risk_level: RiskLevel = Field(description="Overall risk level assessment.")
    derivation_blast_radius: List[str] = Field(description="Downstream columns whose values are directly affected.")
    table_baseline_blast_radius: List[str] = Field(description="Downstream columns flagged by coarse table-level lineage.")
    verification_passed: bool = Field(description="Whether all deterministic verification checks passed.")
    verification_issues: List[str] = Field(description="List of detected verification failures or warnings.")
    recommended_action: str = Field(description="Recommended action: PROCEED, PROCEED_WITH_MIGRATION, or ABORT.")


def propose_change(
    user_request: str, 
    schema_yaml: str, 
    model: str = "gemini-2.5-flash",
    client: Optional[genai.Client] = None
) -> ChangeProposal:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not client:
        if not api_key:
            return _mock_propose_change(user_request, schema_yaml)
        client = genai.Client(api_key=api_key)

    prompt = f"""You are an autonomous data platform engineering agent.
Given the existing database schema catalog and a natural-language request from a data team, 
propose a concrete, single SQL change.

DATABASE CATALOG SCHEMA:
{schema_yaml}

USER REQUEST:
{user_request}

Analyze the request, map it to the catalog tables and columns, and output the structured change proposal.
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ChangeProposal,
            "temperature": 0.0,
        },
    )

    return ChangeProposal.model_validate_json(response.text)


def generate_impact_report(
    proposal: ChangeProposal,
    derivation_blast: List[str],
    table_blast: List[str],
    verification_results: Dict[str, Any],
    model: str = "gemini-2.5-flash",
    client: Optional[genai.Client] = None
) -> ImpactReport:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not client:
        if not api_key:
            return _mock_generate_impact_report(proposal, derivation_blast, table_blast, verification_results)
        client = genai.Client(api_key=api_key)

    prompt = f"""You are an autonomous data governance reviewer.
Review this proposed data-model change, its lineage blast radius, and deterministic verification results.

PROPOSED CHANGE:
- Target Table: {proposal.target_table}
- Target Column: {proposal.target_column}
- Change Type: {proposal.change_type.value}
- SQL: {proposal.sql_statement}
- Intent: {proposal.intent_summary}

LINEAGE IMPACT:
- Column-Level Derivation Blast Radius: {derivation_blast}
- Table-Level Baseline Blast Radius: {table_blast}

DETERMINISTIC VERIFICATION CHECKS:
- Passed: {verification_results.get('passed', True)}
- Issues Found: {verification_results.get('issues', [])}

Produce a formal, transparent ImpactReport. Never hide verification failures or claim a breaking change is safe.
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ImpactReport,
            "temperature": 0.0,
        },
    )

    return ImpactReport.model_validate_json(response.text)


def _mock_propose_change(user_request: str, schema_yaml: str) -> ChangeProposal:
    req_lower = user_request.lower()
    
    if "email" in req_lower and ("remove" in req_lower or "drop" in req_lower or "privacy" in req_lower):
        return ChangeProposal(
            target_table="raw_users",
            target_column="email",
            change_type=ChangeType.DROP,
            old_value="string",
            new_value=None,
            sql_statement="ALTER TABLE raw_users DROP COLUMN email;",
            intent_summary="Remove customer email field per privacy compliance."
        )
    elif "discount" in req_lower and ("rename" in req_lower or "discount_pct" in req_lower or "percentage" in req_lower):
        return ChangeProposal(
            target_table="raw_orders",
            target_column="discount",
            change_type=ChangeType.RENAME,
            old_value="discount",
            new_value="discount_pct",
            sql_statement="ALTER TABLE raw_orders RENAME COLUMN discount TO discount_pct;",
            intent_summary="Rename discount to discount_pct for clarity."
        )
    elif "cost" in req_lower:
        return ChangeProposal(
            target_table="raw_products",
            target_column="cost",
            change_type=ChangeType.ALTER_TYPE,
            old_value="float",
            new_value="string",
            sql_statement="ALTER TABLE raw_products ALTER COLUMN cost TYPE VARCHAR;",
            intent_summary="Convert cost representation."
        )
    elif "status" in req_lower:
        return ChangeProposal(
            target_table="raw_orders",
            target_column="status",
            change_type=ChangeType.MODIFY_LOGIC,
            old_value="string",
            new_value="string",
            sql_statement="UPDATE raw_orders SET status = lower(status);",
            intent_summary="Normalize status casing."
        )
    elif "amount" in req_lower:
        return ChangeProposal(
            target_table="raw_orders",
            target_column="amount",
            change_type=ChangeType.ALTER_TYPE,
            old_value="float",
            new_value="string",
            sql_statement="ALTER TABLE raw_orders ALTER COLUMN amount TYPE VARCHAR;",
            intent_summary="Modify amount data type."
        )
    elif "manager_id" in req_lower:
        return ChangeProposal(
            target_table="employees",
            target_column="manager_id",
            change_type=ChangeType.RENAME,
            old_value="manager_id",
            new_value="supervisor_id",
            sql_statement="ALTER TABLE employees RENAME COLUMN manager_id TO supervisor_id;",
            intent_summary="Rename manager_id column."
        )
    else:
        return ChangeProposal(
            target_table="raw_orders",
            target_column="amount",
            change_type=ChangeType.RENAME,
            old_value="amount",
            new_value="total_amount",
            sql_statement="ALTER TABLE raw_orders RENAME COLUMN amount TO total_amount;",
            intent_summary="Standardizing column naming."
        )


def _mock_generate_impact_report(
    proposal: ChangeProposal,
    derivation_blast: List[str],
    table_blast: List[str],
    verification_results: Dict[str, Any]
) -> ImpactReport:
    issues = verification_results.get("issues", [])
    passed = verification_results.get("passed", True)

    if not passed or len(derivation_blast) > 2:
        risk = RiskLevel.CRITICAL if not passed else RiskLevel.HIGH
        action = "ABORT" if not passed else "PROCEED_WITH_MIGRATION"
    elif len(derivation_blast) > 0:
        risk = RiskLevel.MEDIUM
        action = "PROCEED_WITH_MIGRATION"
    else:
        risk = RiskLevel.LOW
        action = "PROCEED"

    summary = (
        f"Proposal to {proposal.change_type.value} column '{proposal.target_column}' in table "
        f"'{proposal.target_table}'. Affects {len(derivation_blast)} downstream columns."
    )

    return ImpactReport(
        summary=summary,
        risk_level=risk,
        derivation_blast_radius=derivation_blast,
        table_baseline_blast_radius=table_blast,
        verification_passed=passed,
        verification_issues=issues,
        recommended_action=action
    )
