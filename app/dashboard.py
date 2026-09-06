import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests
import streamlit as st
import pandas as pd

from app.chat.coach_chat import FinancialCoachChat
from app.data.csv_ingestor import load_debts_csv, load_transactions_csv
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


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _load_csv(path: str) -> tuple[pd.DataFrame | None, str | None]:
    try:
        df = pd.read_csv(path)
        return df, None
    except Exception as ex:
        return None, str(ex)


def _compute_debt_summary(debts_df: pd.DataFrame | None) -> dict:
    summary = {
        "total_debt": 0.0,
        "total_min_payment": 0.0,
        "avg_apr": None,
        "accounts": 0,
        "balance_col": None,
        "min_col": None,
        "apr_col": None,
        "name_col": None,
    }
    if debts_df is None or debts_df.empty:
        return summary

    balance_col = _find_col(
        debts_df,
        ["balance", "outstanding_balance", "current_balance", "principal", "debt_amount", "amount"],
    )
    min_col = _find_col(
        debts_df,
        ["minimum_payment", "min_payment", "monthly_payment", "emi", "minimum_due"],
    )
    apr_col = _find_col(
        debts_df,
        ["apr", "interest_rate", "rate", "annual_rate"],
    )
    name_col = _find_col(
        debts_df,
        ["debt_name", "loan_name", "account_name", "lender", "bank", "name"],
    )

    if balance_col:
        summary["total_debt"] = float(_to_numeric(debts_df[balance_col]).sum())
    if min_col:
        summary["total_min_payment"] = float(_to_numeric(debts_df[min_col]).sum())
    if apr_col:
        apr_vals = _to_numeric(debts_df[apr_col])
        summary["avg_apr"] = float(apr_vals.mean()) if len(apr_vals) else None

    summary["accounts"] = int(len(debts_df))
    summary["balance_col"] = balance_col
    summary["min_col"] = min_col
    summary["apr_col"] = apr_col
    summary["name_col"] = name_col
    return summary


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
    monthly_income: float,
    payoff_mode: str,
    debts_csv: str,
    tx_csv: str,
    message: str,
    plan_data: dict | None,
) -> str:
    debts = load_debts_csv(debts_csv)
    transactions = load_transactions_csv(tx_csv)
    profile = UserProfile(
        user_id=user_id,
        monthly_income=monthly_income,
        region="global",
        payoff_mode=payoff_mode,
    )
    ctx = AgentContext(profile=profile, debts=debts, transactions=transactions)
    return FinancialCoachChat().respond(message, ctx, plan_data)


def _send_chat_message(
    api_base: str,
    user_id: str,
    monthly_income: float,
    payoff_mode: str,
    debts_csv: str,
    tx_csv: str,
    message: str,
    plan_data: dict | None,
) -> str:
    payload = {
        "user_id": user_id,
        "message": message,
        "monthly_income": monthly_income,
        "region": "global",
        "payoff_mode": payoff_mode,
        "debts_csv": debts_csv,
        "transactions_csv": tx_csv,
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
    monthly_income: float,
    payoff_mode: str,
    debts_csv: str,
    tx_csv: str,
    message: str,
    plan_data: dict | None,
) -> str:
    try:
        return _send_chat_message(
            api_base,
            user_id,
            monthly_income,
            payoff_mode,
            debts_csv,
            tx_csv,
            message,
            plan_data,
        )
    except requests.RequestException:
        reply = _local_chat_reply(
            user_id,
            monthly_income,
            payoff_mode,
            debts_csv,
            tx_csv,
            message,
            plan_data,
        )
        return (
            "*Using local coach (API unavailable — restart `run_api.ps1` for API mode).*\n\n"
            f"{reply}"
        )


with st.sidebar:
    st.header("Data Sources")
    debts_csv = st.text_input("Debts CSV path", r"data\sample_debts.csv")
    tx_csv = st.text_input("Transactions CSV path", r"data\sample_transactions.csv")
    st.divider()
    api_base = _api_base_url(st.text_input("API URL", "http://127.0.0.1:8000"))

main_col, chat_col = st.columns([2.4, 1], gap="large")

