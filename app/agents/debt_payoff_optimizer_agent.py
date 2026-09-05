from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentOutput
from app.rag.tabular_retriever import monthly_cashflow


class DebtPayoffOptimizerAgent(BaseAgent):
    name = "debt_payoff_optimizer"

    def _extra_ratio(self, mode: str):
        return 0.70 if mode == "aggressive" else 0.45 if mode == "balanced" else 0.25

    def run(self, ctx):
        debts = [
            {"name": d.name, "balance": float(d.balance), "apr": float(d.apr), "min_payment": float(d.min_payment)}
            for d in ctx.debts if d.balance > 0
        ]
        cash = monthly_cashflow(ctx.transactions)
        disposable = max(0.0, cash["disposable"])
        extra_budget = disposable * self._extra_ratio(ctx.profile.payoff_mode)
        monthly_min = sum(d["min_payment"] for d in debts)
        total_budget = monthly_min + extra_budget

        if not debts or total_budget <= 0:
            return AgentOutput(
                agent_name=self.name,
                summary="Insufficient data/budget for payoff simulation.",
                details={"estimated_months_to_debt_free": None, "schedule_preview_first_12_months": []},
                confidence=0.7,
            )

        month, total_interest, schedule = 0, 0.0, []
        while month < 600 and any(d["balance"] > 0.01 for d in debts):
            month += 1

            for d in debts:
                if d["balance"] > 0:
                    i = d["balance"] * (d["apr"] / 1200.0)
                    d["balance"] += i
                    total_interest += i

            left = total_budget
            for d in debts:
                if d["balance"] <= 0:
                    continue
                pay = min(d["min_payment"], d["balance"], left)
                d["balance"] -= pay
                left -= pay
                if left <= 0:
                    break

            if left > 0:
                for d in sorted(debts, key=lambda x: x["apr"], reverse=True):
                    if d["balance"] <= 0:
                        continue
                    pay = min(d["balance"], left)
                    d["balance"] -= pay
                    left -= pay
                    if left <= 0:
                        break

            if month <= 12:
                schedule.append({"month": month, "remaining_balance": round(sum(max(0, d["balance"]) for d in debts), 2)})

        return AgentOutput(
            agent_name=self.name,
            summary=f"Avalanche strategy, mode={ctx.profile.payoff_mode}, debt-free in ~{month} months.",
            details={
                "strategy": "avalanche",
                "payoff_mode": ctx.profile.payoff_mode,
                "monthly_min_total": round(monthly_min, 2),
                "extra_payment_budget": round(extra_budget, 2),
                "total_monthly_payment_budget": round(total_budget, 2),
                "estimated_months_to_debt_free": month,
                "estimated_total_interest_paid": round(total_interest, 2),
                "schedule_preview_first_12_months": schedule,
            },
            confidence=0.8,
        )
