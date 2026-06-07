# BP BA Sales Analysis Topic Field Map

## 1. 销售漏斗转化分析

- Use for: register 到 leads/oppty/visit/td/order 掉点定位；不同渠道、区域、车型、经销商的漏斗异常。
- Required fields: `register_rcid`, `leads_id`, `oppty_id`, `visit_id`, `td_id`, `order_id`, `register_create_time`, `leads_create_time`, `oppty_create_time`, `visit_arrival_time`, `td_start_time`, `order_first_confirm_time`.
- Optional fields: `region_route`, `brand_route`, `leads_channel_name`, `register_model`, `dealer_status_name`.
- Metrics: 阶段记录量、阶段转化率、`order/leads`、`order/oppty`、阶段缺失率。
- Caution: 先确认表粒度；演示可按 ID 非空行数，正式分析建议 distinct ID 或语义层口径。

## 2. 媒体投流与渠道效率分析

- Use for: 渠道量质评估；汽车之家、懂车帝、DMO、抖音、易车等渠道效率差异。
- Required fields: `leads_id`, `oppty_id`, `visit_id`, `order_id`, `leads_channel_name`.
- Optional fields: `leads_sub_channel_name`, `leads_media_platform_name`, `register_first_channel_name`, `register_media_platform_name`, `leads_campaign_name`, `register_campaign_name`, `region_route`, `register_model`.
- Metrics: 线索量、机会量、到店量、订单量、到店率、订单转化率。
- Caution: 渠道字段存在 register 与 leads 两套口径，必须说明归因口径。

## 3. 车型转化分析

- Use for: 高线索低订单车型；车型问题阶段定位。
- Required fields: `leads_id`, `oppty_id`, `visit_id`, `td_id`, `order_id`.
- Optional fields: `register_model`, `register_series`, `leads_model_code_ssc`, `oppty_model_code_ssc`, `visit_model_code_ssc`, `td_model_code_ssc`, `order_model_code_ssc`, `brand_route`.
- Metrics: 车型线索量、车型到店率、车型试驾率、车型订单率、车型阶段掉点。
- Caution: 不同阶段车型字段可能不一致，需要标注 register/leads/order 车型口径。

## 4. 经销商运营分析

- Use for: 线索多但承接弱、同区域同车型经销商异常、风险经销商表现。
- Required fields: `leads_id`, `oppty_id`, `visit_id`, `order_id`.
- Optional fields: `register_dealer_id`, `leads_dealer_id`, `oppty_dealer_id`, `visit_dealer_id`, `td_dealer_id`, `order_dealer_id`, `dealer_status_name`, `risk_dealer_type`, `dealership_type_name_cn`, `region_route`, `city_name_zh`, `province_name_zh`.
- Metrics: 经销商线索量、经销商到店率、经销商订单率、风险/关闭状态占比、异常排名。
- Caution: 经销商名称和人员字段可能敏感；输出优先使用脱敏 ID 或聚合排名。

## 5. 区域/大区表现分析

- Use for: East/North/West/South 漏斗差异；区域差异归因。
- Required fields: `leads_id`, `oppty_id`, `visit_id`, `order_id`, `region_route`.
- Optional fields: `region_name_zh`, `sales_bmw_big_area_name_zh`, `sales_bmw_small_area_name_zh`, `province_name_zh`, `city_name_zh`, `leads_channel_name`, `register_model`.
- Metrics: 区域线索量、区域到店率、区域订单率、区域结构占比、区域异常变化。
- Caution: 区域字段可能存在 route 与中文区域名称两套体系，需固定口径。

## 6. Campaign 活动效果分析

- Use for: Campaign 带量与质量评估；活动 x 车型/渠道/区域复盘。
- Required fields: `leads_id`, `oppty_id`, `visit_id`, `order_id`.
- Optional fields: `leads_campaign_id`, `leads_campaign_name`, `leads_campaign_type_cmc`, `register_campaign_id`, `register_campaign_name`, `register_campaign_type_cmc`, `leads_channel_name`, `region_route`, `register_model`.
- Metrics: 活动线索量、活动到店率、活动订单率、活动贡献占比、活动质量排名。
- Caution: Campaign 名称可能很长且口径混杂，建议同时保留 ID 和 name。

## 7. 销售跟进效率分析

- Use for: 跟进速度与转化关系；渠道/经销商响应效率。
- Required fields: `leads_id`, `oppty_id`, `order_id`.
- Optional fields: `leads_first_follow_mindiff`, `oppty_first_oppty_follow_mindiff`, `oppty_leads_sr_datediff`, `oppty_sr_datediff`, `oppty_td_datediff`, `oppty_order_datediff`, `order_first_sr_order_datediff`, `order_last_sr_order_datediff`, `leads_channel_name`, `leads_dealer_id`.
- Metrics: 首次跟进时长、到店间隔、试驾间隔、订单间隔、超时线索订单率。
- Caution: 时长字段需确认单位和起止点；空值不能简单按 0 处理。

## 8. 战败/流失原因分析

