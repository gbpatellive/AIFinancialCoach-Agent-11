from app.agents.debt_analyzer_agent import DebtAnalyzerAgent
from app.agents.budget_advisor_agent import BudgetAdvisorAgent
from app.agents.savings_strategy_agent import SavingsStrategyAgent
from app.agents.debt_payoff_optimizer_agent import DebtPayoffOptimizerAgent
from app.agents.compliance_guard_agent import ComplianceGuardAgent


class FinancialCoachOrchestrator:
    def __init__(self):
        self.agents = [
            DebtAnalyzerAgent(),
            BudgetAdvisorAgent(),
            SavingsStrategyAgent(),
            DebtPayoffOptimizerAgent(),
            ComplianceGuardAgent(),
        ]

    def run(self, ctx):
        outputs = [a.run(ctx).model_dump() for a in self.agents]
        payoff = next((o for o in outputs if o["agent_name"] == "debt_payoff_optimizer"), None)

        return {
            "plan_type": "multi_agent_financial_coach",
            "user_id": ctx.profile.user_id,
            "region": ctx.profile.region,
            "payoff_mode": ctx.profile.payoff_mode,
            "outputs": outputs,
            "headline": {"estimated_months_to_debt_free": payoff["details"].get("estimated_months_to_debt_free") if payoff else None},
            "next_actions": [
                "Cut top 2 expense categories by 15%",
                "Enable autopay for minimum + extra debt payment",
                "Re-upload latest CSV monthly for re-optimization",
            ],
        }
