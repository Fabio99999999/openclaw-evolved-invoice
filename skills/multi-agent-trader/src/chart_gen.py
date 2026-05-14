"""Chart generator for stock analysis — candlestick, volume, moving averages."""

import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

# Try matplotlib; fail gracefully if not installed
_CHART_ENABLED = False
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker
    from matplotlib.patches import Rectangle
    from matplotlib.font_manager import FontProperties

    # Set CJK font
    _CJK_FONTS = ["PingFang HK", "PingFang SC", "Heiti TC", "STHeiti", "SimSong", "AppleGothic"]
    _CJK_FONT = None
    for _fname in _CJK_FONTS:
        try:
            _CJK_FONT = FontProperties(family=_fname)
            plt.rcParams["font.family"] = _fname
            plt.rcParams["axes.unicode_minus"] = False
            _CJK_FONT = _fname
            break
        except Exception:
            continue

    _CHART_ENABLED = True
except ImportError:
    logger.warning("matplotlib not installed, chart generation disabled. pip install matplotlib")

CHART_DIR = os.path.expanduser("~/.openclaw/workspace/skills/multi-agent-trader/charts")


def _ensure_dir():
    os.makedirs(CHART_DIR, exist_ok=True)


def generate_candlestick_chart(
    df,
    stock_name: str = "",
    stock_code: str = "",
    ma_periods: tuple = (5, 10, 20),
    output_path: Optional[str] = None,
) -> Optional[str]:
    """Generate a candlestick + volume + MA chart from a DataFrame.

    Args:
        df: DataFrame with columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 涨跌幅
        stock_name: Stock name for title
        stock_code: Stock code
        ma_periods: Moving average periods
        output_path: Specific output path (auto-generated if None)

    Returns:
        Path to the generated PNG file, or None on failure.
    """
    if not _CHART_ENABLED:
        return None
    if df is None or df.empty:
        return None

    try:
        _ensure_dir()

        # Prepare data
        chart_df = df.sort_values("日期").tail(120)  # Last 120 periods
        dates = chart_df["日期"].tolist()
        opens = chart_df["开盘"].tolist()
        highs = chart_df["最高"].tolist()
        lows = chart_df["最低"].tolist()
        closes = chart_df["收盘"].tolist()
        volumes = chart_df["成交量"].tolist()

        # Parse dates
        import pandas as pd
        date_objs = pd.to_datetime(dates) if hasattr(dates[0], 'strftime') else [pd.to_datetime(str(d)) for d in dates]

        # Create figure with 2 subplots: price + volume
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                       gridspec_kw={"height_ratios": [3, 1]},
                                       sharex=True)
        fig.patch.set_facecolor("#1a1a2e")
        ax1.set_facecolor("#1a1a2e")
        ax2.set_facecolor("#1a1a2e")

        # ── Price candles ──
        width = 0.6
        for i in range(len(chart_df)):
            color = "#e74c3c" if closes[i] < opens[i] else "#2ecc71"
            # Candle body
            ax1.plot([date_objs[i], date_objs[i]], [lows[i], highs[i]],
                     color=color, linewidth=1, alpha=0.7)
            ax1.bar(date_objs[i], abs(closes[i] - opens[i]),
                    bottom=min(opens[i], closes[i]),
                    width=width, color=color, alpha=0.9)

        # Moving averages
        _all = list(zip(date_objs, closes))
        for period, color, style in [(5, "#f39c12", "-"), (10, "#3498db", "-"), (20, "#e91e63", "-")]:
            if len(_all) < period:
                continue
            ma_vals = []
            ma_dates = []
            for i in range(len(_all) - period + 1):
                ma_vals.append(sum(c for _, c in _all[i:i+period]) / period)
                ma_dates.append(_all[i + period - 1][0])
            ax1.plot(ma_dates, ma_vals, color=color, linewidth=1.2, alpha=0.7,
                     label=f"MA{period}")

        # Current price annotation
        if closes:
            latest_close = closes[-1]
            prev_close = closes[-2] if len(closes) > 1 else latest_close
            change_pct = ((latest_close - prev_close) / prev_close) * 100 if prev_close else 0
            arrow_color = "#2ecc71" if change_pct >= 0 else "#e74c3c"
            ax1.annotate(f"{latest_close:.2f} ({change_pct:+.2f}%)",
                         xy=(date_objs[-1], latest_close),
                         xytext=(10, 10), textcoords="offset points",
                         fontsize=12, fontweight="bold",
                         color=arrow_color,
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="#1a1a2e",
                                   edgecolor=arrow_color, alpha=0.8))

        ax1.set_title(f"{stock_name} ({stock_code})\nCandlestick Chart",
                      fontsize=14, fontweight="bold", color="white", pad=15)
        ax1.legend(loc="upper left", fontsize=9, framealpha=0.7)
        ax1.grid(True, alpha=0.15, color="white")
        ax1.tick_params(colors="white", labelsize=9)
        ax1.set_ylabel("Price", fontsize=10, color="white")

        # ── Volume bars ──
        max_vol = max(volumes)
        for i in range(len(chart_df)):
            color = "#e74c3c" if closes[i] < opens[i] else "#2ecc71"
            ax2.bar(date_objs[i], volumes[i] / max_vol,
                    width=width, color=color, alpha=0.5)

        ax2.axhline(y=0.5, color="white", linewidth=0.5, alpha=0.2, linestyle="--")
        ax2.set_ylabel("Volume", fontsize=10, color="white")
        ax2.tick_params(colors="white", labelsize=9)
        ax2.grid(True, alpha=0.15, color="white")

        # Date axis
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax2.xaxis.set_major_locator(mdates.WeekdayLocator())
        fig.autofmt_xdate(rotation=45)

        plt.tight_layout()

        # Save
        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(CHART_DIR, f"{stock_code}_{ts}.png")

        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close(fig)
        logger.info(f"Chart saved: {output_path}")
        return output_path

    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")
        return None


