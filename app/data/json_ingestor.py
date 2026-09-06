from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from app.models.schemas import (
    Debt,
    Transaction,
    UserProfile,
    UserFinancialDocument,
)


def _to_monthly(amount: float, frequency: str) -> float:
    freq = (frequency or "").lower().strip()
    if freq == "yearly":
        return amount / 12.0
    return amount


def load_user_financial_json(path: str) -> UserFinancialDocument:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"user_json_path not found: {path}")

    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return UserFinancialDocument.model_validate(raw)


def normalize_to_legacy_context(
    path: str,
) -> Tuple[UserProfile, List[Debt], List[Transaction], Dict]:
    doc = load_user_financial_json(path)

    monthly_income = sum(_to_monthly(i.amount, i.frequency) for i in doc.income_sources)
    monthly_expenses = sum(_to_monthly(e.amount, e.frequency) for e in doc.current_expenses)
    savings_rate = 0.0 if monthly_income <= 0 else max((monthly_income - monthly_expenses) / monthly_income, 0.0)

    profile = UserProfile(
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        savings_rate=savings_rate,
        risk_tolerance="moderate",  # safe default if not present in JSON
        dependents=doc.user.dependents,
    )

    debts: List[Debt] = []
    for d in doc.debts:
        debts.append(
            Debt(
                debt_name=d.name,
                balance=d.current_balance,
                interest_rate=d.apr or 0.0,
                minimum_payment=d.minimum_payment or d.monthly_payment or 0.0,
            )
        )

    # Synthetic monthly transactions for agents that expect transaction history
    today = date.today().replace(day=1).isoformat()
    transactions: List[Transaction] = []

    for i in doc.income_sources:
        transactions.append(
            Transaction(
                date=today,
                description=i.source,
                category="income",
                amount=_to_monthly(i.amount, i.frequency),
            )
        )

    for e in doc.current_expenses:
        transactions.append(
            Transaction(
                date=today,
                description=e.source,
                category=e.category,
                amount=-abs(_to_monthly(e.amount, e.frequency)),
            )
        )

    metadata = {
        "currency": doc.metadata.currency,
        "profile": doc.metadata.profile,
        "username": doc.username,
        "last_updated": doc.metadata.last_updated,
    }

    return profile, debts, transactions, metadata