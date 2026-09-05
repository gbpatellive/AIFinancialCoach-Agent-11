from collections import defaultdict


def monthly_cashflow(transactions):
    income = sum(t.amount for t in transactions if t.type == "income")
    expense = sum(t.amount for t in transactions if t.type == "expense")
    return {"income": round(income, 2), "expense": round(expense, 2), "disposable": round(income - expense, 2)}


def category_spend(transactions):
    spend = defaultdict(float)
    for t in transactions:
        if t.type == "expense":
            spend[t.category] += t.amount
    return dict(sorted(((k, round(v, 2)) for k, v in spend.items()), key=lambda x: x[1], reverse=True))


def mode_breakdown(transactions):
    breakdown = defaultdict(float)
    for t in transactions:
        breakdown[t.mode] += t.amount
    return dict(sorted(((k, round(v, 2)) for k, v in breakdown.items()), key=lambda x: x[1], reverse=True))
