"""Command-line entrypoint for the BP BA analysis agent POC."""

from __future__ import annotations

import argparse
import json

from .agent import BPBAAnalysisAgent
from .analysis_topics import get_analysis_topic, list_analysis_topics, recommend_topics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a BP BA analysis workflow case.")
    parser.add_argument("business_question", nargs="?", help="业务问题，例如：分析媒体投流转化下降原因")
    parser.add_argument("--scenario", choices=["media", "model_conversion", "dealer_operation", "target_steering"])
    parser.add_argument("--purpose", dest="analysis_purpose")
    parser.add_argument("--target-object")
    parser.add_argument("--time-range")
    parser.add_argument("--dimension", action="append", default=[])
    parser.add_argument(
        "--deliverable-type",
        default="management_report",
        choices=["management_report", "data_validation", "target_steering"],
    )
    parser.add_argument("--audience", default="Sales BP / BI stakeholders")
    parser.add_argument("--json", action="store_true", help="Output full Analysis Case JSON.")
    parser.add_argument("--list-topics", action="store_true", help="List available BP BA analysis topics.")
    parser.add_argument("--topic", help="Show one analysis topic by key.")
    parser.add_argument("--recommend-topics", action="store_true", help="Recommend topics for the business question.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.list_topics:
        print(json.dumps(list_analysis_topics(), ensure_ascii=False, indent=2))
        return
    if args.topic:
        print(json.dumps(get_analysis_topic(args.topic).to_dict(), ensure_ascii=False, indent=2))
        return
    if args.recommend_topics:
        if not args.business_question:
            raise SystemExit("--recommend-topics requires a business_question")
        print(json.dumps([topic.to_dict() for topic in recommend_topics(args.business_question)], ensure_ascii=False, indent=2))
        return
    if not args.business_question:
        raise SystemExit("business_question is required unless --list-topics or --topic is used")
    agent = BPBAAnalysisAgent()
    case = agent.run(
        args.business_question,
        scenario=args.scenario,
        analysis_purpose=args.analysis_purpose,
        target_object=args.target_object,
        time_range=args.time_range,
        dimensions=args.dimension,
        deliverable_type=args.deliverable_type,
        audience=args.audience,
    )

    if args.json:
        print(json.dumps(case.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"Analysis Case: {case.case_id}")
    print(f"场景: {case.knowledge_tags[0] if case.knowledge_tags else case.scenario}")
    print(f"分析目的: {case.analysis_purpose}")
    print("\n待确认问题:")
    for item in case.clarification_questions:
        print(f"- {item}")
    print("\n核心假设:")
    for item in case.hypotheses:
        print(f"- {item}")
    print("\n核心指标:")
    for metric in case.metric_tree:
        print(f"- {metric.name}: {metric.business_meaning}")
    print("\n校验计划:")
    for check in case.validation_plan:
        print(f"- {check.name}: {check.method}")
    if case.deliverable:
        print("\n交付草稿:")
        for item in case.deliverable.executive_summary:
            print(f"- {item}")


if __name__ == "__main__":
    main()
