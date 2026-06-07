"""Read-only integration contracts for future Data Center, BI, and KM access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class QueryPreview:
    source: str
    rows: list[dict[str, object]]
    warnings: list[str]


class ReadOnlyDataConnector(Protocol):
    """Contract implemented by real warehouse/Tableau connectors later."""

    name: str

    def preview_metric(self, metric_name: str, filters: dict[str, str]) -> QueryPreview:
        """Return a small read-only preview for human review."""


class MockDataWarehouseConnector:
    name = "Data Center / 数仓只读连接"

    def preview_metric(self, metric_name: str, filters: dict[str, str]) -> QueryPreview:
        return QueryPreview(
            source=self.name,
            rows=[
                {
                    "metric": metric_name,
                    "period": filters.get("time_range", "待确认周期"),
                    "value": "POC mock value",
                    "note": "真实环境由数仓只读查询返回。",
                }
            ],
            warnings=["当前为 POC mock connector，未访问真实生产数据。"],
        )


class MockTableauConnector:
    name = "Tableau / BI 元数据只读连接"

    def preview_metric(self, metric_name: str, filters: dict[str, str]) -> QueryPreview:
        return QueryPreview(
            source=self.name,
            rows=[
                {
                    "metric": metric_name,
                    "dashboard": f"{metric_name}相关看板",
                    "owner": "BI 产品团队",
                    "note": "真实环境由 Tableau metadata/API 返回。",
                }
            ],
            warnings=["当前为 POC mock connector，未访问真实 Tableau。"],
        )
