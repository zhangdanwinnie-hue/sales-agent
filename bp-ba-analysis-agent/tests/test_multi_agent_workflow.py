from __future__ import annotations

import unittest

from bp_ba_agent.multi_agent_workflow import (
    BAConfirmation,
    BAConfirmationRequiredError,
    DESIGN_STEP,
    INSIGHT_STEP,
    REPORT_STEP,
    DataInsightAgent,
    MultiAgentWorkflow,
    workflow_contracts,
)


class MultiAgentWorkflowTests(unittest.TestCase):
    def test_contracts_define_three_agents_and_confirmation_gates(self) -> None:
        contracts = workflow_contracts()

        self.assertEqual([contract.agent_id for contract in contracts], [DESIGN_STEP, INSIGHT_STEP, REPORT_STEP])
        self.assertEqual(contracts[0].next_agent, INSIGHT_STEP)
        self.assertEqual(contracts[1].next_agent, REPORT_STEP)
        self.assertIsNone(contracts[2].next_agent)
        self.assertTrue(all(contract.ba_confirmation_gate for contract in contracts))

    def test_workflow_requires_ba_confirmation_between_agents(self) -> None:
        workflow = MultiAgentWorkflow()

        session = workflow.start(
            business_question="为什么 4 月客流下降，需要拆解自然客流、线上客流、区域和渠道",
            target_object="全网客流",
            time_range="2026-04 vs 2026-03",
            dimensions=["月份", "大区", "城市", "经销商", "渠道"],
        )

        self.assertEqual(session.current_step, DESIGN_STEP)
        self.assertEqual(session.status, "waiting_ba_confirmation")
        self.assertIn(DESIGN_STEP, session.results)

        session = workflow.confirm_step(
            session.session_id,
            step_id=DESIGN_STEP,
            confirmed_by="BP BA",
            feedback="分析框架确认。",
        )
        self.assertEqual(session.current_step, INSIGHT_STEP)
        self.assertIn(INSIGHT_STEP, session.results)
        self.assertEqual(session.results[DESIGN_STEP].status, "ba_confirmed")

        session = workflow.confirm_step(
            session.session_id,
            step_id=INSIGHT_STEP,
            confirmed_by="BP BA",
            feedback="数据口径和校验计划确认。",
        )
        self.assertEqual(session.current_step, REPORT_STEP)
        self.assertIn(REPORT_STEP, session.results)
        self.assertEqual(session.results[INSIGHT_STEP].status, "ba_confirmed")

        session = workflow.confirm_step(
            session.session_id,
            step_id=REPORT_STEP,
            confirmed_by="BP BA",
            feedback="报告草稿确认，可以发布内部版本。",
        )
        self.assertEqual(session.current_step, "completed")
        self.assertEqual(session.status, "completed")
        self.assertEqual(session.results[REPORT_STEP].status, "ba_confirmed")

    def test_data_agent_rejects_unconfirmed_design(self) -> None:
        workflow = MultiAgentWorkflow()
        session = workflow.start(business_question="分析车型转化问题")

        with self.assertRaises(BAConfirmationRequiredError):
            DataInsightAgent().run(
                session.case,
                BAConfirmation(
                    step_id=DESIGN_STEP,
                    confirmed=False,
                    confirmed_by="BP BA",
                    feedback="还需要改。",
                ),
            )

    def test_reject_feedback_keeps_session_on_current_step(self) -> None:
        workflow = MultiAgentWorkflow()
        session = workflow.start(business_question="分析经销商运营异常")

        session = workflow.confirm_step(
            session.session_id,
            step_id=DESIGN_STEP,
            confirmed=False,
            confirmed_by="BP BA",
            feedback="需要增加城市维度。",
        )

        self.assertEqual(session.current_step, DESIGN_STEP)
        self.assertEqual(session.status, "ba_revision_requested")
        self.assertNotIn(INSIGHT_STEP, session.results)


if __name__ == "__main__":
    unittest.main()