def generate_portfolio_chart(holdings: list, output_path: Optional[str] = None) -> Optional[str]:
    """Generate a pie chart for portfolio allocation."""
    if not _CHART_ENABLED:
        return None

    try:
        _ensure_dir()

        names = [h.get("name", str(h.get("code", "?"))) for h in holdings]
        values = [float(h.get("value", h.get("market_value", h.get("position", 0)))) for h in holdings]
        changes = [float(h.get("change_pct", 0)) for h in holdings]

        if sum(values) == 0:
            return None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        fig.patch.set_facecolor("#1a1a2e")

        # Pie
        colors_pie = ["#2ecc71" if c >= 0 else "#e74c3c" for c in changes]
        wedges, texts, autotexts = ax1.pie(
            values, labels=None, autopct="%1.0f%%",
            colors=colors_pie, startangle=90,
            textprops={"color": "white", "fontsize": 9},
        )
        ax1.legend(wedges, [f"{n} ({c:+.1f}%)" for n, c in zip(names, changes)],
                   title="Holdings", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                   fontsize=9)
        ax1.set_title("Portfolio Allocation", fontsize=14, fontweight="bold", color="white")

        # Simple bar for change
        ax2.set_facecolor("#1a1a2e")
        bar_colors = ["#2ecc71" if c >= 0 else "#e74c3c" for c in changes]
        ax2.barh(names, changes, color=bar_colors, alpha=0.8)
        ax2.axvline(x=0, color="white", linewidth=0.8, alpha=0.3)
        ax2.set_title("Daily Change %", fontsize=14, fontweight="bold", color="white")
        ax2.tick_params(colors="white", labelsize=9)
        ax2.grid(True, alpha=0.15, color="white", axis="x")

        plt.tight_layout()

        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(CHART_DIR, f"portfolio_{ts}.png")

        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close(fig)
        logger.info(f"Portfolio chart saved: {output_path}")
        return output_path

    except Exception as e:
        logger.warning(f"Portfolio chart failed: {e}")
        return None
