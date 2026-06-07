from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .data_source import build_profile
from .orchestrator import BAAnalysisOrchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BA daily data analysis agent chatbot.")
    parser.add_argument("--source", required=True, help="Path to .xlsx or .csv data source.")
    args = parser.parse_args(argv)

    profile = build_profile(Path(args.source))
    orchestrator = BAAnalysisOrchestrator(profile)
    _print_intro(profile)

    while True:
        try:
            raw = input("ba-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not raw:
            continue
        command, _, value = raw.partition(" ")
        command = command.lower()

        try:
            if command in {"exit", "quit"}:
                return 0
            if command == "new":
                if not value:
                    print("请输入业务问题，例如：new 帮我分析 5 月注册到订单转化率下降的原因")
                    continue
                _print_json(orchestrator.start(value))
            elif command == "show":
                _print_json(orchestrator.current_artifact())
            elif command == "confirm":
                _print_json(orchestrator.confirm_current())
            elif command == "revise":
                if not value:
                    print("请输入修改意见，例如：revise 时间范围改为 2026-05-01 到 2026-05-15")
                    continue
                _print_json(orchestrator.request_revision(value))
            elif command == "reject":
                if not value:
                    print("请输入拒绝原因，例如：reject 这个阶段的口径不对")
                    continue
                _print_json(orchestrator.reject_current(value))
            elif command == "status":
                _print_json(orchestrator.status())
            elif command == "history":
                _print_json(orchestrator.history())
            elif command == "workflow":
                _print_json(orchestrator.workflow())
            elif command == "llm":
                _print_json(orchestrator.llm_status())
            elif command == "profile":
                _print_json(profile)
            elif command == "help":
                _print_help()
            else:
                print("未知命令。输入 help 查看可用命令。")
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)


def _print_intro(profile: Any) -> None:
    first_table = profile.tables_or_sheets[0] if profile.tables_or_sheets else None
    print("BA 日常数据分析 Agent 已启动。")
    if first_table:
        print(
            f"数据源: {profile.source_type} | {first_table.name} | "
            f"{first_table.row_count} rows | {len(first_table.columns)} columns"
        )
    _print_help()


def _print_help() -> None:
    print(
        "命令: new <业务问题> | show | confirm | revise <修改意见> | "
        "reject <原因> | status | history | workflow | llm | profile | help | exit"
    )


def _print_json(value: Any) -> None:
    print(json.dumps(_to_jsonable(value), ensure_ascii=False, indent=2))


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
