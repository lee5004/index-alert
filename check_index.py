import json
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
LEVELS = [10, 20, 30, 40, 50]   # 고점 대비 하락 단계(%)
LOOKBACK = "max"                # 역대 전고점 기준
# ================

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = Path("state.json")


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
    for ticker, name in INDEXES.items():
        try:
            hist = yf.Ticker(ticker).history(period=LOOKBACK)
        except Exception as e:
            print(f"[{name}] 조회 실패: {e}")
            continue
        if hist.empty:
            print(f"[{name}] 데이터 없음")
            continue

        high = float(hist["High"].max())
        high_date = hist["High"].idxmax().strftime("%Y-%m-%d")
        price = float(hist["Close"].iloc[-1])
        drawdown = (price - high) / high * 100

        s = state.get(ticker, {"high": 0, "alerted": []})
        if abs(high - s["high"]) > 0.01:
            s = {"high": high, "alerted": []}

        new_levels = [lv for lv in LEVELS if drawdown <= -lv and lv not in s["alerted"]]
        if new_levels:
            send(
                f"📉 {name} 고점 대비 -{max(new_levels)}% 돌파\n"
                f"현재 {price:,.2f} ({drawdown:.2f}%)\n"
                f"고점 {high:,.2f} ({high_date})"
            )
            s["alerted"] = sorted(set(s["alerted"]) | set(new_levels))

        state[ticker] = s
        print(f"[{name}] 현재 {price:,.2f} / 고점 {high:,.2f} / {drawdown:.2f}%")

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
