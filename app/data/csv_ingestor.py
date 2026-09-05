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
