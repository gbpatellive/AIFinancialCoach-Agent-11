from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentOutput
from app.rag.tabular_retriever import category_spend, mode_breakdown, monthly_cashflow


class BudgetAdvisorAgent(BaseAgent):
    name = "budget_advisor"

    def run(self, ctx):
        cash = monthly_cashflow(ctx.transactions)
        spend_by_category = category_spend(ctx.transactions)
        spend_by_mode = mode_breakdown([t for t in ctx.transactions if t.type == "expense"])
        top3 = list(spend_by_category.items())[:3]
        reduction_targets = [{"category": c, "suggested_cut": round(v * 0.15, 2)} for c, v in top3]

        return AgentOutput(
            agent_name=self.name,
            summary=f"Disposable={cash['disposable']:.2f}. Suggested 15% cut in top categories.",
            details={
                "cashflow": cash,
                "top_spend_categories": top3,
                "spend_by_mode_expense_only": spend_by_mode,
                "reduction_targets": reduction_targets,
            },
            confidence=0.84,
        )
