        send(
            "📊 지수 현황\n\n" + "\n\n".join(report)
            + "\n\n🟢 -10% 이내  🟡 -10~20%  🔴 -20% 이하"
        )import json
import os
from pathlib import Path

import requests
import yfinance as yf

# ===== 설정 =====
INDEXES = {
    "^KS11": "코스피",
    "^KQ11": "코스닥",
    "^GSPC": "S&P 500",
    "^IXIC": "나스닥",
}
LEVELS = [10, 20, 30, 40, 50]   # 전고점 대비 하락 알림 단계(%)
REARM_GAP = 5                   # 단계보다 이만큼(%p) 회복하면 그 단계 다시 알림 가능
UP_LEVELS = [5, 10, 15, 20, 25, 30, 40, 50]       # 저점 대비 반등 알림 단계(%)
LOOKBACK = "max"                # 역대 전고점 기준
# ================

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = Path("state.json")
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=10,
    )
    r.raise_for_status()


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def main():
    state = load_state()
    report = []

    for ticker, name in INDEXES.items():
        try:
            hist = yf.Ticker(ticker).history(period=LOOKBACK)
        except Exception as e:
            print(f"[{name}] 조회 실패: {e}")
            report.append(f"{name}: 조회 실패")
            continue
        if hist.empty:
            print(f"[{name}] 데이터 없음")
            report.append(f"{name}: 데이터 없음")
            continue

        high_idx = hist["High"].idxmax()
        high = float(hist["High"].max())
        after = hist.loc[high_idx:]
        low_idx = after["Low"].idxmin()
        low = float(after["Low"].min())
        price = float(hist["Close"].iloc[-1])

        dd = (price - high) / high * 100        # 전고점 대비
        max_dd = (low - high) / high * 100      # 이번 사이클 최대 낙폭
        rebound = (price - low) / low * 100     # 저점 대비 반등

        old = state.get(ticker, {})
        s = {
            "high": old.get("high", 0),
            "low": old.get("low", 0),
            "down": old.get("down", old.get("alerted", [])),
            "up": old.get("up", []),
        }

        # 3. 신고점: 10% 이상 하락했던 사이클이 끝났을 때만 알림
        if high > s["high"] + 0.01:
            if s["high"] > 0 and s["down"]:
                send(
                    f"🎉 {name} 전고점 돌파 · 사이클 완료\n"
                    f"현재 {price:,.2f}\n"
                    f"이전 고점 {s['high']:,.2f} → 새 고점 {high:,.2f}"
                )
            s = {"high": high, "low": low, "down": [], "up": []}

        # 새 저점이 나오면 반등 단계 초기화
        if abs(low - s["low"]) > 0.01:
            s["low"] = low
            s["up"] = []

        # 1. 재알림: 단계보다 REARM_GAP 이상 회복하면 그 단계 초기화
        s["down"] = [lv for lv in s["down"] if dd <= -(lv - REARM_GAP)]

        new_down = [lv for lv in LEVELS if dd <= -lv and lv not in s["down"]]
        if new_down:
            send(
                f"📉 {name} 전고점 대비 -{max(new_down)}% 돌파\n"
                f"현재 {price:,.2f} ({dd:.2f}%)\n"
                f"고점 {high:,.2f} ({high_idx:%Y-%m-%d})"
            )
            s["down"] = sorted(set(s["down"]) | set(new_down))

        # 2. 저점 대비 반등: 10% 이상 하락한 적이 있을 때만
        if max_dd <= -LEVELS[0]:
            new_up = [lv for lv in UP_LEVELS if rebound >= lv and lv not in s["up"]]
            if new_up:
                send(
                    f"📈 {name} 저점 대비 +{max(new_up)}% 반등\n"
                    f"현재 {price:,.2f} (+{rebound:.2f}%)\n"
                    f"저점 {low:,.2f} ({low_idx:%Y-%m-%d})\n"
                    f"전고점 대비 {dd:.2f}%"
                )
                s["up"] = sorted(set(s["up"]) | set(new_up))

        state[ticker] = s
    
        mark = "🔴" if dd <= -20 else "🟡" if dd <= -10 else "🟢"
        report.append(
            f"{mark} {name}  {price:,.0f}\n"
            f"     전고점 {dd:+.1f}% · 저점 {rebound:+.1f}%"
        )
        print(f"[{name}] 현재 {price:,.2f} / 전고점 {dd:.2f}% / 반등 {rebound:.2f}%")

    if MANUAL:
        send(
            "📊 지수 현황\n\n" + "\n\n".join(report)
            + "\n\n🟢 -10% 이내  🟡 -10~20%  🔴 -20% 이하"
        )

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
