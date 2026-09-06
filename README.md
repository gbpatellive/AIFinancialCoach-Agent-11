# AI Financial Coach

AI Financial Coach is a personal finance assistant focused on debt analysis, payoff strategy guidance, and educational financial insights.  
It ingests transaction and debt data, runs specialized agents, and exposes recommendations through an API and dashboard.

## Project Goal

Build a practical, education-first financial coaching system that helps users:

- Understand current debt position and repayment risk
- Compare payoff approaches (for example, avalanche-style strategies)
- Track spending and cash-flow patterns
- Receive clear, non-advisory guidance for better financial decisions

## High-Level Architecture

- **Agent Layer**: Modular agents generate structured insights (example: [`app.agents.debt_analyzer_agent.DebtAnalyzerAgent`](app/agents/debt_analyzer_agent.py))
- **Data Layer**: CSV ingestion and normalization pipeline (see [app/data](app/data))
- **Model Layer**: Shared Pydantic schemas for context and outputs (see [app/models/schemas.py](app/models/schemas.py))
- **API Layer**: FastAPI endpoints for programmatic access (see [app/api](app/api))
- **UI Layer**: Streamlit dashboard for interactive usage (see [app/dashboard.py](app/dashboard.py))

## Tech Stack

- **Language**: Python 3.x
- **API Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Data Processing**: Pandas
- **Validation/Schema**: Pydantic
- **Dashboard**: Streamlit
- **HTTP Client**: Requests
- **Environment/Bootstrap**: PowerShell scripts for local setup and run

Dependencies are defined in [requirements.txt](requirements.txt).  
Bootstrap and run scripts are available in [bootstrap.ps1](bootstrap.ps1), [run_api.ps1](run_api.ps1), and [run_dashboard.ps1](run_dashboard.ps1).

## Key Data Contracts

Primary shared structures are defined in [`app.models.schemas`](app/models/schemas.py), including:

- `UserProfile`
- `AgentContext`
- `AgentOutput`
- Debt/transaction domain models

These contracts keep agent outputs consistent across API and dashboard consumers.

## Current Agent Example

The debt analysis flow is implemented in [`app.agents.debt_analyzer_agent.DebtAnalyzerAgent`](app/agents/debt_analyzer_agent.py), which computes:

- Total debt balance
- Total monthly minimum payment
- Weighted APR
- Risk classification (`low` / `medium` / `high`)

## Run Locally

1. Create and activate a virtual environment
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start API:
   - `./run_api.ps1`
4. Start dashboard:
   - `./run_dashboard.ps1`

## Notes

- This project provides educational financial guidance.
- It is not legal, tax, or investment advice.

-Test