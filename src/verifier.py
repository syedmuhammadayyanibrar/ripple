from typing import Set, Dict, Any, List, Optional
from src.agent import ChangeProposal, ChangeType


class VerificationResult:
    """Holds verification outcome: pass/fail status, uncertainty flags, issues, and warnings."""

    def __init__(self):
        self.passed: bool = True
        self.uncertain: bool = False
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.details: Dict[str, Any] = {}

    def add_failure(self, issue: str):
        self.passed = False
        self.issues.append(issue)

    def add_uncertainty(self, reason: str):
        self.uncertain = True
        self.passed = False
        self.issues.append(f"UNCERTAINTY_FLAGGED: {reason}")

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "uncertain": self.uncertain,
            "issues": self.issues,
            "warnings": self.warnings,
            "details": self.details,
        }


class DeterministicVerifier:
    """
    Rule-based verification engine enforcing safety constraints on top of graph blast radiuses.
    Implements ternary verification states: PASS (Safe), FAIL (Breaking), and UNCERTAIN (Audit Required).
    """

    def __init__(self, schema: Dict[str, Any] | None = None):
        self.schema = schema or {}

    def verify(
        self,
        proposal: ChangeProposal,
        derivation_blast: Set[str],
        relational_blast: Set[str],
        table_blast: Set[str],
        unresolved_constructs: Optional[Dict[str, List[str]]] = None,
    ) -> VerificationResult:
        result = VerificationResult()
        unresolved = unresolved_constructs or {}
        
        result.details["derivation_count"] = len(derivation_blast)
        result.details["relational_count"] = len(relational_blast)
        result.details["table_count"] = len(table_blast)

        if len(derivation_blast) == 0 and unresolved:
            construct_list = [f"{tbl}: {', '.join(c)}" for tbl, c in unresolved.items()]
            result.add_uncertainty(
                f"Absence of detected blast radius cannot be certified as safe. "
                f"Pipeline contains complex constructs with known lineage resolution limitations: {construct_list}. "
                f"MANUAL_AUDIT_REQUIRED."
            )
            return result

        if proposal.change_type == ChangeType.DROP:
            if len(derivation_blast) > 0:
                result.add_failure(
                    f"Destructive DROP blocked: Column '{proposal.target_column}' is referenced by "
                    f"{len(derivation_blast)} downstream columns: {sorted(list(derivation_blast))}."
                )
            else:
                result.details["drop_safe"] = True

        if proposal.change_type == ChangeType.RENAME:
            if len(derivation_blast) > 0:
                result.add_failure(
                    f"Breaking RENAME detected: Renaming '{proposal.target_column}' to '{proposal.new_value}' "
                    f"breaks {len(derivation_blast)} downstream dependencies without synchronized migration: "
                    f"{sorted(list(derivation_blast))}."
                )

        if proposal.change_type == ChangeType.ALTER_TYPE:
            old_type = (proposal.old_value or "").lower()
            new_type = (proposal.new_value or "").lower()
            
            numeric_types = {"int", "integer", "float", "double", "decimal", "numeric"}
            string_types = {"string", "varchar", "text", "char"}
            
            if old_type in numeric_types and any(st in new_type for st in string_types):
                if len(derivation_blast) > 0:
                    result.add_failure(
                        f"Incompatible Type Cast: Converting numeric column '{proposal.target_column}' "
                        f"({old_type}) to string ({new_type}) invalidates downstream arithmetic/aggregation "
                        f"in {len(derivation_blast)} columns: {sorted(list(derivation_blast))}."
                    )

        if len(relational_blast) > 0:
            result.add_warning(
                f"Relational Control Shift: Modifying '{proposal.target_column}' impacts row filtering, "
                f"join matching, or grouping across {len(relational_blast)} downstream relations: "
                f"{sorted(list(relational_blast))}."
            )

        if len(table_blast) > len(derivation_blast):
            inflation_diff = len(table_blast) - len(derivation_blast)
            result.details["table_false_alarms"] = inflation_diff

        return result
