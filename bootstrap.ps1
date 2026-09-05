$ErrorActionPreference = "Stop"

$root = "C:\Gaurav\Learning\AI\Hackathon\AIFinancialCoach"

function Write-File {
    param(
        [string]$Path,
        [string]$Content
    )
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
    Write-Host "Wrote: $Path"
}

# Folders
@(
    "$root\app",
    "$root\app\api",
    "$root\app\agents",
    "$root\app\data",
    "$root\app\models",
    "$root\app\rag",
    "$root\data"
) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path $_ | Out-Null
}

# __init__.py files
@(
    "$root\app\__init__.py",
    "$root\app\api\__init__.py",
    "$root\app\agents\__init__.py",
    "$root\app\data\__init__.py",
    "$root\app\models\__init__.py",
    "$root\app\rag\__init__.py"
) | ForEach-Object {
    Set-Content -Path $_ -Value "" -Encoding UTF8
}

Write-File "$root\requirements.txt" @'
fastapi==0.116.1
uvicorn==0.35.0
pandas==2.3.2
pydantic==2.11.7
streamlit==1.49.1
requests==2.32.5
'@

Write-File "$root\app\models\schemas.py" @'
from typing import Dict, List, Literal
from pydantic import BaseModel, Field, field_validator

TransactionType = Literal["income", "expense"]
TransactionMode = Literal["bank", "cash", "upi", "credit_card", "debit_card", "wallet", "other"]
PayoffMode = Literal["conservative", "balanced", "aggressive"]


class Debt(BaseModel):
    name: str
    balance: float
    apr: float
    min_payment: float


class Transaction(BaseModel):
    date: str
    category: str
    amount: float
    type: TransactionType
    mode: TransactionMode = "bank"

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        value = str(v).strip().lower()
        if value in {"expense", "expence", "spend"}:
            return "expense"
        if value in {"income", "earning", "salary"}:
            return "income"
        raise ValueError(f"Invalid transaction type: {v}")

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v):
        value = str(v).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "creditcard": "credit_card",
            "cc": "credit_card",
            "debitcard": "debit_card",
            "gpay": "upi",
            "phonepe": "upi",
            "paytm_upi": "upi",
            "bank_transfer": "bank",
        }
        value = aliases.get(value, value)
        return value if value in {"bank", "cash", "upi", "credit_card", "debit_card", "wallet", "other"} else "other"


class UserProfile(BaseModel):
    user_id: str
    monthly_income: float
    region: str = "global"
    payoff_mode: PayoffMode = "aggressive"


class AgentContext(BaseModel):
    profile: UserProfile
    debts: List[Debt]
    transactions: List[Transaction]
    metadata: Dict = Field(default_factory=dict)


class AgentOutput(BaseModel):
    agent_name: str
    summary: str
    details: Dict
    confidence: float = 0.8
'@

Write-File "$root\app\data\csv_ingestor.py" @'
import pandas as pd
from app.models.schemas import Debt, Transaction


def _assert_columns(df: pd.DataFrame, required: list[str], label: str):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def load_debts_csv(path: str) -> list[Debt]:
    df = pd.read_csv(path)
    _assert_columns(df, ["name", "balance", "apr", "min_payment"], "Debts CSV")
    return [
        Debt(
            name=str(row["name"]),
            balance=float(row["balance"]),
            apr=float(row["apr"]),
            min_payment=float(row["min_payment"]),
        )
        for _, row in df.iterrows()
    ]


def load_transactions_csv(path: str) -> list[Transaction]:
    df = pd.read_csv(path)
    _assert_columns(df, ["date", "category", "amount", "type"], "Transactions CSV")
    if "mode" not in df.columns:
        df["mode"] = "bank"

    return [
        Transaction(
            date=str(row["date"]),
            category=str(row["category"]),
            amount=float(row["amount"]),
            type=row["type"],
            mode=row["mode"],
        )
        for _, row in df.iterrows()
    ]
'@

Write-File "$root\app\rag\tabular_retriever.py" @'
from collections import defaultdict


def monthly_cashflow(transactions):
    income = sum(t.amount for t in transactions if t.type == "income")
    expense = sum(t.amount for t in transactions if t.type == "expense")
    return {"income": round(income, 2), "expense": round(expense, 2), "disposable": round(income - expense, 2)}


def category_spend(transactions):
    spend = defaultdict(float)
    for t in transactions:
        if t.type == "expense":
            spend[t.category] += t.amount
    return dict(sorted(((k, round(v, 2)) for k, v in spend.items()), key=lambda x: x[1], reverse=True))


def mode_breakdown(transactions):
    breakdown = defaultdict(float)
    for t in transactions:
        breakdown[t.mode] += t.amount
    return dict(sorted(((k, round(v, 2)) for k, v in breakdown.items()), key=lambda x: x[1], reverse=True))
'@

Write-File "$root\app\agents\base_agent.py" @'
from abc import ABC, abstractmethod
from app.models.schemas import AgentContext, AgentOutput


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentOutput:
        raise NotImplementedError
'@

Write-File "$root\app\agents\debt_analyzer_agent.py" @'
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
'@

Write-File "$root\app\agents\budget_advisor_agent.py" @'
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
'@

