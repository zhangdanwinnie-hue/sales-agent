---
name: bp-ba-sales-analysis
description: Use when Codex needs to choose BP BA analysis themes, map required fields, define metrics, or draft analysis plans for BI register-to-order sales funnel data with fields such as register, leads, oppty, visit, test drive, order, channel, campaign, model, dealer, region, and data-quality columns.
---

# BP BA Sales Analysis

Use this skill to turn a BP BA business question into a concrete sales-funnel analysis plan.

## Workflow

1. Identify the business theme: funnel, channel, model, dealer, region, campaign, follow-up, conversion cycle, battle-fail, loyal-customer new-car sales, customer repeat/cross-dealer, single-stage review, or data quality.
2. Load `references/topic-field-map.md` when field-level detail is needed.
3. Select required fields first, then optional drill-down fields.
4. State the metric grain before giving conclusions: row-level non-empty ID counts, distinct stage IDs, customer-level, dealer-level, or semantic-layer metrics.
5. Default to aggregate-only outputs. Do not export customer phone, VIN, customer name, consultant name, or other personal-level fields.
6. Draft BP BA deliverables as: analysis objective, metric口径, dimensions, data checks, findings, hypotheses, and next validation steps.

## Analysis Framework Patterns

- Conversion cycle: split online lead-to-store and store-to-order; compare median/P75 cycle time, 7/14/30-day conversion, and cycle buckets by channel, region, city, dealer, and model.
- Loyal-customer new-car sales: compare loyal customers vs new customers; split by customer_loyal_flag, vehicle age, historical series, channel, region, dealer, and intended model.
- Single-stage review: start from one declining stage such as traffic, leads, store visits, test drives, or orders; decompose current vs previous period into natural/online, region, city, dealer, channel, campaign, and model contributions.

## Recommended Demo Path

Use this path when building a first demo from the real `ads_rpt_sal_ncs_register_to_order_sales_ssa_t` zip:

1. Sales funnel overview: `register -> leads -> oppty -> visit -> td -> order`.
2. Channel efficiency drill-down: channel/media/campaign contribution and conversion.
3. Conversion-cycle view: online lead-to-store and store-to-order cycle distribution.
4. Region/model split: identify where conversion gaps concentrate.
5. Dealer operation view: find high-volume low-conversion dealers or risky dealer statuses.
6. Agent story output: generate conclusion draft, data口径, validation notes, and PPT storyline.

## Field Rules

- Treat `register_*`, `leads_*`, `oppty_*`, `visit_*`, `td_*`, and `order_*` as stage-specific field families.
- Prefer ID fields for stage existence checks: `register_rcid`, `leads_id`, `oppty_id`, `visit_id`, `td_id`, `order_id`.
- Prefer time fields for stage chronology: `register_create_time`, `leads_create_time`, `oppty_create_time`, `visit_arrival_time`, `td_start_time`, `order_first_confirm_time`.
- Prefer non-personal dimensions for demos: `region_route`, `brand_route`, `leads_channel_name`, `leads_media_platform_name`, `leads_campaign_name`, `register_model`, `dealer_status_name`, `risk_dealer_type`.
- Use customer-level fields only for aggregate privacy-safe repeat/cross-dealer analysis.

## Integration

Inside this repo, the same analysis map is implemented in `src/bp_ba_agent/analysis_topics.py`. Use the CLI to inspect it:

```powershell
$env:PYTHONPATH="src"
python -m bp_ba_agent --list-topics
python -m bp_ba_agent --topic media_channel_efficiency
python -m bp_ba_agent --topic conversion_cycle_analysis
python -m bp_ba_agent --topic loyal_customer_new_car_sales
python -m bp_ba_agent --topic single_stage_review
python -m bp_ba_agent "分析汽车之家线索多但订单转化低的原因" --recommend-topics
python -m bp_ba_agent "复盘客流下降，区分自然客流下降和线上客流下降" --recommend-topics
```