- Use for: 未转化原因、战败原因、战败阶段定位。
- Required fields: `oppty_id`, `oppty_opportunity_status_desc`.
- Optional fields: `oppty_battle_fail_type_desc`, `oppty_battle_fail_time`, `oppty_battle_fail_primary_reason_desc`, `oppty_battle_fail_secondary_reason_desc`, `oppty_status_flag_nation`, `oppty_status_flag_region`, `oppty_pipeline_stage_desc`, `leads_channel_name`, `register_model`, `region_route`.
- Metrics: 战败机会量、战败率、主原因占比、阶段分布、高战败组合。
- Caution: 战败原因依赖销售填写质量，需同时看空值率和异常原因值。

## 9. 客户重复/跨店/跨区域分析

- Use for: 多次留资、跨店流转、多渠道触达。
- Required fields: `leads_id`.
- Optional fields: `customer_spark_id`, `customer_id`, `leads_dealer_cnt_nation_ytd`, `leads_dealer_cnt_nation_6m`, `leads_dealer_cnt_city_mtd`, `leads_channel_cnt_nation_ytd`, `transfer_ticket_flag`, `transfer_source_dealer_id`, `transfer_target_dealer_id`, `order_id`.
- Metrics: 重复留资率、跨店线索占比、跨店订单率、转派成功率、多渠道触达数。
- Caution: 客户级分析权限风险最高；默认只输出聚合，不导出手机号、姓名、明细 ID。

## 10. 数据质量和口径校验分析

- Use for: 字段缺失、链路断层、leads/oppty/order 口径差异。
- Required fields: `leads_id`, `oppty_id`, `order_id`, `etl_batch_time`.
- Optional fields: `register_rcid`, `visit_id`, `td_id`, `register_valid_flag`, `visit_valid_flag`, `order_deleted_desc`, `leads_channel_name`, `region_route`, `brand_route`, `register_model`.
- Metrics: 字段填充率、阶段断层率、重复率、删除/无效记录占比、口径差异清单。
- Caution: 质量结论要先于业务结论；严重缺失字段不能支撑强业务判断。

## 11. 转化周期分析

- Use for: 线上线索到到店周期、到店到订单周期、周期变长对订单转化的影响。
- Required fields: `leads_id`, `visit_id`, `order_id`, `leads_create_time`, `visit_arrival_time`, `order_first_confirm_time`.
- Optional fields: `register_create_time`, `oppty_create_time`, `td_start_time`, `leads_first_follow_mindiff`, `oppty_leads_sr_datediff`, `oppty_td_datediff`, `oppty_order_datediff`, `order_first_sr_order_datediff`, `leads_channel_name`, `leads_media_platform_name`, `region_route`, `city_name_zh`, `leads_dealer_id`, `register_model`.
- Metrics: 线索到到店周期、到店到订单周期、7/14/30 天内到店率、7/14/30 天内成交率、周期分层订单率。
- Framework: 先做周期分布，再把样本分成快/中/慢周期，比较不同周期组的订单转化；再按渠道、区域、城市、经销商、车型定位周期异常。
- Caution: 必须排除空时间、倒挂时间和极端异常值；起止时间字段要在结论前写清楚。

## 12. 保客新车销售分析

- Use for: 保客再购、保客到店转化、保客与新客的销售漏斗对比。
- Required fields: `leads_id`, `visit_id`, `order_id`, `customer_loyal_flag`.
- Optional fields: `customer_spark_id`, `customer_id`, `customer_group_desc`, `customer_source_desc`, `customer_loyal_vehicle_cnt`, `customer_loyal_eseries`, `customer_loyal_vehicle_age`, `customer_loyal_last_order_mile`, `customer_loyal_afs_level`, `leads_channel_name`, `leads_media_platform_name`, `brand_route`, `register_model`, `region_route`, `city_name_zh`, `leads_dealer_id`, `order_id`.
- Metrics: 保客线索量、保客到店率、保客订单率、保客再购率、保客 vs 新客转化差异。
- Framework: 先比较保客/新客漏斗，再按车龄、历史车系、渠道、区域、经销商、意向车型分层，识别保客转化低的主要位置。
- Caution: 保客分析涉及客户级字段，默认只输出聚合分层；`customer_loyal_flag` 的业务定义需先确认。

## 13. 单环节复盘分析

- Use for: 客流下降、线索下降、到店下降、试驾下降、订单下降等单一环节复盘。
- Required fields: `visit_id`, `visit_arrival_time` for 客流/到店复盘；其他环节需替换为对应阶段 ID 和主时间字段。
- Optional fields: `leads_id`, `register_rcid`, `oppty_id`, `order_id`, `visit_create_time`, `visit_is_nature_sr_flag`, `visit_first_visit_flag_dealer_mtd`, `visit_first_visit_flag_city_mtd`, `visit_first_visit_flag_region_mtd`, `visit_first_sr_flag_dealer_mtd`, `visit_first_sr_flag_city_mtd`, `visit_first_sr_flag_region_mtd`, `visit_dealer_id`, `leads_channel_name`, `leads_media_platform_name`, `leads_campaign_name`, `region_route`, `province_name_zh`, `city_name_zh`, `register_model`, `dealer_status_name`.
- Metrics: 环节量级、环比/同比变化、自然客流量、线上客流量、维度贡献度。
- Framework: 先定义单环节口径，再做当前 vs 对比周期变化；随后拆自然/线上，再按区域、城市、经销商、渠道、车型做贡献拆解。
- Caution: 下降归因建议用贡献拆解，不只看 Top 排名；高基数区域/经销商天然更容易排在前面。
