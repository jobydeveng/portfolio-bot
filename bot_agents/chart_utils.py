"""
Chart Generation Utilities
Functions to render charts from specifications
"""

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Category colors (consistent with original bot)
CATEGORY_COLORS = {
    "Mutual Funds": "#4e8ef7",
    "FD": "#f7c948",
    "RD": "#e67e22",
    "Stocks": "#e74c3c",
    "Gold": "#ffcc00",
    "PF": "#27ae60",
    "NPS": "#3498db",
    "US Stocks": "#9b59b6",
    "Crypto": "#1abc9c",
}


def fmt_inr(val: float) -> str:
    """Format Indian rupees value"""
    if val >= 1_00_000:
        return f"Rs.{val/1_00_000:.2f}L"
    elif val >= 1000:
        return f"Rs.{val/1000:.1f}K"
    return f"Rs.{val:,.0f}"


def generate_pie_chart(cats: dict, title: str) -> io.BytesIO:
    """Generate donut pie chart"""
    fig, ax = plt.subplots(figsize=(8, 6), facecolor="#0a1628")
    ax.set_facecolor("#0a1628")
    labels = list(cats.keys())
    values = list(cats.values())
    colors = [CATEGORY_COLORS.get(l, "#888888") for l in labels]
    wedges, _, autotexts = ax.pie(
        values, labels=None, colors=colors, autopct="%1.1f%%",
        startangle=140, pctdistance=0.75,
        wedgeprops=dict(width=0.6, edgecolor="#0a1628", linewidth=2),
    )
    for at in autotexts:
        at.set_color("white"); at.set_fontsize(9)
    ax.legend(wedges, [f"{l}: {fmt_inr(v)}" for l, v in zip(labels, values)],
              loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2,
              fontsize=8, facecolor="#0f2140", edgecolor="#2a5298", labelcolor="white")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=15)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf


def generate_bar_chart(cats: dict, title: str) -> io.BytesIO:
    """Generate horizontal bar chart"""
    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    labels = list(cats.keys())
    values = [v / 1_00_000 for v in cats.values()]
    colors = [CATEGORY_COLORS.get(l, "#888888") for l in labels]
    bars = ax.barh(labels, values, color=colors, edgecolor="#0a1628", height=0.6)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f"Rs.{val:.2f}L", va="center", color="white", fontsize=9)
    ax.set_xlabel("Value (Lakhs)", color="#8ab4d4")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white"); ax.spines[:].set_color("#1e3a5f")
    ax.grid(axis="x", color="#1e3a5f", linestyle="--", alpha=0.5)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf


