from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentOutput


class DebtAnalyzerAgent(BaseAgent):
    name = "debt_analyzer"

    def run(self, ctx):
        total_balance = sum(d.balance for d in ctx.debts)
        monthly_min_total = sum(d.min_payment for d in ctx.debts)
        weighted_apr = sum(d.balance * d.apr for d in ctx.debts) / total_balance if total_balance > 0 else 0.0
        risk = "high" if weighted_apr >= 20 else "medium" if weighted_apr >= 12 else "low"

        return AgentOutput(
            agent_name=self.name,
            summary=f"Debt={total_balance:.2f}, weighted APR={weighted_apr:.2f}%, risk={risk}",
            details={
                "total_balance": round(total_balance, 2),
                "weighted_apr": round(weighted_apr, 2),
                "monthly_min_total": round(monthly_min_total, 2),
                "risk": risk,
            },
            confidence=0.91,
        )
