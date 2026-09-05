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
