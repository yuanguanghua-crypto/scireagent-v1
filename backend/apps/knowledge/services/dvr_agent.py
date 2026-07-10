"""DVR Protocol Agent: Design-Verify-Rectify Loop
Implements a simplified neuro-symbolic FSM for protocol generation based on
the BioProAgent Design-Verify-Rectify pattern.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """FSM 状态"""
    INIT = "INIT"
    CHATTING = "CHATTING"
    CLARIFY_INTENT = "CLARIFY_INTENT"
    DESIGN_DRAFT = "DESIGN_DRAFT"
    VERIFY_DRAFT = "VERIFY_DRAFT"
    RECTIFY_DRAFT = "RECTIFY_DRAFT"
    SUCCESS = "SUCCESS"


@dataclass
class ContextSignals:
    """上下文信号"""
    sigma_ambiguous: bool = False
    sigma_know: bool = False
    sigma_draft: bool = False
    sigma_sci_pos: bool = False
    sigma_sci_neg: bool = False


@dataclass
class PlannerContext:
    """规划器上下文"""
    session_id: str = ""
    user_input: str = ""
    experiment_context: str = ""
    current_state: AgentState = AgentState.INIT
    mem_work: dict = field(default_factory=dict)
    mem_episodic: list = field(default_factory=list)


@dataclass
class ValidationReport:
    """校验报告"""
    class _Section:
        def __init__(self):
            self.passed = True
            self.issues = []

    scientific: _Section = field(default_factory=_Section)
    completeness: _Section = field(default_factory=_Section)
    safety: _Section = field(default_factory=_Section)

    def __post_init__(self):
        if isinstance(self.scientific, type):
            self.scientific = self._Section()
        if isinstance(self.completeness, type):
            self.completeness = self._Section()
        if isinstance(self.safety, type):
            self.safety = self._Section()


@dataclass
class GenerationResult:
    """生成结果"""
    protocol: Optional[dict] = None
    status: str = "draft"
    iterations: int = 0
    passed: bool = False
    need_review: bool = False
    persisted: bool = False
    final_state: str = "INIT"
    errors: list = field(default_factory=list)


class ProtocolVerifier:
    """三层协议校验器"""

    DANGEROUS_CHEMICALS = {
        "sodium azide": "Toxic and potentially explosive. Handle with care.",
        "sodium azide ": "Toxic and potentially explosive. Handle with care.",
        "azide": "Potentially explosive. Avoid friction and heat.",
        "azido": "Azide compound - potentially explosive.",
        "NaN3": "Sodium azide - toxic and potentially explosive.",
    }

    def verify(self, draft: dict) -> ValidationReport:
        """执行三层校验"""
        report = ValidationReport()
        report.scientific = self._check_scientific(draft)
        report.completeness = self._check_completeness(draft)
        report.safety = self._check_safety(draft)
        return report

    def _check_scientific(self, draft: dict) -> "_Section":
        s = ValidationReport._Section()
        steps = draft.get("steps", [])
        if not steps:
            s.passed = False
            s.issues.append("No steps defined")
        if len(steps) < 2:
            s.passed = False
            s.issues.append("Too few steps for a complete protocol")
        return s

    def _check_completeness(self, draft: dict) -> "_Section":
        s = ValidationReport._Section()
        if not draft.get("materials"):
            s.passed = False
            s.issues.append("Missing materials section")
        if not draft.get("safety"):
            s.passed = False
            s.issues.append("Missing safety section")
        return s

    def _check_safety(self, draft: dict) -> "_Section":
        s = ValidationReport._Section()
        safety_notes = " ".join(draft.get("safety", [])).lower()
        for material in draft.get("materials", []):
            for chem, warning in self.DANGEROUS_CHEMICALS.items():
                if chem in material.lower() and chem not in safety_notes:
                    s.passed = False
                    s.issues.append(f"Missing safety warning for hazardous material: {material}")
                    break
        return s


class DVRProtocolAgent:
    """DVR 协议生成智能体"""

    def __init__(self):
        self.AgentState = AgentState
        self.state = AgentState.INIT
        self.verifier = ProtocolVerifier()
        self._context = None

    def _create_context(self, product) -> PlannerContext:
        """从产品创建规划上下文"""
        ctx = PlannerContext(
            user_input=f"Design protocol for {product.name} (CAS: {product.cas or 'N/A'})",
            experiment_context=f"Product: {product.name}\nCategory: {product.category_l1}\nSMILES: {product.smiles or 'N/A'}",
            current_state=AgentState.DESIGN_DRAFT,
            mem_work={"knowledge": f"Product info for {product.name}"},
        )
        self._context = ctx
        self.state = AgentState.DESIGN_DRAFT
        return ctx

    def _design(self) -> dict:
        """生成协议草案"""
        draft = {
            "steps": [
                "Prepare reaction mixture with the product and required reagents",
                "Incubate at appropriate temperature for optimal reaction",
                "Monitor reaction progress by TLC or HPLC",
                "Purify the product by appropriate method (extraction/chromatography)",
                "Characterize the final product by NMR, MS, or HPLC",
            ],
            "materials": [self._context.user_input.split(" for ")[-1] if " for " in self._context.user_input else "Product compound"],
            "safety": ["Follow standard laboratory safety procedures"],
        }
        if self._context:
            self._context.mem_work["draft"] = draft
            self._context.mem_work["current_draft"] = draft
        return draft

    def _extract_signals(self, ctx: PlannerContext) -> ContextSignals:
        """提取上下文信号"""
        data = ctx.mem_work
        s = ContextSignals()
        has_exp_info = bool(data.get("knowledge"))
        s.sigma_ambiguous = not has_exp_info
        s.sigma_know = bool(data.get("knowledge"))
        s.sigma_draft = bool(data.get("draft") or data.get("current_draft"))

        ks = data.get("ks_verification", {})
        if isinstance(ks, dict):
            status = str(ks.get("status", "")).lower()
            if status in ("pass", "done", "success"):
                s.sigma_sci_pos = True
            elif status in ("fail",):
                s.sigma_sci_neg = True

        return s

    def _infer_state(self, ctx: PlannerContext) -> AgentState:
        """基于信号推断下一个状态"""
        prev_state = ctx.current_state
        signals = self._extract_signals(ctx)

        decision_chain = [
            (signals.sigma_sci_neg and signals.sigma_draft, AgentState.RECTIFY_DRAFT),
            (not signals.sigma_draft and not signals.sigma_ambiguous, AgentState.DESIGN_DRAFT),
            (signals.sigma_draft and signals.sigma_sci_pos, AgentState.SUCCESS),
            (signals.sigma_draft and not signals.sigma_sci_pos and not signals.sigma_sci_neg, AgentState.VERIFY_DRAFT),
            (signals.sigma_ambiguous, AgentState.CLARIFY_INTENT),
        ]

        for condition, state in decision_chain:
            if condition:
                return state
        return prev_state

    def _verify(self) -> ValidationReport:
        """校验当前草案"""
        draft = self._context.mem_work.get("draft", {}) if self._context else {}
        return self.verifier.verify(draft)

    def _rectify(self, draft: dict, report: ValidationReport) -> dict:
        """根据校验报告修正草案"""
        corrected = {
            "steps": list(draft.get("steps", [])),
            "materials": list(draft.get("materials", [])),
            "safety": list(draft.get("safety", [])),
        }

        # 修复科学性问题
        if not report.scientific.passed:
            if len(corrected["steps"]) < 2:
                corrected["steps"] = [
                    "Prepare the reaction mixture",
                    "Perform the reaction under controlled conditions",
                    "Isolate and purify the product",
                ]

        # 修复材料完整性
        if not report.completeness.passed:
            if "Missing materials section" in (report.completeness.issues or []):
                corrected["materials"] = ["Product compound", "Solvent", "Catalyst"]
            if "Missing safety section" in (report.completeness.issues or []):
                corrected["safety"] = ["Follow standard laboratory safety procedures"]

        # 修复安全问题
        if not report.safety.passed:
            for issue in (report.safety.issues or []):
                if "hazardous material" in issue.lower():
                    corrected["safety"].append("Handle with care - see SDS for hazards")

        return corrected

    def generate(self, product, max_iterations: int = 3) -> GenerationResult:
        """执行完整的 DVR 循环"""
        result = GenerationResult()
        self._create_context(product)

        ctx = self._context
        if ctx is None:
            result.errors.append("Failed to create context")
            return result

        for iteration in range(max_iterations):
            result.iterations = iteration + 1
            self.state = self._infer_state(ctx)

            if self.state == AgentState.DESIGN_DRAFT:
                self._design()
                self.state = AgentState.VERIFY_DRAFT

            if self.state == AgentState.VERIFY_DRAFT:
                report = self._verify()
                ctx.mem_work["ks_verification"] = {
                    "status": "pass" if (report.scientific.passed and
                                         report.completeness.passed and
                                         report.safety.passed) else "fail",
                }
                self.state = self._infer_state(ctx)

            if self.state == AgentState.RECTIFY_DRAFT:
                report = self._verify()
                draft = ctx.mem_work.get("draft", {})
                corrected = self._rectify(draft, report)
                ctx.mem_work["draft"] = corrected
                ctx.mem_work["current_draft"] = corrected
                # 重校验
                self.state = AgentState.VERIFY_DRAFT

            if self.state == AgentState.SUCCESS:
                result.passed = True
                break

        final_draft = ctx.mem_work.get("draft", {}) if ctx else {}
        result.protocol = final_draft
        result.final_state = self.state.value

        if not result.passed:
            result.need_review = True

        return result
