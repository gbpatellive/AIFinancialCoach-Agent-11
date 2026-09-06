from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from app.data.csv_ingestor import load_debts_csv, load_transactions_csv
from app.data.json_ingestor import normalize_to_legacy_context
from app.models.schemas import AgentContext, PayoffMode, UserProfile
from app.orchestrator import FinancialCoachOrchestrator

app = FastAPI(title="AI Financial Coach - Hackathon")
orch = FinancialCoachOrchestrator()


class PlanRequest(BaseModel):
    input_mode: Literal["csv", "json"] = "csv"

    # csv mode
    debts_csv: Optional[str] = None
    transactions_csv: Optional[str] = None

    # json mode
    user_json_path: Optional[str] = None

    payoff_mode: PayoffMode = "balanced"

    @model_validator(mode="after")
    def validate_inputs(self):
        if self.input_mode == "csv":
            if not self.debts_csv or not self.transactions_csv:
                raise ValueError("For input_mode='csv', debts_csv and transactions_csv are required.")
        elif self.input_mode == "json":
            if not self.user_json_path:
                raise ValueError("For input_mode='json', user_json_path is required.")
        return self


@app.get("/health")
def health():
    return {"status": "ok"}


def _build_csv_profile(transactions) -> UserProfile:
    # Assumption: positive = income, negative = expense
    income = sum(float(t.amount) for t in transactions if float(t.amount) > 0)
    expenses = abs(sum(float(t.amount) for t in transactions if float(t.amount) < 0))

    savings_rate = 0.0
    if income > 0:
        savings_rate = max((income - expenses) / income, 0.0)

    return UserProfile(
        monthly_income=float(income),
        monthly_expenses=float(expenses),
        savings_rate=float(savings_rate),
        risk_tolerance="moderate",
        dependents=0,
    )


# Keep all common endpoint variants to avoid 404 from UI clients
@app.post("/generate-plan")
@app.post("/generate_plan")
@app.post("/api/generate-plan")
def generate_plan(request: PlanRequest):
    try:
        if request.input_mode == "json":
            profile, debts, transactions, metadata = normalize_to_legacy_context(request.user_json_path)
        else:
            debts = load_debts_csv(request.debts_csv)
            transactions = load_transactions_csv(request.transactions_csv)
            profile = _build_csv_profile(transactions)
            metadata = {
                "source": "csv",
                "debts_csv": request.debts_csv,
                "transactions_csv": request.transactions_csv,
            }

        context = AgentContext(
            profile=profile,
            debts=debts,
            transactions=transactions,
            metadata=metadata,
        )

        # FIX: use instance 'orch', not module 'orchestrator'
        result = orch.run(context=context, payoff_mode=request.payoff_mode)
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))