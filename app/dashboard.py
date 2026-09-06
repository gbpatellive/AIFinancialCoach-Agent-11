import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import requests
import streamlit as st
import pandas as pd

from app.chat.coach_chat import FinancialCoachChat
from app.data.json_ingestor import normalize_to_legacy_context
from app.models.schemas import AgentContext, UserProfile

st.set_page_config(
    page_title="AI Financial Coach",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 0.75rem;
    }
    div[data-testid="column"]:nth-of-type(2) [data-testid="stVerticalBlock"] {
        position: sticky;
        top: 1rem;
        max-height: calc(100vh - 2rem);
        overflow-y: auto;
        padding: 0.5rem;
        border: 1px solid rgba(49, 51, 63, 0.2);
        border-radius: 0.75rem;
        background: rgba(240, 242, 246, 0.4);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi! I'm your **AI Financial Coach**. Ask me about debt, spending, "
                "cashflow, savings, or your payoff plan.\n\n"
                "Try: *What's my debt situation?* or *How long until I'm debt-free?*"
            ),
        }
    ]

if "plan_data" not in st.session_state:
    st.session_state.plan_data = None

DEFAULT_API_BASE = "http://127.0.0.1:8000"

def load_logged_in_user() -> Optional[dict]:
    session_file = os.getenv(
        "AIFC_SESSION_FILE",
        os.path.join(os.path.dirname(__file__), "session", "current_user.json"),
    )
    if not os.path.exists(session_file):
        return None

    # Try common encodings used by PowerShell output
    for enc in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le"):
        try:
            with open(session_file, "r", encoding=enc) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    return None


def resolve_user_json_path(logged_user: dict) -> str:
    """
    Resolve user profile JSON path in this priority:
    1) logged_user["user_json_path"]
    2) logged_user["profile"]["user_json_path"]
    3) data/<username>.json
    """
    username = (logged_user or {}).get("username", "")
    profile = (logged_user or {}).get("profile", {}) or {}

    explicit = (logged_user or {}).get("user_json_path") or profile.get("user_json_path")
    if explicit:
        return explicit

    project_root = Path(__file__).resolve().parent.parent
    return str(project_root / "data" / f"{username}.json")


def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    cols = {c.lower().strip(): c for c in df.columns}
    for c in candidates:
        key = c.lower().strip()
        if key in cols:
            return cols[key]
    return None


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _load_json(path: str) -> Tuple[Optional[dict], Optional[str]]:
    if not path:
        return None, "Empty JSON path"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as ex:
        return None, str(ex)


def _to_monthly(amount: float, frequency: str) -> float:
    freq = (frequency or "").lower().strip()
    if freq == "yearly":
        return float(amount) / 12.0
    return float(amount)


def _format_currency(amount: float, currency: str = "INR") -> str:
    """Format the dashboard's monetary values without exposing raw floats."""
    symbol = "₹" if currency.upper() == "INR" else f"{currency.upper()} "
    return f"{symbol}{float(amount or 0):,.0f}"


def _frequency_label(frequency: str) -> str:
    """Make source frequencies readable while preserving the JSON value."""
    value = (frequency or "monthly").strip().lower()
    return {"monthly": "per month", "yearly": "per year"}.get(value, value)


def _compute_json_summary(user_doc: Optional[dict]) -> dict:
    summary = {
        "monthly_income": 0.0,
        "monthly_expenses": 0.0,
        "total_debt": 0.0,
        "total_min_payment": 0.0,
        "avg_apr": None,
        "accounts": 0,
        "currency": "INR",
    }
    if not user_doc:
        return summary

    metadata = user_doc.get("metadata", {}) or {}
    summary["currency"] = metadata.get("currency", "INR")

    incomes = user_doc.get("income_sources", []) or []
    expenses = user_doc.get("current_expenses", []) or []
    debts = user_doc.get("debts", []) or []

    summary["monthly_income"] = float(
        sum(_to_monthly(x.get("amount", 0.0), x.get("frequency", "monthly")) for x in incomes)
    )
    summary["monthly_expenses"] = float(
        sum(_to_monthly(x.get("amount", 0.0), x.get("frequency", "monthly")) for x in expenses)
    )

    total_debt = 0.0
    total_min_payment = 0.0
    apr_values: list[float] = []

    for d in debts:
        bal = float(d.get("current_balance", 0.0) or 0.0)
        total_debt += bal

        min_pay = d.get("minimum_payment", None)
        if min_pay is None:
            min_pay = d.get("monthly_payment", 0.0)
        total_min_payment += float(min_pay or 0.0)

        apr = d.get("apr", None)
        if apr is not None:
            apr_values.append(float(apr))

    summary["total_debt"] = total_debt
    summary["total_min_payment"] = total_min_payment
    summary["accounts"] = int(len(debts))
    summary["avg_apr"] = float(sum(apr_values) / len(apr_values)) if apr_values else None
    return summary


