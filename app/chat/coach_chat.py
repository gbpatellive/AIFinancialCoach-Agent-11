import re
from typing import Any

from app.models.schemas import AgentContext
from app.rag.tabular_retriever import category_spend, mode_breakdown, monthly_cashflow

DISCLAIMER = (
    "\n\n---\n*Educational guidance only — not legal, tax, or investment advice. "
    "Consult licensed professionals for regulated decisions.*"
)


class FinancialCoachChat:
    """Context-aware financial coach chat using the logged-in user's financial profile."""

    def respond(self, message: str, ctx: AgentContext, plan: dict | None = None) -> str:
        text = message.strip()
        if not text:
            return self._help(ctx) + DISCLAIMER

        lowered = text.lower()
        snapshot = self._build_snapshot(ctx, plan)

        if self._matches(lowered, ["help", "what can you", "how do i", "commands", "options"]):
            return self._help(ctx) + DISCLAIMER

        if self._matches(lowered, ["hello", "hi", "hey", "good morning", "good evening"]):
            return self._greeting(ctx, snapshot) + DISCLAIMER

        if self._matches(lowered, ["summary", "overview", "financial position", "my situation", "how am i"]):
            return self._financial_summary(snapshot) + DISCLAIMER

        if self._matches(lowered, ["debt", "loan", "balance", "owe", "owing", "apr", "interest rate"]):
            return self._debt_insights(ctx, snapshot, plan) + DISCLAIMER

        if self._matches(lowered, ["dti", "debt to income", "debt-to-income"]):
            return self._dti_insight(snapshot) + DISCLAIMER

        if self._matches(
            lowered,
            ["expense", "spending", "spend", "budget", "category", "categories", "where is my money"],
        ):
            return self._budget_insights(ctx, plan) + DISCLAIMER

        if self._matches(lowered, ["cashflow", "cash flow", "surplus", "deficit", "disposable", "left over"]):
            return self._cashflow_insight(ctx, snapshot) + DISCLAIMER

        if self._matches(lowered, ["saving", "savings", "emergency fund", "emergency", "rainy day"]):
            return self._savings_insight(plan) + DISCLAIMER

        if self._matches(
            lowered,
            ["payoff", "pay off", "debt free", "debt-free", "timeline", "how long", "months to", "avalanche"],
        ):
            return self._payoff_insight(plan, snapshot) + DISCLAIMER

        if self._matches(lowered, ["payoff mode", "aggressive", "balanced", "conservative", "strategy mode"]):
            return self._payoff_mode_insight(ctx, plan) + DISCLAIMER

        if self._matches(lowered, ["next step", "next action", "recommend", "suggest", "what should i", "advice"]):
            return self._recommendations(plan, snapshot) + DISCLAIMER

        if self._matches(lowered, ["plan", "agent", "insight", "analysis", "report"]):
            return self._plan_summary(plan) + DISCLAIMER

        if self._matches(lowered, ["income", "salary", "earn"]):
            return self._income_insight(ctx, snapshot) + DISCLAIMER

        return self._fallback(snapshot) + DISCLAIMER

    def _matches(self, text: str, keywords: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in keywords)

    def _build_snapshot(self, ctx: AgentContext, plan: dict | None) -> dict[str, Any]:
        cash = monthly_cashflow(ctx.transactions)
        total_debt = sum(d.balance for d in ctx.debts)
        total_min = sum(d.min_payment for d in ctx.debts)
        weighted_apr = (
            sum(d.balance * d.apr for d in ctx.debts) / total_debt if total_debt > 0 else 0.0
        )
        income = ctx.profile.monthly_income or cash["income"]
        expenses = cash["expense"]
        net = income - expenses - total_min
        dti = (total_min / income * 100.0) if income > 0 else 0.0

        months_to_free = None
        if plan:
            months_to_free = plan.get("headline", {}).get("estimated_months_to_debt_free")

        return {
            "user_id": ctx.profile.user_id,
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "total_debt": round(total_debt, 2),
            "total_min_payment": round(total_min, 2),
            "weighted_apr": round(weighted_apr, 2),
            "net_cashflow": round(net, 2),
            "dti": round(dti, 1),
            "payoff_mode": ctx.profile.payoff_mode,
            "debt_count": len(ctx.debts),
            "months_to_debt_free": months_to_free,
            "has_plan": plan is not None,
        }

    def _greeting(self, ctx: AgentContext, snapshot: dict) -> str:
        plan_note = (
            "I've loaded your latest financial plan — ask me anything about it."
            if snapshot["has_plan"]
            else "Generate a plan on the left, then ask me to explain debt, budget, or payoff details."
        )
        return (
            f"Hi! I'm your **AI Financial Coach** for `{ctx.profile.user_id}`.\n\n"
            f"{plan_note}\n\n"
            "Try asking:\n"
            "- *What's my debt situation?*\n"
            "- *Where am I spending the most?*\n"
            "- *How long until I'm debt-free?*\n"
            "- *What should I do next?*"
        )

    def _help(self, ctx: AgentContext) -> str:
        return (
            f"**Financial Coach — `{ctx.profile.user_id}`**\n\n"
            "Ask natural questions about your finances. I use your logged-in financial profile "
            "and generated plan (when available).\n\n"
            "**Topics I can help with:**\n"
            "- **Debt** — balances, APR, risk, individual accounts\n"
            "- **Budget** — top spending categories and payment modes\n"
            "- **Cashflow** — surplus/deficit and disposable income\n"
            "- **Savings** — emergency fund target and auto-save amount\n"
            "- **Payoff** — timeline, strategy, and payoff mode impact\n"
            "- **Recommendations** — next actions from your plan\n"
            "- **Summary** — full financial position overview"
        )

    def _financial_summary(self, snapshot: dict) -> str:
        status = "deficit" if snapshot["net_cashflow"] < 0 else "surplus"
        plan_line = (
            f"- **Est. months to debt-free:** {snapshot['months_to_debt_free']}\n"
            if snapshot["months_to_debt_free"] is not None
            else "- **Est. months to debt-free:** Generate a plan first\n"
        )
        return (
            "**Your Financial Snapshot**\n\n"
            f"- **Monthly income:** {snapshot['income']:,.2f}\n"
            f"- **Monthly expenses:** {snapshot['expenses']:,.2f}\n"
            f"- **Total debt:** {snapshot['total_debt']:,.2f} across {snapshot['debt_count']} account(s)\n"
            f"- **Min debt payments:** {snapshot['total_min_payment']:,.2f}\n"
            f"- **Weighted APR:** {snapshot['weighted_apr']:.2f}%\n"
            f"- **DTI (min payment / income):** {snapshot['dti']:.1f}%\n"
            f"- **Net cashflow:** {snapshot['net_cashflow']:,.2f} ({status})\n"
            f"- **Payoff mode:** {snapshot['payoff_mode'].title()}\n"
            f"{plan_line}"
        )

    def _debt_insights(self, ctx: AgentContext, snapshot: dict, plan: dict | None) -> str:
        if not ctx.debts:
            return "No debt accounts were found in your financial profile."

        risk = "high" if snapshot["weighted_apr"] >= 20 else "medium" if snapshot["weighted_apr"] >= 12 else "low"
        lines = [
            "**Debt Analysis**\n",
            f"- **Total balance:** {snapshot['total_debt']:,.2f}",
            f"- **Weighted APR:** {snapshot['weighted_apr']:.2f}%",
            f"- **Risk level:** {risk}",
            f"- **Total minimum payments:** {snapshot['total_min_payment']:,.2f}/month",
            "",
            "**Accounts:**",
        ]
        for debt in sorted(ctx.debts, key=lambda d: d.balance, reverse=True):
            lines.append(
                f"- **{debt.name}** — balance {debt.balance:,.2f}, APR {debt.apr:.2f}%, "
                f"min payment {debt.min_payment:,.2f}"
            )

        if plan:
            analyzer = self._agent_output(plan, "debt_analyzer")
            if analyzer:
                lines.extend(["", f"*Agent insight:* {analyzer.get('summary', '')}"])

        highest = max(ctx.debts, key=lambda d: d.apr)
        lines.extend(
            [
                "",
                f"**Tip:** Focus extra payments on **{highest.name}** first (highest APR at {highest.apr:.2f}%) "
                "using the avalanche method.",
            ]
        )
        return "\n".join(lines)

    def _dti_insight(self, snapshot: dict) -> str:
        dti = snapshot["dti"]
        if dti >= 40:
            level = "high — prioritize reducing debt obligations"
        elif dti >= 25:
            level = "moderate — monitor closely and avoid new debt"
        else:
            level = "healthy — room to accelerate payoff or savings"

        return (
            f"**Debt-to-Income (DTI)**\n\n"
            f"Your DTI based on minimum debt payments is **{dti:.1f}%** ({level}).\n\n"
            f"- Monthly income: {snapshot['income']:,.2f}\n"
            f"- Min debt payments: {snapshot['total_min_payment']:,.2f}\n"
            f"- Net cashflow after expenses & debt mins: {snapshot['net_cashflow']:,.2f}"
        )

    def _budget_insights(self, ctx: AgentContext, plan: dict | None) -> str:
        spend = category_spend(ctx.transactions)
        if not spend:
            return "No expense data was found in your financial profile."

        lines = ["**Spending by Category**\n"]
        for category, amount in list(spend.items())[:5]:
            pct = (amount / sum(spend.values()) * 100) if spend else 0
            lines.append(f"- **{category}:** {amount:,.2f} ({pct:.0f}% of expenses)")

        modes = mode_breakdown([t for t in ctx.transactions if t.type == "expense"])
        if modes:
            lines.extend(["", "**Payment modes (expenses):**"])
            for mode, amount in list(modes.items())[:4]:
                lines.append(f"- {mode.replace('_', ' ').title()}: {amount:,.2f}")

        if plan:
            advisor = self._agent_output(plan, "budget_advisor")
            if advisor:
                targets = advisor.get("details", {}).get("reduction_targets", [])
                if targets:
                    lines.extend(["", "**Suggested 15% cuts:**"])
                    for target in targets:
                        lines.append(
                            f"- {target['category']}: save ~{target['suggested_cut']:,.2f}/month"
                        )

        top = next(iter(spend))
        lines.extend(
            [
                "",
                f"**Tip:** Start by trimming **{top}** — it's your largest expense category.",
            ]
        )
        return "\n".join(lines)

    def _cashflow_insight(self, ctx: AgentContext, snapshot: dict) -> str:
        cash = monthly_cashflow(ctx.transactions)
        income = ctx.profile.monthly_income or cash["income"]
        net = snapshot["net_cashflow"]

        if net < 0:
            guidance = (
                f"You have a **monthly deficit of {abs(net):,.2f}**. "
                "Consider reducing top expense categories or switching to a conservative payoff mode."
            )
        else:
            guidance = (
                f"You have a **monthly surplus of {net:,.2f}** after expenses and minimum debt payments. "
                "This can accelerate debt payoff or build your emergency fund."
            )

        return (
            "**Cashflow Analysis**\n\n"
            f"- Transaction income: {cash['income']:,.2f}\n"
            f"- Transaction expenses: {cash['expense']:,.2f}\n"
            f"- Profile monthly income: {income:,.2f}\n"
            f"- Min debt payments: {snapshot['total_min_payment']:,.2f}\n"
            f"- **Net cashflow:** {net:,.2f}\n\n"
            f"{guidance}"
        )

    def _savings_insight(self, plan: dict | None) -> str:
        if not plan:
            return (
                "Generate a financial plan first to get personalized savings targets. "
                "I'll calculate your emergency fund goal and recommended auto-save amount."
            )

        savings = self._agent_output(plan, "savings_strategy")
        if not savings:
            return "Savings analysis is not available yet. Generate a plan to unlock savings recommendations."

        details = savings.get("details", {})
        return (
            "**Savings Strategy**\n\n"
            f"- **Payoff mode:** {details.get('mode', 'N/A').title()}\n"
            f"- **Emergency fund target:** {details.get('emergency_fund_target', 0):,.2f} "
            f"({details.get('emergency_months', 'N/A')} months of expenses)\n"
            f"- **Recommended auto-save:** {details.get('auto_save_per_month', 0):,.2f}/month\n\n"
            f"*Agent insight:* {savings.get('summary', '')}"
        )

    def _payoff_insight(self, plan: dict | None, snapshot: dict) -> str:
        if not plan:
            return (
                "Generate a plan to see your debt-free timeline. "
                "I'll simulate avalanche payoff based on your income, expenses, and payoff mode."
            )

        payoff = self._agent_output(plan, "debt_payoff_optimizer")
        if not payoff:
            return "Payoff simulation is not available. Try generating a plan with valid debt data."

        details = payoff.get("details", {})
        months = details.get("estimated_months_to_debt_free")
        interest = details.get("estimated_total_interest_paid", 0)
        extra = details.get("extra_payment_budget", 0)

        return (
            "**Debt Payoff Projection**\n\n"
            f"- **Strategy:** Avalanche (highest APR first)\n"
            f"- **Payoff mode:** {snapshot['payoff_mode'].title()}\n"
            f"- **Extra payment budget:** {extra:,.2f}/month\n"
            f"- **Total monthly payment budget:** {details.get('total_monthly_payment_budget', 0):,.2f}\n"
            f"- **Estimated months to debt-free:** {months}\n"
            f"- **Estimated total interest:** {interest:,.2f}\n\n"
            f"*Agent insight:* {payoff.get('summary', '')}"
        )

    def _payoff_mode_insight(self, ctx: AgentContext, plan: dict | None) -> str:
        current = ctx.profile.payoff_mode
        modes = {
            "aggressive": "70% of disposable income toward extra debt payments; 3-month emergency fund target.",
            "balanced": "45% extra toward debt; 4-month emergency fund; good middle ground.",
            "conservative": "25% extra toward debt; 6-month emergency fund; prioritizes safety buffer.",
        }

        lines = [
            f"**Payoff Mode: {current.title()}** (your current setting)\n",
            f"{modes[current]}\n",
            "**All modes compared:**",
        ]
        for mode, desc in modes.items():
            marker = " ← current" if mode == current else ""
            lines.append(f"- **{mode.title()}:** {desc}{marker}")

        if plan:
            months = plan.get("headline", {}).get("estimated_months_to_debt_free")
            if months is not None:
                lines.append(f"\nWith **{current}** mode, you're projected debt-free in **~{months} months**.")
                lines.append("Switch modes in the profile section and regenerate the plan to compare timelines.")

        return "\n".join(lines)

    def _recommendations(self, plan: dict | None, snapshot: dict) -> str:
        lines = ["**Recommended Next Steps**\n"]

        if snapshot["net_cashflow"] < 0:
            lines.append("1. **Urgent:** Address your monthly deficit before accelerating debt payoff.")

        if plan:
            actions = plan.get("next_actions", [])
            for i, action in enumerate(actions, 1):
                lines.append(f"{i}. {action}")
        else:
            lines.extend(
                [
                    "1. Click **Generate Plan** to run all financial agents.",
                    "2. Review top spending categories and cut the largest by 15%.",
                    "3. Set up autopay for minimum + extra debt payments.",
                ]
            )

        if snapshot["weighted_apr"] >= 15:
            lines.append(
                f"\n**Priority:** Your weighted APR is {snapshot['weighted_apr']:.2f}% — "
                "focus on high-interest debt first."
            )

        return "\n".join(lines)

    def _plan_summary(self, plan: dict | None) -> str:
        if not plan:
            return (
                "No plan generated yet. Click **Generate Plan** on the left panel, "
                "then ask me to explain any agent's findings."
            )

        lines = ["**Multi-Agent Plan Summary**\n"]
        for output in plan.get("outputs", []):
            name = output.get("agent_name", "unknown").replace("_", " ").title()
            lines.append(f"**{name}**\n{output.get('summary', 'No summary.')}\n")

        headline = plan.get("headline", {})
        if headline.get("estimated_months_to_debt_free") is not None:
            lines.append(
                f"**Headline:** Debt-free in ~{headline['estimated_months_to_debt_free']} months "
                f"({plan.get('payoff_mode', 'N/A').title()} mode)."
            )

        return "\n".join(lines)

    def _income_insight(self, ctx: AgentContext, snapshot: dict) -> str:
        cash = monthly_cashflow(ctx.transactions)
        return (
            "**Income Overview**\n\n"
            f"- **Profile monthly income:** {ctx.profile.monthly_income:,.2f}\n"
            f"- **Income from financial profile:** {cash['income']:,.2f}\n"
            f"- **Monthly expenses:** {snapshot['expenses']:,.2f}\n"
            f"- **After expenses & min debt payments:** {snapshot['net_cashflow']:,.2f}"
        )

    def _fallback(self, snapshot: dict) -> str:
        return (
            "I'm not sure I understood that. Here are things you can ask:\n\n"
            "- *What's my debt situation?*\n"
            "- *Show my top expenses*\n"
            "- *How long until I'm debt-free?*\n"
            "- *What's my DTI?*\n"
            "- *Give me a financial summary*\n"
            "- *What should I do next?*\n\n"
            f"Quick snapshot: debt **{snapshot['total_debt']:,.2f}**, "
            f"net cashflow **{snapshot['net_cashflow']:,.2f}**, "
            f"payoff mode **{snapshot['payoff_mode']}**."
        )

    def _agent_output(self, plan: dict, agent_name: str) -> dict | None:
        for output in plan.get("outputs", []):
            if output.get("agent_name") == agent_name:
                return output
        return None
