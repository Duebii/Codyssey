"""Create three FX charts and reproducible trend/volatility summaries."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
IMAGES = OUT / "images"
COLORS = {"USD_KRW": "#2563A6", "EUR_KRW": "#C65B3E", "JPY100_KRW": "#16877C"}
NAMES = {"USD_KRW": "달러", "EUR_KRW": "유로", "JPY100_KRW": "엔화"}
UNITS = {"USD_KRW": "원 / 1달러", "EUR_KRW": "원 / 1유로", "JPY100_KRW": "원 / 100엔"}


def style_axis(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color("#CFD7DF")
    ax.grid(axis="y", color="#E5EAF0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#536174", length=0)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def save(fig, filename):
    fig.savefig(IMAGES / filename, dpi=160, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    if font_path.exists():
        fm.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = fm.FontProperties(fname=str(font_path)).get_name()
    else:
        available = {f.name for f in fm.fontManager.ttflist}
        for name in ["Noto Sans CJK KR", "NanumGothic", "AppleGothic"]:
            if name in available:
                plt.rcParams["font.family"] = name
                break
        else:
            raise RuntimeError("Install a Korean font (Malgun Gothic, Noto Sans CJK KR or NanumGothic)")
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 11,
                         "axes.labelcolor": "#536174", "text.color": "#162D45"})
    rates = pd.read_csv(OUT / "fx_krw_clean.csv", parse_dates=["date"]).set_index("date")
    columns = list(NAMES)
    if list(rates.columns) != columns or not rates.index.is_unique or not rates.index.is_monotonic_increasing:
        raise ValueError("Run check_data.py first; unexpected clean data schema")
    if rates.isna().any().any() or not np.isfinite(rates.to_numpy()).all() or (rates <= 0).any().any():
        raise ValueError("Clean data must contain finite positive complete observations")
    index100 = rates.div(rates.iloc[0]) * 100
    ma20 = rates.rolling(20, min_periods=20).mean()
    change = rates.pct_change(fill_method=None) * 100
    monthly_vol = change.groupby(change.index.to_period("M")).std(ddof=1)
    monthly_count = change.groupby(change.index.to_period("M")).count()
    monthly_vol.index = monthly_vol.index.to_timestamp()
    monthly_count.index = monthly_count.index.to_timestamp()
    index100.to_csv(OUT / "fx_index100.csv", index_label="date", float_format="%.8f")
    ma20.to_csv(OUT / "fx_ma20.csv", index_label="date", float_format="%.8f")
    change.to_csv(OUT / "fx_change_pct.csv", index_label="date", float_format="%.8f")
    monthly_vol.to_csv(OUT / "monthly_volatility.csv", index_label="month", float_format="%.8f")
    monthly_count.to_csv(OUT / "monthly_change_counts.csv", index_label="month")
    metrics = {}
    for col in columns:
        peak = monthly_vol[col].idxmax()
        metrics[col] = {
            "name": NAMES[col], "unit": UNITS[col], "first_rate": float(rates[col].iloc[0]),
            "last_rate": float(rates[col].iloc[-1]), "change_pct": float(index100[col].iloc[-1] - 100),
            "minimum": float(rates[col].min()), "minimum_date": rates[col].idxmin().strftime("%Y-%m-%d"),
            "maximum": float(rates[col].max()), "maximum_date": rates[col].idxmax().strftime("%Y-%m-%d"),
            "change_std_full_period": float(change[col].std(ddof=1)),
            "peak_volatility_month": peak.strftime("%Y-%m"),
            "peak_monthly_volatility_pct": float(monthly_vol.loc[peak, col]),
            "peak_month_valid_changes": int(monthly_count.loc[peak, col]),
        }
    summary = {"observations": len(rates), "first_date": rates.index.min().strftime("%Y-%m-%d"),
               "last_date": rates.index.max().strftime("%Y-%m-%d"), "monthly_periods": len(monthly_vol),
               "moving_average_window_observations": 20, "volatility_ddof": 1,
               "metrics": metrics, "versions": {"matplotlib": matplotlib.__version__, "pandas": pd.__version__, "numpy": np.__version__}}
    (OUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(12, 6.4))
    fig.subplots_adjust(top=0.80, bottom=0.17, left=0.09, right=0.96)
    fig.text(0.09, 0.94, "달러·유로·엔화, 출발점에서 얼마나 달라졌을까?", fontsize=20, weight="bold")
    fig.text(0.09, 0.88, f"{summary['first_date']} = 100  |  동일한 원화 기준·공통 관측일 {len(rates):,}개", color="#536174", fontsize=11)
    for col in columns:
        ax.plot(index100.index, index100[col], color=COLORS[col], linewidth=1.6,
                label=f"{NAMES[col]}  {metrics[col]['change_pct']:+.2f}%")
        ax.scatter(index100.index[-1], index100[col].iloc[-1], color=COLORS[col], s=30, zorder=4)
    ax.axhline(100, color="#8995A3", linewidth=1, linestyle="--")
    ax.set_ylabel("환율 비교 지수")
    ax.legend(loc="upper left", frameon=False, ncols=3)
    style_axis(ax)
    fig.text(0.09, 0.06, "100 초과: 시작일보다 외화가 원화 기준으로 비싸짐. 100 미만: 시작일보다 저렴해짐.", fontsize=10, color="#536174")
    fig.text(0.09, 0.02, "자료: FRED / 미국 연준 H.10  ·  환전 수수료·이자 제외  ·  2026년은 8월까지", fontsize=9, color="#69798C")
    save(fig, "01_index_comparison.png")

    fig, axes = plt.subplots(3, 1, figsize=(12, 9.2), sharex=True)
    fig.subplots_adjust(top=0.85, bottom=0.12, left=0.11, right=0.97, hspace=0.30)
    fig.text(0.11, 0.95, "통화별 환율 수준과 20개 관측일 이동평균", fontsize=20, weight="bold")
    fig.text(0.11, 0.90, "옅은 선은 실제 환율, 진한 선은 최근 20개 관측값의 평균", fontsize=11, color="#536174")
    for ax, col in zip(axes, columns):
        ax.plot(rates.index, rates[col], color=COLORS[col], alpha=0.28, linewidth=1, label="실제 환율")
        ax.plot(ma20.index, ma20[col], color=COLORS[col], linewidth=2, label="20개 관측일 평균")
        ax.set_title(NAMES[col], loc="left", weight="bold", fontsize=13)
        ax.set_ylabel(UNITS[col])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f}"))
        style_axis(ax)
    axes[0].legend(loc="upper left", ncols=2, frameon=False, fontsize=9)
    fig.text(0.11, 0.055, "패널별 세로축 범위가 다름. 통화 간 변화 크기는 그림 1의 지수와 함께 확인.", color="#536174", fontsize=10)
    fig.text(0.11, 0.02, "자료: FRED / 미국 연준 H.10  ·  유로·엔화는 교차환율  ·  최초 19개 이동평균 값은 미산출", fontsize=9, color="#69798C")
    save(fig, "02_rates_moving_average.png")

    fig, axes = plt.subplots(3, 1, figsize=(12, 8.2), sharex=True, sharey=True)
    fig.subplots_adjust(top=0.85, bottom=0.14, left=0.11, right=0.97, hspace=0.34)
    fig.text(0.11, 0.95, "어느 시기에 환율이 더 크게 흔들렸을까?", fontsize=20, weight="bold")
    fig.text(0.11, 0.90, "월별 변동성: 전 관측일 대비 변화율의 표준편차  |  세 패널의 세로축 범위 동일", fontsize=11, color="#536174")
    upper = float(monthly_vol.max().max()) * 1.38
    for ax, col in zip(axes, columns):
        ax.plot(monthly_vol.index, monthly_vol[col], color=COLORS[col], linewidth=1.6)
        ax.fill_between(monthly_vol.index, 0, monthly_vol[col], color=COLORS[col], alpha=0.10)
        peak = monthly_vol[col].idxmax()
        value = monthly_vol.loc[peak, col]
        ax.scatter(peak, value, color=COLORS[col], s=30, zorder=4)
        ax.annotate(f"{peak:%Y-%m}  {value:.2f}%", xy=(peak, value), xytext=(5, 12),
                    textcoords="offset points", color=COLORS[col], fontsize=10)
        ax.set_title(NAMES[col], loc="left", fontsize=13, weight="bold")
        ax.set_ylabel("표준편차 (%)")
        ax.set_ylim(0, upper)
        style_axis(ax)
    fig.text(0.11, 0.065, "값이 클수록 변화율의 퍼짐이 큼. 상승·하락 방향이나 투자 수익률을 나타내는 지표는 아님.", fontsize=10, color="#536174")
    fig.text(0.11, 0.025, "자료: FRED / 미국 연준 H.10  ·  표본 표준편차(ddof=1)  ·  변화율은 휴일을 건너뛴 관측 간 변화를 포함", fontsize=9, color="#69798C")
    save(fig, "03_monthly_volatility.png")

    lines = ["# 분석 결과와 그래프 읽기", "", f"기간: {summary['first_date']}–{summary['last_date']}. 공통 관측일 {len(rates):,}개. 월별 구간 {len(monthly_vol)}개.",
             "", "## 질문 1. 시작점 대비 얼마나 달라졌는가?", "",
             "![시작값 100 기준 비교](images/01_index_comparison.png)", "",
             "각 통화 환율을 첫날 값으로 나눈 뒤 100을 곱했다. 통화의 단위 차이를 없애 변화의 비율을 비교하기 위한 방법이다.",
             "", "| 통화 | 첫 관측일 환율 | 마지막 관측일 환율 | 기간 변화율 |", "|---|---:|---:|---:|"]
    for col, m in metrics.items():
        lines.append(f"| {NAMES[col]} ({UNITS[col]}) | {m['first_rate']:,.2f} | {m['last_rate']:,.2f} | {m['change_pct']:+.2f}% |")
    lines += ["", "**관찰:** " + " / ".join(f"{NAMES[c]} {metrics[c]['change_pct']:+.2f}%" for c in columns) + ".",
              "**해석:** 같은 양의 외화를 마련할 때 드는 원화 비용의 변화가 통화마다 달랐다. 이 지수는 기준일 대비 변화이며 적정 가치·저평가 여부를 판단하는 지표가 아니다. 기간 변화율은 환율만의 변화로 이자·수수료·세금을 포함한 투자 수익률과 다르다.",
              "", "## 질문 2. 환율의 흐름은 어떻게 달랐는가?", "",
              "![환율과 이동평균](images/02_rates_moving_average.png)", "",
              "20개 유효 관측값의 후행 평균을 사용했다. 단기 움직임을 부드럽게 해 전체 흐름을 읽기 위한 것이며, 20달력일과 다르고 방향 전환을 늦게 반영할 수 있다. 최초 19개 평균은 미산출로 유지했다.",
              "", "| 통화 | 최솟값과 날짜 | 최댓값과 날짜 |", "|---|---|---|"]
    for col, m in metrics.items():
        lines.append(f"| {NAMES[col]} | {m['minimum']:,.2f} ({m['minimum_date']}) | {m['maximum']:,.2f} ({m['maximum_date']}) |")
    lines += ["", "**해석 시 확인:** 첫날과 마지막 날의 차이만으로 중간의 상승·하락 과정을 설명할 수 없다. 각 통화의 극값 시점과 이동평균 흐름을 함께 확인한다. 패널별 축이 다르므로 선의 기울기로 통화 간 변화 크기를 비교하지 않는다.",
              "", "## 질문 3. 언제 가장 크게 흔들렸는가?", "",
              "![월별 변동성](images/03_monthly_volatility.png)", "",
              "전 공통 관측일 대비 단순 변화율(%)을 구한 뒤, 변화가 끝난 날짜의 월로 묶어 표본 표준편차(ddof=1)를 계산했다. 월 첫 관측일에는 직전 월 관측일과의 변화가 포함될 수 있다. 2020년 첫 관측일의 변화율은 미산출이다.",
              "", "| 통화 | 전체 기간 변화율 표준편차 | 변동성 최대 월 | 해당 월 표준편차 | 해당 월 변화율 수 |", "|---|---:|---|---:|---:|"]
    for col, m in metrics.items():
        lines.append(f"| {NAMES[col]} | {m['change_std_full_period']:.4f}% | {m['peak_volatility_month']} | {m['peak_monthly_volatility_pct']:.4f}% | {m['peak_month_valid_changes']} |")
    lines += ["", "**해석:** 변동성은 변화율이 평균 주변에서 얼마나 퍼졌는지 나타낸다. 큰 변동성만으로 상승 방향·손실 크기·미래 움직임을 판단할 수 없다. 통계는 관측일 단위이며 연율화하지 않았다.",
              "", "## 계산 정의와 한계", "",
              "- 기간 변화율 = 마지막 환율 / 첫 환율 − 1. 그래프에는 100을 곱해 %로 표시.",
              "- 각 통화는 원화를 기준으로 하므로 원화 측 움직임을 공유한다. 세 시리즈를 서로 독립적인 자산 움직임으로 가정하지 않는다.",
              "- 결측치를 채우지 않았으므로 주말·휴일을 건너뛴 변화가 포함된다.",
              "- 2026년은 1–8월 자료이며 2026년 전체 결과로 표현하지 않는다.",
              "- 외부 금리·정책 사건의 인과관계는 이 분석에서 검증하지 않았다.",
              "", "## AI 사용 로그", "",
              "| 작업 | 이유 | 검증 방법 |", "|---|---|---|",
              "| 계산 코드와 그래프 작성 | 동일한 방법으로 세 통화를 비교하고 재현하기 위해 | 원본 환산 점검 결과 활용, 저장된 계산값의 독립 검산 및 이미지 확인 |",
              "| 그래프 설명 초안 작성 | 관찰과 해석을 구분하고 단위를 명확히 하기 위해 | 실제 계산 수치와 설명 대조, 최종 해석은 사용자 검토 |",
              "", "## 출처", "",
              "[DEXKOUS](https://fred.stlouisfed.org/series/DEXKOUS), [DEXUSEU](https://fred.stlouisfed.org/series/DEXUSEU), [DEXJPUS](https://fred.stlouisfed.org/series/DEXJPUS). 원출처: 미국 연방준비제도 H.10, 제공: FRED. 자세한 수집·정제 기록은 [DATA_CHECK.md](DATA_CHECK.md)에 있다.",
              "", "최종 인사이트와 결론·회고는 [REPORT.md](REPORT.md)에 정리했다.", ""]
    (OUT / "ANALYSIS_NOTES.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
