"""TDD Phase 3: Knowledge Chain Filler (DVR Cycle)
Tests for the Design-Verify-Rectify protocol generation loop.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory


class DVRAgentStructureTest(TestCase):
    """DVR 循环基础结构"""

    # ── Cycle 8: DVR Basics ──────────────────────────────────

    def test_dvr_agent_can_be_instantiated(self):
        """DVR 智能体可实例化"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent, AgentState
        agent = DVRProtocolAgent()
        self.assertIsNotNone(agent)
        self.assertEqual(agent.state, AgentState.INIT)

    def test_agent_states_defined(self):
        """AgentState 枚举包含所有必需状态"""
        from apps.knowledge.services.dvr_agent import AgentState
        required_states = [
            "INIT", "CLARIFY_INTENT", "DESIGN_DRAFT",
            "VERIFY_DRAFT", "RECTIFY_DRAFT", "SUCCESS",
        ]
        for state in required_states:
            self.assertTrue(hasattr(AgentState, state),
                            f"Missing required state: {state}")

    def test_signal_extraction(self):
        """信号提取从上下文提取正确布尔信号"""
        from apps.knowledge.services.dvr_agent import (
            DVRProtocolAgent, PlannerContext, AgentState,
        )
        agent = DVRProtocolAgent()
        ctx = PlannerContext(
            user_input="Design PCR protocol",
            mem_work={"knowledge": "PCR knowledge"},
        )
        signals = agent._extract_signals(ctx)
        self.assertFalse(signals.sigma_ambiguous)
        self.assertTrue(signals.sigma_know)
        self.assertFalse(signals.sigma_draft)

    def test_state_inference_priority_matrix(self):
        """状态推断遵循优先级矩阵"""
        from apps.knowledge.services.dvr_agent import (
            DVRProtocolAgent, PlannerContext, AgentState,
        )
        agent = DVRProtocolAgent()
        # σ_sci- ∧ σ_draft → RECTIFY_DRAFT（优先级 2）
        ctx = PlannerContext(
            user_input="test",
            mem_work={
                "draft": "some draft",
                "ks_verification": {"status": "fail"},
            },
            current_state=AgentState.DESIGN_DRAFT,
        )
        state = agent._infer_state(ctx)
        self.assertEqual(state, AgentState.RECTIFY_DRAFT)


class DesignPhaseTest(TestCase):
    """设计阶段 (DESIGN) 测试"""

    # ── Cycle 9: DESIGN ──────────────────────────────────────

    def test_design_retrieves_knowledge(self):
        """DESIGN 阶段从知识库检索相关信息"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent
        agent = DVRProtocolAgent()
        agent.state = agent.AgentState.DESIGN_DRAFT
        product = ProductFactory(name="5-Ethynyl-dUTP")
        ctx = agent._create_context(product)
        self.assertIsNotNone(ctx)
        self.assertIn("5-Ethynyl", ctx.user_input)

    def test_design_generates_draft(self):
        """DESIGN 阶段生成协议草案"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent
        agent = DVRProtocolAgent()
        product = ProductFactory(name="5-Ethynyl-dUTP")
        agent._create_context(product)
        draft = agent._design()
        self.assertIsNotNone(draft)
        self.assertIn("steps", draft)
        self.assertGreater(len(draft["steps"]), 0)
        self.assertIn("materials", draft)
        self.assertIn("safety", draft)


