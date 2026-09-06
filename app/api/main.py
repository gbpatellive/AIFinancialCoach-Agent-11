from typing import Any

from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator
from app.chat.coach_chat import FinancialCoachChat

from app.data.json_ingestor import normalize_to_legacy_context
from app.models.schemas import AgentContext, PayoffMode, UserProfile
from app.orchestrator import FinancialCoachOrchestrator

app = FastAPI(title="AI Financial Coach - Hackathon")
orch = FinancialCoachOrchestrator()
chat = FinancialCoachChat()


class PlanRequest(BaseModel):
    user_json_path: str
    payoff_mode: PayoffMode = "balanced"
    @model_validator(mode="after")
    def validate_inputs(self):
        if not self.user_json_path.strip():
            raise ValueError("user_json_path is required.")
        return self


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str
    payoff_mode: PayoffMode = "aggressive"
    user_json_path: str
    plan_context: dict[str, Any] | None = Field(
        default=None,
        description="Optional cached plan response from /plan for richer chat answers.",
    )

@app.on_event("startup")
def show_routes():
    print("Registered routes:")
    for r in app.routes:
        print(f"{sorted(getattr(r, 'methods', []))} {r.path}")
        
@app.get("/health")
def health():
    return {"status": "ok"}


# Keep all common endpoint variants to avoid 404 from UI clients
@app.post("/generate_plan")
def generate_plan(request: PlanRequest):
    print(f"Received request: {request}")
    try:
        profile, debts, transactions, metadata = normalize_to_legacy_context(request.user_json_path)
        profile = profile.model_copy(update={"payoff_mode": request.payoff_mode})

        context = AgentContext(
            profile=profile,
            debts=debts,
            transactions=transactions,
            metadata=metadata,
        )

        # FIX: use instance 'orch', not module 'orchestrator'
        result = orch.run(context)
        print(f"Generated plan: {result}")
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/chat")
def chat_with_coach(req: ChatRequest):
    try:
        profile, debts, transactions, metadata = normalize_to_legacy_context(req.user_json_path)
        profile = profile.model_copy(
            update={"user_id": req.user_id or profile.user_id, "payoff_mode": req.payoff_mode}
        )
        ctx = AgentContext(profile=profile, debts=debts, transactions=transactions, metadata=metadata)
        reply = chat.respond(req.message, ctx, req.plan_context)

        return {
            "user_id": req.user_id,
            "message": req.message,
            "reply": reply,
            "has_plan_context": req.plan_context is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