Write-File "$root\app\agents\savings_strategy_agent.py" @'
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
'@

Write-File "$root\app\agents\debt_payoff_optimizer_agent.py" @'
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
'@

Write-File "$root\app\agents\compliance_guard_agent.py" @'
from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentOutput


class ComplianceGuardAgent(BaseAgent):
    name = "compliance_guard"

    def run(self, ctx):
        return AgentOutput(
            agent_name=self.name,
            summary="Educational guidance only; not legal/tax/investment advice.",
            details={
                "disclaimer": "Consult licensed professionals for regulated advice.",
                "region": ctx.profile.region,
                "global_note": "Rules vary by country.",
            },
            confidence=0.99,
        )
'@

Write-File "$root\app\orchestrator.py" @'
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
'@

Write-File "$root\app\api\main.py" @'
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.data.csv_ingestor import load_debts_csv, load_transactions_csv
from app.models.schemas import UserProfile, AgentContext, PayoffMode
from app.orchestrator import FinancialCoachOrchestrator

app = FastAPI(title="AI Financial Coach - Hackathon")
orch = FinancialCoachOrchestrator()


class PlanRequest(BaseModel):
    user_id: str = "demo-user"
    monthly_income: float = 0
    region: str = "global"
    payoff_mode: PayoffMode = "aggressive"
    debts_csv: str
    transactions_csv: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/plan")
def generate_plan(req: PlanRequest):
    try:
        debts = load_debts_csv(req.debts_csv)
        transactions = load_transactions_csv(req.transactions_csv)

        profile = UserProfile(
            user_id=req.user_id,
            monthly_income=req.monthly_income,
            region=req.region,
            payoff_mode=req.payoff_mode,
        )
        ctx = AgentContext(profile=profile, debts=debts, transactions=transactions)
        return orch.run(ctx)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
'@

Write-File "$root\app\dashboard.py" @'
import requests
import streamlit as st
import pandas as pd

st.set_page_config(page_title="AI Financial Coach", layout="wide")
st.title("AI Financial Coach - Multi-Agent Demo")

api_url = st.text_input("API URL", "http://127.0.0.1:8000/plan")
debts_csv = st.text_input("Debts CSV path", r"data\sample_debts.csv")
tx_csv = st.text_input("Transactions CSV path", r"data\sample_transactions.csv")

c1, c2, c3 = st.columns(3)
with c1:
    user_id = st.text_input("User ID", "demo-user")
with c2:
    monthly_income = st.number_input("Monthly Income", min_value=0.0, value=120000.0, step=1000.0)
with c3:
    payoff_mode = st.selectbox("Payoff Mode", ["aggressive", "balanced", "conservative"], index=0)

if st.button("Generate Plan"):
    payload = {
        "user_id": user_id,
        "monthly_income": monthly_income,
        "region": "global",
        "payoff_mode": payoff_mode,
        "debts_csv": debts_csv,
        "transactions_csv": tx_csv,
    }
    r = requests.post(api_url, json=payload, timeout=60)
    if r.status_code != 200:
        st.error(r.text)
    else:
        data = r.json()
        st.success("Plan generated")
        st.subheader("Headline")
        st.json(data.get("headline", {}))

        for item in data.get("outputs", []):
            st.markdown(f"### {item['agent_name']}")
            st.write(item["summary"])
            st.json(item["details"])

            if item["agent_name"] == "debt_payoff_optimizer":
                schedule = item["details"].get("schedule_preview_first_12_months", [])
                if schedule:
                    df = pd.DataFrame(schedule)
                    st.line_chart(df.set_index("month")["remaining_balance"])
'@

Write-File "$root\data\sample_debts.csv" @'
name,balance,apr,min_payment
Credit Card A,85000,36,3500
Personal Loan,220000,16,6500
Credit Card B,42000,28,2200
'@

Write-File "$root\data\sample_transactions.csv" @'
date,category,amount,type,mode
2026-08-01,Salary,120000,income,bank
2026-08-02,Rent,28000,expense,bank
2026-08-03,Groceries,8500,expense,upi
2026-08-05,Dining,4200,expense,credit_card
2026-08-07,Transport,2500,expense,cash
2026-08-09,Utilities,3900,expense,bank
2026-08-12,Shopping,7800,expense,credit_card
2026-08-15,Freelance,18000,income,upi
2026-08-17,EMI,6500,expense,bank
2026-08-20,Entertainment,3000,expense,wallet
'@

Write-File "$root\run_api.ps1" @'
Set-Location C:\Gaurav\Learning\AI\Hackathon\AIFinancialCoach
pip install -r requirements.txt
uvicorn app.api.main:app --reload
'@

Write-File "$root\run_dashboard.ps1" @'
Set-Location C:\Gaurav\Learning\AI\Hackathon\AIFinancialCoach
streamlit run app\dashboard.py
'@

Write-Host "`nBootstrap completed."
Write-Host "Next:"
Write-Host "1) py -m venv .venv"
Write-Host "2) .\.venv\Scripts\Activate.ps1"
Write-Host "3) pip install -r requirements.txt"
Write-Host "4) uvicorn app.api.main:app --reload"
Write-Host "5) streamlit run app\dashboard.py"