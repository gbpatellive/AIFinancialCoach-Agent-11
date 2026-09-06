import json
import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import requests
import streamlit as st

DEFAULT_API_BASE = "http://127.0.0.1:8000"

def _discover_generate_plan_url(base_url: str) -> str:
    # Try OpenAPI first
    try:
        r = requests.get(f"{base_url}/openapi.json", timeout=10)
        r.raise_for_status()
        spec = r.json()
        paths = (spec or {}).get("paths", {}) or {}
        for p in paths.keys():
            if "generate" in p and "plan" in p:
                return f"{base_url}{p}"
    except Exception:
        pass

    # Fallback candidates
    for p in ("/generate-plan", "/generate_plan", "/api/generate-plan"):
        try:
            # We only probe with OPTIONS to check route existence
            probe = requests.options(f"{base_url}{p}", timeout=5)
            if probe.status_code not in (404,):
                return f"{base_url}{p}"
        except Exception:
            pass

    return f"{base_url}/generate-plan"

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


# ----------------- UI -----------------
st.set_page_config(page_title="AI Financial Coach", page_icon="💸", layout="wide")

# Header row with top-right user id
h1, h2 = st.columns([4, 2])
with h1:
    st.title("💸 AI Financial Coach")
with h2:
    logged_user = load_logged_in_user()
    user_id = (logged_user or {}).get("username", "")
    st.markdown(
        f"<div style='text-align:right; margin-top: 14px;'><b>{user_id}</b></div>",
        unsafe_allow_html=True,
    )

st.caption("Financial plan generation based on logged-in user profile.")

if not logged_user:
    st.error("No valid login session found. Start the app using run_dashboard.ps1.")
    st.stop()

profile = logged_user.get("profile", {}) or {}
st.markdown(
    f"""
**Name:** {profile.get("first_name", "")} {profile.get("last_name", "")}  
**Aadhar:** {profile.get("aadhar_number", "")}  
**PAN:** {profile.get("pan_number", "")}
"""
)

user_json_path = resolve_user_json_path(logged_user)
st.text_input("Resolved User JSON Path", value=user_json_path, disabled=True)

payoff_mode = st.selectbox("Payoff Mode", ["conservative", "balanced", "aggressive"], index=1)

user_doc, json_err = _load_json(user_json_path)
json_summary = _compute_json_summary(user_doc)

derived_monthly_income = json_summary["monthly_income"] if json_summary["monthly_income"] > 0 else 100000.0
total_debt = json_summary["total_debt"]
total_min_payment = json_summary["total_min_payment"]
monthly_expenses = json_summary["monthly_expenses"]
avg_apr = json_summary["avg_apr"]
debt_accounts = json_summary["accounts"]
currency_symbol = "₹" if json_summary.get("currency", "INR") == "INR" else ""

monthly_income = st.number_input(
    "Monthly Income",
    min_value=0.0,
    value=float(derived_monthly_income),
    step=1000.0,
)

net_cashflow = monthly_income - monthly_expenses - total_min_payment
dti = (total_min_payment / monthly_income * 100.0) if monthly_income > 0 else 0.0

st.markdown("### Financial Position Snapshot")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Debt", f"{currency_symbol}{total_debt:,.2f}")
k2.metric("Min Debt Payment", f"{currency_symbol}{total_min_payment:,.2f}")
k3.metric("Monthly Expenses", f"{currency_symbol}{monthly_expenses:,.2f}")
k4.metric("Net Cashflow", f"{currency_symbol}{net_cashflow:,.2f}")
k5.metric("DTI", f"{dti:.2f}%")

r1, r2 = st.columns(2)
with r1:
    st.write(f"Debt Accounts: **{debt_accounts}**")
with r2:
    st.write(f"Avg APR: **{avg_apr:.2f}%**" if avg_apr is not None else "Avg APR: **N/A**")

if json_err:
    st.error(f"User JSON load error: {json_err}")

run = st.button("Generate Plan", type="primary", use_container_width=True)

if run:
    payload = {
        "input_mode": "json",
        "payoff_mode": payoff_mode,
        "user_json_path": user_json_path,
    }

    api_url = _discover_generate_plan_url(DEFAULT_API_BASE)

    try:
        resp = requests.post(api_url, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        st.success("Plan generated successfully.")
        st.subheader("Response")
        st.json(data)

        if isinstance(data, dict):
            if "headline" in data:
                st.subheader("Headline")
                st.json(data.get("headline"))

            if "next_actions" in data and isinstance(data.get("next_actions"), list):
                st.subheader("Next Actions")
                for i, action in enumerate(data.get("next_actions", []), start=1):
                    st.write(f"{i}. {action}")

            if "outputs" in data:
                st.subheader("Agent Outputs")
                st.json(data.get("outputs"))

    except requests.RequestException as ex:
        st.error(f"API call failed: {ex} (url tried: {api_url})")
    except Exception as ex:
        st.error(f"Unexpected error: {ex}")