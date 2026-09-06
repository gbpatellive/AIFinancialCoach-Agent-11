from typing import Dict, List, Literal
from typing import Optional
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
Frequency = Literal["monthly", "yearly"]
FlowType = Literal["fixed", "variable"]
ExpenseType = Literal["essential", "discretionary"]
GoalHorizon = Literal["short_term", "mid_term", "long_term"]
Priority = Literal["low", "medium", "high"]


class MetaData(BaseModel):
    currency: str = "INR"
    profile: Optional[str] = None
    last_updated: Optional[str] = None


class UserInfo(BaseModel):
    name: str
    age: int
    occupation: Optional[str] = None
    dependents: int = 0


class IncomeSource(BaseModel):
    source: str
    amount: float
    frequency: Frequency
    type: FlowType


class CurrentExpense(BaseModel):
    source: str
    amount: float
    frequency: Frequency
    category: str
    type: ExpenseType


class DebtItem(BaseModel):
    name: str
    type: str
    current_balance: float
    monthly_payment: float = 0.0
    minimum_payment: float = 0.0
    payment_frequency: Frequency = "monthly"
    remaining_term_months: Optional[int] = None
    apr: Optional[float] = None


class InvestmentItem(BaseModel):
    name: str
    type: str
    current_value: float
    monthly_contribution: float = 0.0


class InsuranceItem(BaseModel):
    type: str
    cover: float
    premium: float
    payment_frequency: Frequency


class CashAndSavings(BaseModel):
    current_balance: float = 0.0
    emergency_fund: float = 0.0


class FinancialGoal(BaseModel):
    goal: str
    horizon: GoalHorizon
    horizon_years: str
    target_amount: float
    current_amount: float = 0.0
    priority: Priority


class UserFinancialDocument(BaseModel):
    metadata: MetaData
    username: str
    password: Optional[str] = None
    aadhar_number: Optional[str] = None
    Aadhar: Optional[str] = None
    pan_number: Optional[str] = None
    PAN: Optional[str] = None
    user: UserInfo
    income_sources: list[IncomeSource] = Field(default_factory=list)
    current_expenses: list[CurrentExpense] = Field(default_factory=list)
    debts: list[DebtItem] = Field(default_factory=list)
    investments: list[InvestmentItem] = Field(default_factory=list)
    insurance: list[InsuranceItem] = Field(default_factory=list)
    cash_and_savings: CashAndSavings = Field(default_factory=CashAndSavings)
    financial_goals: list[FinancialGoal] = Field(default_factory=list)
