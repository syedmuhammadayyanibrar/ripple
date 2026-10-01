import argparse
import copy
from typing import Dict, Any, List
import yaml

from src.agent_loop import AutonomousDataAgent
from src.agent import RiskLevel
from src.metrics import calculate_metrics


def load_yaml(file_path: str) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_agent_evaluation(
    eval_cases_path: str = "data/agent_eval_cases.yaml",
    schema_path: str = "data/schema.yaml"
):
    schema = load_yaml(schema_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_yaml_str = f.read()

    test_cases = load_yaml(eval_cases_path)

    print(f"\n{'='*105}")
    print(f"AUTONOMOUS AGENT RELIABILITY BENCHMARK: {eval_cases_path} ({len(test_cases)} Scenarios)")
    print(f"{'='*105}")
    print(
        f"{'Case ID':<36} | {'Type':<11} | {'True Blast':<10} | {'Agent Blast':<11} | {'Agent Risk':<10} | {'Action':<22} | {'Status'}"
    )
    print(f"{'-'*36}-+-{'-'*11}-+-{'-'*10}-+-{'-'*11}-+-{'-'*10}-+-{'-'*22}-+-{'-'*10}")

    total_standard = 0
    correct_standard = 0
    total_adversarial = 0
    correct_adversarial = 0
    false_confidence_count = 0
    uncertain_audit_count = 0

    for tc in test_cases:
        tc_id = tc["id"]
        category = tc["category"]
        user_request = tc["user_request"]
        pipeline_queries = tc["pipeline_queries"]
        true_blast = set(tc.get("true_blast_radius", []))
        expected_verdict = tc["expected_verdict"]

        agent = AutonomousDataAgent(schema=copy.deepcopy(schema), queries=pipeline_queries)
        result = agent.execute_change_request(
            user_request=user_request,
            schema_yaml_str=schema_yaml_str
        )

        agent_blast = set(result.derivation_blast)
        agent_risk = result.impact_report.risk_level.value
        agent_action = result.impact_report.recommended_action

        blast_matches = (agent_blast == true_blast)

        is_breaking = len(true_blast) > 0
        is_falsely_confident = is_breaking and (
            result.verification_passed is True and
            result.impact_report.risk_level == RiskLevel.LOW and
            result.impact_report.recommended_action == "PROCEED"
        )

        if is_falsely_confident:
            false_confidence_count += 1
            status = "FALSE_CONFIDENCE"
        elif result.verification_uncertain or agent_action == "MANUAL_AUDIT_REQUIRED":
            uncertain_audit_count += 1
            status = "AUDIT_FLAGGED"
        elif blast_matches:
            status = "EXACT_MATCH"
        else:
            status = "NOISY_OVERPRED"

        if category == "standard":
            total_standard += 1
            if status == "EXACT_MATCH":
                correct_standard += 1
        else:
            total_adversarial += 1
            if status in ["EXACT_MATCH", "AUDIT_FLAGGED"]:
                correct_adversarial += 1

        print(
            f"{tc_id:<36} | {category:<11} | {len(true_blast):<10} | {len(agent_blast):<11} | {agent_risk:<10} | {agent_action:<22} | {status}"
        )

    std_acc = (correct_standard / total_standard * 100) if total_standard else 0.0
    adv_safe_acc = (correct_adversarial / total_adversarial * 100) if total_adversarial else 0.0
    overall_safe_acc = ((correct_standard + correct_adversarial) / len(test_cases) * 100) if test_cases else 0.0
    false_conf_pct = (false_confidence_count / len(test_cases) * 100) if test_cases else 0.0

    print(f"{'='*105}")
    print("AGENT RELIABILITY & TRUST ASSESSMENT (POST-TERNARY FIX)")
    print(f"{'='*105}")
    print(f"{'Metric':<45} | {'Value':<15}")
    print(f"{'-'*45}-+-{'-'*15}")
    print(f"{'Standard SQL Reliability':<45} | {std_acc:<14.1f}%")
    print(f"{'Adversarial SQL Safe Handling':<45} | {adv_safe_acc:<14.1f}%")
    print(f"{'Overall Safe Decision Rate':<45} | {overall_safe_acc:<14.1f}%")
    print(f"{'False Confidence Failure Rate':<45} | {false_conf_pct:<14.1f}%")
    print(f"{'Uncertainty / Manual Audits Flagged':<45} | {uncertain_audit_count:<14}")
    print(f"{'='*105}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/agent_eval_cases.yaml")
    args = parser.parse_args()
    run_agent_evaluation(args.dataset)