with main_col:
    st.title("💸 AI Financial Coach")
    st.caption("Clean view of your financial analysis from all agents.")

    st.subheader("Profile")
    c1, c2, c3 = st.columns(3)
    with c1:
        user_id = st.text_input("User ID", "demo-user")
    with c2:
        monthly_income = st.number_input(
            "Monthly Income",
            min_value=0.0,
            value=120000.0,
            step=1000.0,
            help="Total monthly take-home income.",
        )
    with c3:
        payoff_mode = st.selectbox("Payoff Mode", ["aggressive", "balanced", "conservative"], index=0)

    debts_df, debts_err = _load_csv(debts_csv)
    tx_df, tx_err = _load_csv(tx_csv)

    debt_summary = _compute_debt_summary(debts_df)
    expense_summary = _compute_expense_summary(tx_df)

    total_debt = debt_summary["total_debt"]
    monthly_expenses = expense_summary["monthly_expenses"]
    total_min_payment = debt_summary["total_min_payment"]

    net_cashflow = monthly_income - monthly_expenses - total_min_payment
    dti = (total_min_payment / monthly_income * 100.0) if monthly_income > 0 else 0.0

    st.markdown("### Financial Position Snapshot")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Total Debt", f"{total_debt:,.2f}")
    with k2:
        st.metric("Monthly Income", f"{monthly_income:,.2f}")
    with k3:
        st.metric("Monthly Expenses", f"{monthly_expenses:,.2f}")
    with k4:
        st.metric("Debt Payments (Min)", f"{total_min_payment:,.2f}")
    with k5:
        st.metric("Net Cashflow", f"{net_cashflow:,.2f}")

    r1, r2 = st.columns(2)
    with r1:
        st.metric("DTI % (Min Payment / Income)", f"{dti:.1f}%")
    with r2:
        if net_cashflow < 0:
            st.error("Risk: Monthly deficit detected. Consider reducing expenses or adjusting payoff mode.")
        else:
            st.success("Healthy: Monthly surplus available.")

    if debts_err:
        st.warning(f"Could not read debts CSV for preview: {debts_err}")
    if tx_err:
        st.warning(f"Could not read transactions CSV for preview: {tx_err}")

    run = st.button("Generate Plan", type="primary", use_container_width=True)

    if run:
        payload = {
            "user_id": user_id,
            "monthly_income": monthly_income,
            "region": "global",
            "payoff_mode": payoff_mode,
            "debts_csv": debts_csv,
            "transactions_csv": tx_csv,
        }

        try:
            with st.spinner("Generating plan..."):
                r = requests.post(f"{api_base}/plan", json=payload, timeout=60)

            if r.status_code != 200:
                st.error(r.text)
            else:
                data = r.json()
                st.session_state.plan_data = data
                st.success("Plan generated — ask the coach on the right about any insight.")

        except requests.RequestException as ex:
            st.error(f"Request failed: {ex}")

    data = st.session_state.plan_data
    if data:
        headline = data.get("headline", {})
        h1, h2, h3 = st.columns(3)
        with h1:
            st.metric("Monthly Income", f"{monthly_income:,.2f}")
        with h2:
            st.metric("Payoff Mode", payoff_mode.title())
        with h3:
            st.metric(
                "Estimated Months to Debt-Free",
                headline.get("estimated_months_to_debt_free", "N/A"),
            )

        tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Debt Details", "Agent Insights", "Raw JSON"])

        with tab1:
            st.subheader("Headline")
            st.json(headline)

            st.subheader("Income vs Outflow")
            compare_df = pd.DataFrame(
                {
                    "component": ["Income", "Expenses", "Debt Min Payment", "Net Cashflow"],
                    "amount": [monthly_income, monthly_expenses, total_min_payment, net_cashflow],
                }
            )
            st.dataframe(compare_df, use_container_width=True, hide_index=True)
            st.bar_chart(compare_df.set_index("component")["amount"])

            next_actions = data.get("next_actions", [])
            if next_actions:
                st.subheader("Next Actions")
                for i, action in enumerate(next_actions, 1):
                    st.write(f"{i}. {action}")

        with tab2:
            st.subheader("Debt Accounts")
            if debts_df is None or debts_df.empty:
                st.info("No debt CSV data available to display.")
            else:
                st.dataframe(debts_df, use_container_width=True, hide_index=True)

                balance_col = debt_summary["balance_col"]
                name_col = debt_summary["name_col"]

                if balance_col:
                    chart_df = debts_df.copy()
                    chart_df[balance_col] = _to_numeric(chart_df[balance_col])

                    if name_col:
                        by_debt = chart_df[[name_col, balance_col]].groupby(name_col, as_index=False).sum()
                        by_debt = by_debt.sort_values(balance_col, ascending=False)
                        st.subheader("Debt by Account")
                        st.bar_chart(by_debt.set_index(name_col)[balance_col])
                    else:
                        st.subheader("Debt Balances")
                        st.bar_chart(chart_df[balance_col])

        with tab3:
            outputs = data.get("outputs", [])
            if not outputs:
                st.info("No agent outputs found.")
            for item in outputs:
                st.markdown(f"### {item.get('agent_name', 'unknown_agent')}")
                st.write(item.get("summary", ""))

                details = item.get("details", {})
                if isinstance(details, dict) and details:
                    details_df = pd.DataFrame([{"field": k, "value": v} for k, v in details.items()])
                    st.dataframe(details_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No details available.")

                if item.get("agent_name") == "debt_payoff_optimizer":
                    schedule = details.get("schedule_preview_first_12_months", [])
                    if schedule:
                        df = pd.DataFrame(schedule)
                        if "month" in df.columns and "remaining_balance" in df.columns:
                            st.line_chart(df.set_index("month")["remaining_balance"])

        with tab4:
            st.json(data)

with chat_col:
    st.markdown("### 💬 Financial Coach")
    plan_status = "Plan loaded" if st.session_state.plan_data else "No plan yet — generate one for richer answers"
    st.caption(plan_status)

    chat_container = st.container(height=520)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Ask about debt, budget, savings, payoff..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        try:
            with st.spinner("Thinking..."):
                reply = _coach_reply(
                    api_base,
                    user_id,
                    monthly_income,
                    payoff_mode,
                    debts_csv,
                    tx_csv,
                    prompt,
                    st.session_state.plan_data,
                )
        except Exception as ex:
            reply = (
                "Sorry, I couldn't process that question. "
                "Check your CSV paths in the sidebar and try again.\n\n"
                f"`{ex}`"
            )

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Chat cleared. Ask me about your debt, spending, cashflow, "
                    "or payoff strategy anytime."
                ),
            }
        ]
        st.rerun()