def _find_emergency_fund_goal(user_doc: Optional[dict]) -> float:
    """Return the emergency-fund target when it has been captured as a goal."""
    for goal in (user_doc or {}).get("financial_goals", []) or []:
        goal_name = str(goal.get("goal", "")).lower()
        if "emergency" in goal_name and "fund" in goal_name:
            return float(goal.get("target_amount", 0.0) or 0.0)
    return 0.0


def _compute_expense_summary(tx_df: pd.DataFrame | None) -> dict:
    summary = {"monthly_expenses": 0.0, "method": "not_available", "amount_col": None}
    if tx_df is None or tx_df.empty:
        return summary

    amount_col = _find_col(tx_df, ["amount", "txn_amount", "transaction_amount", "value"])
    type_col = _find_col(tx_df, ["type", "transaction_type", "dr_cr", "direction", "kind"])

    if not amount_col:
        return summary

    amounts = _to_numeric(tx_df[amount_col])
    monthly_expenses = 0.0
    method = "all_amounts_sum"

    if type_col:
        t = tx_df[type_col].astype(str).str.lower().str.strip()
        expense_mask = t.isin(["expense", "debit", "dr", "outflow"])
        if expense_mask.any():
            monthly_expenses = float(amounts[expense_mask].abs().sum())
            method = "type_filtered"
        else:
            negatives = amounts[amounts < 0]
            monthly_expenses = float(negatives.abs().sum()) if len(negatives) else float(amounts.abs().sum())
            method = "negative_or_abs_fallback"
    else:
        negatives = amounts[amounts < 0]
        monthly_expenses = float(negatives.abs().sum()) if len(negatives) else float(amounts.abs().sum())
        method = "negative_or_abs_fallback"

    summary["monthly_expenses"] = monthly_expenses
    summary["method"] = method
    summary["amount_col"] = amount_col
    return summary


def _api_base_url(raw_url: str) -> str:
    return raw_url.rstrip("/").removesuffix("/plan")


def _local_chat_reply(
    user_id: str,
    user_json_path: str,
    message: str,
    plan_data: dict | None,
) -> str:
    profile, debts, transactions, metadata = normalize_to_legacy_context(user_json_path)
    profile = profile.model_copy(update={"user_id": user_id or profile.user_id})
    ctx = AgentContext(profile=profile, debts=debts, transactions=transactions, metadata=metadata)
    return FinancialCoachChat().respond(message, ctx, plan_data)


def _send_chat_message(
    api_base: str,
    user_id: str,
    user_json_path: str,
    message: str,
    plan_data: dict | None,
) -> str:
    payload = {
        "user_id": user_id,
        "message": message,
        "user_json_path": user_json_path,
        "plan_context": plan_data,
    }
    response = requests.post(f"{api_base}/chat", json=payload, timeout=60)
    if response.status_code == 404:
        raise requests.HTTPError(
            "Chat endpoint not found. Restart the API with run_api.ps1 to load /chat.",
            response=response,
        )
    if response.status_code != 200:
        raise requests.HTTPError(response.text, response=response)
    return response.json()["reply"]


def _coach_reply(
    api_base: str,
    user_id: str,
    user_json_path: str,
    message: str,
    plan_data: dict | None,
) -> str:
    try:
        return _send_chat_message(
            api_base,
            user_id,
            user_json_path,
            message,
            plan_data,
        )
    except requests.RequestException:
        reply = _local_chat_reply(
            user_id,
            user_json_path,
            message,
            plan_data,
        )
        return (
            "*Using local coach (API unavailable — restart `run_api.ps1` for API mode).*\n\n"
            f"{reply}"
        )

# ----------------- UI -----------------
logged_user = load_logged_in_user()
if not logged_user:
    st.error("No valid login session found. Start the app using run_dashboard.ps1.")
    st.stop()

