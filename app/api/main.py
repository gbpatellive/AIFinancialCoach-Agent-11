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