class VerifyPhaseTest(TestCase):
    """校验阶段 (VERIFY) 测试"""

    # ── Cycle 10: VERIFY ─────────────────────────────────────

    def test_verifier_can_be_instantiated(self):
        """校验器可创建"""
        from apps.knowledge.services.dvr_agent import ProtocolVerifier
        verifier = ProtocolVerifier()
        self.assertIsNotNone(verifier)

    def test_verifier_returns_validation_report(self):
        """校验器返回结构化校验报告"""
        from apps.knowledge.services.dvr_agent import ProtocolVerifier, ValidationReport
        verifier = ProtocolVerifier()
        draft = {"steps": ["Do A", "Do B"], "materials": [], "safety": []}
        report = verifier.verify(draft)
        self.assertIsInstance(report, ValidationReport)
        self.assertIsNotNone(report.scientific)
        self.assertIsNotNone(report.completeness)
        self.assertIsNotNone(report.safety)

    def test_verify_detects_missing_safety_warning(self):
        """校验器发现缺少安全警告"""
        from apps.knowledge.services.dvr_agent import ProtocolVerifier
        verifier = ProtocolVerifier()
        draft = {
            "steps": ["Mix sodium azide with buffer", "Incubate at 37°C"],
            "materials": ["sodium azide", "buffer"],
            "safety": [],
        }
        report = verifier.verify(draft)
        self.assertFalse(report.safety.passed)
        safety_issues = [i for i in report.safety.issues if "azide" in i.lower()]
        self.assertGreater(len(safety_issues), 0)

    def test_verify_all_passed(self):
        """完整合规的草案全部校验通过"""
        from apps.knowledge.services.dvr_agent import ProtocolVerifier
        verifier = ProtocolVerifier()
        draft = {
            "steps": ["Step 1", "Step 2", "Step 3"],
            "materials": ["water", "ethanol"],
            "safety": ["Wear gloves", "Use in fume hood", "Avoid contact with skin"],
        }
        report = verifier.verify(draft)
        self.assertTrue(report.scientific.passed)
        self.assertTrue(report.completeness.passed)
        self.assertTrue(report.safety.passed)


class RectifyPhaseTest(TestCase):
    """修正阶段 (RECTIFY) 测试"""

    # ── Cycle 11: RECTIFY ────────────────────────────────────

    def test_rectify_fixes_identified_issues(self):
        """RECTIFY 根据校验结果修正协议"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent, ValidationReport
        agent = DVRProtocolAgent()
        draft = {"steps": ["Add sodium azide"], "materials": ["sodium azide"], "safety": []}
        report = ValidationReport()
        report.safety.passed = False
        report.safety.issues = ["Missing safety warning for hazardous material: sodium azide"]
        corrected = agent._rectify(draft, report)
        self.assertGreater(len(corrected["safety"]), 0, "Safety section should have been populated")

    def test_rectify_preserves_passed_sections(self):
        """修正不修改已经通过的校验项"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent, ValidationReport
        agent = DVRProtocolAgent()
        draft = {
            "steps": ["Step 1", "Step 2"],
            "materials": ["water"],
            "safety": ["Wear gloves"],
        }
        report = ValidationReport()
        report.scientific.passed = True
        report.safety.passed = True
        report.completeness.passed = False
        report.completeness.issues = ["Missing step 3"]
        corrected = agent._rectify(draft, report)
        # Safety section should not be modified
        self.assertEqual(corrected["safety"], draft["safety"])

    def test_rectify_loop_iteration_count(self):
        """生成函数最多迭代 3 次，超限标记待审核"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent
        agent = DVRProtocolAgent()
        product = ProductFactory(name="TestCompound")
        result = agent.generate(product, max_iterations=3)
        self.assertLessEqual(result.iterations, 3)
        if not result.passed:
            self.assertTrue(result.need_review)


class FullDVRCycleTest(TestCase):
    """端到端 DVR 循环测试"""

    # ── Cycle 12: End-to-End ─────────────────────────────────

    def test_generate_returns_structured_output(self):
        """完整的知识链生成返回结构化输出"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent
        agent = DVRProtocolAgent()
        product = ProductFactory(
            name="5-Ethynyl-dUTP",
            cas="111289-87-3",
            category_l1="nucleotides_nucleosides",
        )
        result = agent.generate(product)
        self.assertIsNotNone(result.protocol)
        self.assertGreater(len(result.protocol["steps"]), 0)

    def test_generate_does_not_persist(self):
        """generate 不自动写入数据库，需人工确认"""
        from apps.knowledge.services.dvr_agent import DVRProtocolAgent
        agent = DVRProtocolAgent()
        product = ProductFactory(name="TestCompound")
        result = agent.generate(product)
        self.assertEqual(result.status, "draft")
        self.assertFalse(result.persisted)