user_id = logged_user.get("username", "")
profile = logged_user.get("profile", {}) or {}
user_json_path = resolve_user_json_path(logged_user)
user_doc, json_err = _load_json(user_json_path)
json_summary = _compute_json_summary(user_doc)

monthly_income = json_summary["monthly_income"]
monthly_expenses = json_summary["monthly_expenses"]
total_debt = json_summary["total_debt"]
total_min_payment = json_summary["total_min_payment"]
currency = json_summary["currency"]
net_cashflow = monthly_income - monthly_expenses - total_min_payment
dti = (total_min_payment / monthly_income * 100.0) if monthly_income else 0.0

main_col, chat_col = st.columns([2.2, 1], gap="large")

with main_col:
    st.title("💸 AI Financial Coach")
    st.caption("Financial plan generation based on your logged-in financial profile.")
    st.markdown(
        f"**{profile.get('first_name', '')} {profile.get('last_name', '')}** · `{user_id}`"
    )
    if json_err:
        st.error(f"Could not load the financial profile: {json_err}")
    else:
        st.caption(f"Profile data: {user_json_path}")

    incomes = (user_doc or {}).get("income_sources", []) or []
    expenses = (user_doc or {}).get("current_expenses", []) or []
    debts = (user_doc or {}).get("debts", []) or []
    investments = (user_doc or {}).get("investments", []) or []
    cash_and_savings = (user_doc or {}).get("cash_and_savings", {}) or {}
    current_balance = float(cash_and_savings.get("current_balance", 0.0) or 0.0)
    emergency_fund = float(cash_and_savings.get("emergency_fund", 0.0) or 0.0)
    total_investments = sum(
        float(investment.get("current_value", 0.0) or 0.0) for investment in investments
    )
    emergency_fund_target = _find_emergency_fund_goal(user_doc)

    income_card, expense_card = st.columns(2, gap="medium")
    with income_card:
        with st.container(border=True):
            st.subheader("Income sources")
            st.metric("Monthly total", _format_currency(monthly_income, currency))
            if incomes:
                income_df = pd.DataFrame(
                    [
                        {
                            "Source": item.get("source", "Income"),
                            "Amount": _format_currency(item.get("amount", 0.0), currency),
                            "Frequency": _frequency_label(item.get("frequency", "monthly")),
                            "Type": str(item.get("type", "")).capitalize(),
                        }
                        for item in incomes
                    ]
                )
                st.dataframe(income_df, use_container_width=True, hide_index=True)
            else:
                st.info("No income sources recorded.")

    with expense_card:
        with st.container(border=True):
            st.subheader("Expense sources")
            st.metric("Monthly total", _format_currency(monthly_expenses, currency))
            if expenses:
                expense_df = pd.DataFrame(
                    [
                        {
                            "Source": item.get("source", "Expense"),
                            "Amount": _format_currency(item.get("amount", 0.0), currency),
                            "Frequency": _frequency_label(item.get("frequency", "monthly")),
                            "Category": str(item.get("category", "")).replace("_", " ").title(),
                            "Type": str(item.get("type", "")).capitalize(),
                        }
                        for item in expenses
                    ]
                )
                st.dataframe(expense_df, use_container_width=True, hide_index=True)
            else:
                st.info("No expense sources recorded.")

    debt_card, goals_card = st.columns(2, gap="medium")
    with debt_card:
        with st.container(border=True):
            st.subheader("Outstanding debt")
            st.metric("Total outstanding", _format_currency(total_debt, currency))
            if debts:
                debt_df = pd.DataFrame(
                    [
                        {
                            "Debt": item.get("name", "Debt"),
                            "Outstanding": _format_currency(item.get("current_balance", 0.0), currency),
                            "EMI": _format_currency(
                                item.get("minimum_payment") or item.get("monthly_payment", 0.0),
                                currency,
                            ),
                            "Frequency": _frequency_label(item.get("payment_frequency", "monthly")),
                            "Remaining term": (
                                f"{item['remaining_term_months']} months"
                                if item.get("remaining_term_months") is not None
                                else "Not provided"
                            ),
                        }
                        for item in debts
                    ]
                )
                st.dataframe(debt_df, use_container_width=True, hide_index=True)
            else:
                st.info("No outstanding debts recorded.")

    with goals_card:
        with st.container(border=True):
            st.subheader("Financial goals")
            financial_goals = (user_doc or {}).get("financial_goals", []) or []
            if financial_goals:
                goals_df = pd.DataFrame(
                    [
                        {
                            "Goal": item.get("goal", "Financial goal"),
                            "Target": _format_currency(item.get("target_amount", 0.0), currency),
                            "Saved": _format_currency(item.get("current_amount", 0.0), currency),
                            "Horizon": item.get("horizon_years", "Not provided"),
                            "Priority": str(item.get("priority", "")).capitalize(),
                        }
                        for item in financial_goals
                    ]
                )
                st.dataframe(goals_df, use_container_width=True, hide_index=True)
            else:
                st.info("No financial goals recorded.")

    with st.container(border=True):
        st.subheader("Savings & investments")
        savings_summary, investment_summary = st.columns(2)
        with savings_summary:
            st.metric("Cash & savings", _format_currency(current_balance, currency))
            st.write(f"**Emergency fund** · {_format_currency(emergency_fund, currency)}")
        with investment_summary:
            st.metric("Investments", _format_currency(total_investments, currency))

        if emergency_fund_target:
            progress = min(emergency_fund / emergency_fund_target, 1.0)
            st.progress(progress)
            st.caption(
                f"Emergency fund: {_format_currency(emergency_fund, currency)} of "
                f"{_format_currency(emergency_fund_target, currency)} target "
                f"({progress:.0%})"
            )
        else:
            st.caption("Set an emergency-fund goal to track progress.")

        st.divider()
        st.markdown("**Investment holdings**")
        if investments:
            investment_df = pd.DataFrame(
                [
                    {
                        "Name": item.get("name", "Investment"),
                        "Type": str(item.get("type", "")).replace("_", " ").title(),
                        "Current value": _format_currency(item.get("current_value", 0.0), currency),
                        "Monthly contribution": _format_currency(
                            item.get("monthly_contribution", 0.0), currency
                        ),
                    }
                    for item in investments
                ]
            )
            st.dataframe(investment_df, use_container_width=True, hide_index=True)
        else:
            st.info("No investments recorded yet.")

    if st.button("Generate Plan", type="primary"):
        try:
            print(f"Generating plan for user: {user_json_path}")
            with st.spinner("Generating plan..."):
                print(f"Calling API at {DEFAULT_API_BASE}/generate_plan with user_json_path: {user_json_path}")
                resp = requests.post(
                    f"{DEFAULT_API_BASE}/generate_plan",
                    json={"user_json_path": user_json_path},
                    timeout=90,
                )
                print(f"API response status: {resp.status_code}, content: {resp.text}")
            resp.raise_for_status()
            st.session_state.plan_data = resp.json()
            st.success("Plan generated successfully.")
        except requests.RequestException as ex:
            st.error(f"API call failed: {ex}")

    data = st.session_state.plan_data
    if data:
        headline = data.get("headline", {})
        st.metric("Estimated Months to Debt-Free", headline.get("estimated_months_to_debt_free", "N/A"))
        tab1, tab2, tab3 = st.tabs(["Overview", "Agent Insights", "Raw JSON"])
        with tab1:
            compare_df = pd.DataFrame(
                {
                    "component": ["Income", "Expenses", "Debt Min Payment", "Net Cashflow"],
                    "amount": [monthly_income, monthly_expenses, total_min_payment, net_cashflow],
                }
            )
            st.bar_chart(compare_df.set_index("component")["amount"])
            for i, action in enumerate(data.get("next_actions", []), 1):
                st.write(f"{i}. {action}")
        with tab2:
            st.json(data.get("outputs", []))
        with tab3:
            st.json(data)

with chat_col:
    st.subheader("💬 AI Financial Coach")
    st.caption("Plan loaded" if st.session_state.plan_data else "Generate a plan for richer answers")
    chat_container = st.container(height=620)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Ask about debt, budget, or savings..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            with st.spinner("Thinking..."):
                reply = _coach_reply(
                    DEFAULT_API_BASE,
                    user_id,
                    user_json_path,
                    prompt,
                    st.session_state.plan_data,
                )
        except Exception as ex:
            reply = f"Sorry, I couldn't process that question.\n\n`{ex}`"
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "Chat cleared. How can I help with your finances?"}
        ]
        st.rerun()