def generate_trend_chart(all_data: list) -> io.BytesIO:
    """Generate portfolio growth trend chart"""
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    months = [d["month"] for d in all_data]
    totals = [d["total"] / 1_00_000 for d in all_data]
    ax.plot(months, totals, color="#4e8ef7", linewidth=2.5, marker="o",
            markersize=8, markerfacecolor="white", markeredgecolor="#4e8ef7")
    ax.fill_between(months, totals, alpha=0.15, color="#4e8ef7")
    for m, t in zip(months, totals):
        ax.annotate(f"Rs.{t:.2f}L", (m, t), textcoords="offset points",
                    xytext=(0, 10), ha="center", color="white", fontsize=8)
    ax.set_title("Portfolio Growth", color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white"); plt.xticks(rotation=20, ha="right")
    ax.set_ylabel("Value (Lakhs)", color="#8ab4d4"); ax.spines[:].set_color("#1e3a5f")
    ax.grid(color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf


def generate_comparison_chart(d1: dict, d2: dict, month1: str, month2: str) -> io.BytesIO:
    """Generate side-by-side comparison chart for two months"""
    cats = list(set(list(d1["cats"].keys()) + list(d2["cats"].keys())))
    x = np.arange(len(cats)); w = 0.35
    v1 = [d1["cats"].get(c, 0) / 1_00_000 for c in cats]
    v2 = [d2["cats"].get(c, 0) / 1_00_000 for c in cats]
    fig, ax = plt.subplots(figsize=(11, 6), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    ax.bar(x - w/2, v1, w, label=month1, color="#4e8ef7", edgecolor="#0a1628")
    ax.bar(x + w/2, v2, w, label=month2, color="#4caf82", edgecolor="#0a1628")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=20, ha="right", color="white", fontsize=8)
    ax.set_ylabel("Value (Lakhs)", color="#8ab4d4")
    ax.set_title(f"Comparison: {month1} vs {month2}", color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white")
    ax.legend(facecolor="#0f2140", edgecolor="#2a5298", labelcolor="white")
    ax.spines[:].set_color("#1e3a5f"); ax.grid(axis="y", color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf


def generate_stock_pl_chart() -> io.BytesIO:
    """Generate P&L chart for individual stock holdings (hardcoded data)"""
    stocks = {
        "GOLDBEES": 105.95, "GOLDIETF": 60.29, "SBIN": 57.56,
        "MON100": 52.82, "BAJFIN": 42.96, "ICICIBANK": 30.11,
        "AXISBANK": 23.44, "NESTLEIND": 11.11, "BANKBEES": 9.79,
        "NIFTYBEES": 8.27, "KOTAKBANK": 4.59, "HDFCBANK": 2.46,
        "ITBEES": 1.02, "IDFCFIRSTB": -5.52, "JIOFIN": -9.18,
        "SBICARD": -9.25, "HINDUNILVR": -9.11, "HDFCLIFE": -4.49,
        "RELIANCE": -5.96, "ITC": -19.77, "AAVAS": -10.62,
        "ASIANPAINT": -17.34, "KWIL": -46.59, "HAPPSTMNDS": -72.73,
    }
    sorted_stocks = dict(sorted(stocks.items(), key=lambda x: x[1], reverse=True))
    labels = list(sorted_stocks.keys())
    values = list(sorted_stocks.values())
    colors = ["#4caf82" if v >= 0 else "#f44336" for v in values]

    fig, ax = plt.subplots(figsize=(12, 8), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    bars = ax.barh(labels, values, color=colors, edgecolor="#0a1628", height=0.7)
    for bar, val in zip(bars, values):
        xpos = bar.get_width() + (0.5 if val >= 0 else -0.5)
        ax.text(xpos, bar.get_y() + bar.get_height()/2,
                f"{val:+.1f}%", va="center", color="white", fontsize=8,
                ha="left" if val >= 0 else "right")
    ax.axvline(0, color="white", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("P&L %", color="#8ab4d4")
    ax.set_title("Stock Holdings — P&L %", color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white"); ax.spines[:].set_color("#1e3a5f")
    ax.grid(axis="x", color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf


def render_chart_from_spec(chart_spec: dict) -> io.BytesIO:
    """
    Render a chart from agent-generated specification

    Args:
        chart_spec: Dict with "chart_type", "data", "title", etc.

    Returns:
        BytesIO buffer with PNG image
    """
    chart_type = chart_spec.get("chart_type")
    data = chart_spec.get("data", {})
    title = chart_spec.get("title", "Chart")

    if chart_type == "pie":
        return generate_pie_chart(data.get("categories", {}), title)
    elif chart_type == "bar":
        return generate_bar_chart(data.get("categories", {}), title)
    elif chart_type == "trend":
        return generate_trend_chart(data.get("history", []))
    elif chart_type == "comparison":
        return generate_comparison_chart(
            data.get("month1_data", {}),
            data.get("month2_data", {}),
            data.get("month1_name", "Month 1"),
            data.get("month2_name", "Month 2")
        )
    elif chart_type == "stock_pl":
        return generate_stock_pl_chart()
    else:
        raise ValueError(f"Unknown chart type: {chart_type}")
