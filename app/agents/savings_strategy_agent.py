from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentOutput
from app.rag.tabular_retriever import monthly_cashflow


class SavingsStrategyAgent(BaseAgent):
    name = "savings_strategy"

    def run(self, ctx):
        cash = monthly_cashflow(ctx.transactions)
        disposable = max(0.0, cash["disposable"])
        monthly_expense = max(1.0, cash["expense"])

        if ctx.profile.payoff_mode == "aggressive":
            emergency_months, save_ratio = 3, 0.15
        elif ctx.profile.payoff_mode == "balanced":
            emergency_months, save_ratio = 4, 0.25
        else:
            emergency_months, save_ratio = 6, 0.35

        emergency_target = round(monthly_expense * emergency_months, 2)
        monthly_auto_save = round(disposable * save_ratio, 2)

        return AgentOutput(
            agent_name=self.name,
            summary=f"Emergency fund target={emergency_target:.2f}, auto-save={monthly_auto_save:.2f}/month.",
            details={
                "mode": ctx.profile.payoff_mode,
                "emergency_months": emergency_months,
                "emergency_fund_target": emergency_target,
                "auto_save_per_month": monthly_auto_save,
            },
            confidence=0.85,
        )
