"""Run the six POC acceptance scenarios as sample Analysis Cases."""

from __future__ import annotations

import json

from bp_ba_agent import BPBAAnalysisAgent


CASES = [
    ("媒体投流转化下降，想定位渠道和归因问题", "media"),
    ("车型 A 的线索很多但订单转化偏低", "model_conversion"),
    ("部分经销商本月客流和订单表现异常", "dealer_operation"),
    ("Target steering 月度订单目标如何拆解到大区和车型", "target_steering"),
]


def main() -> None:
    agent = BPBAAnalysisAgent()
    results = [
        agent.run(question, scenario=scenario, time_range="2026年4月").to_dict()
        for question, scenario in CASES
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
