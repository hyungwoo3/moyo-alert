import os
import re
import json
import requests
from datetime import date
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

MIN_DATA_GB = 7
MAX_PRICE   = 3000

SENT_LOG = "sent_log.json"

URL = (
    "https://www.moyoplan.com/plans"
    "?excludeDiscount=9999-9999"
    "&page=1"
    "&sorting=fee_asc"
    "&tetheringRange=0-500"
    "&voice=9999-9999"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def load_sent_log():
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG, "r") as f:
            return json.load(f)
    return {}

def save_sent_log(log):
    with open(SENT_LOG, "w") as f:
        json.dump(log, f)

def fetch_plans():
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    plans = []
    for card in soup.select("a[href^='/plans/']"):
        text = card.get_text(" ", strip=True)
        price_match = re.search(r"월\s*([\d,]+)원", text)
        if not price_match:
            continue
        price = int(price_match.group(1).replace(",", ""))
        data_match = re.search(r"월\s*(\d+(?:\.\d+)?)\s*GB", text)
        if not data_match:
            continue
        data_gb = float(data_match.group(1))
        link = "https://www.moyoplan.com" + card["href"]
        plans.append({
            "price": price,
            "data_gb": data_gb,
            "link": link,
        })
    return plans

def filter_plans(plans):
    return [
        p for p in plans
        if p["data_gb"] >= MIN_DATA_GB
        and p["price"] <= MAX_PRICE
        and not any(kw in p["raw"] for kw in AD_KEYWORDS)
    ]

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] 텔레그램 환경변수가 설정되지 않았습니다.")
        return False
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=10,
    )
    if resp.status_code == 200:
        print("[OK] 텔레그램 알림 전송 성공!")
        return True
    else:
        print(f"[ERROR] 전송 실패: {resp.status_code} / {resp.text}")
        return False

def build_message(matched_plans):
    lines = [
        "🔔 모요플랜 알림!",
        f"7GB 이상 / {MAX_PRICE:,}원 이하 요금제 발견!",
        "",
    ]
    for p in matched_plans:
        lines.append(f"📱 {p['data_gb']}GB · 월 {p['price']:,}원")
        lines.append(f"👉 {p['link']}")
        lines.append("")
    lines.append("https://www.moyoplan.com/plans")
    return "\n".join(lines)

def main():
    today = str(date.today())
    print(f"[INFO] 크롤링 시작 (조건: {MIN_DATA_GB}GB 이상 / {MAX_PRICE:,}원 이하)")

    # 오늘 이미 알림 보냈는지 확인
    log = load_sent_log()
    if log.get("last_sent") == today:
        print("[INFO] 오늘 이미 알림 보냄 → 스킵")
        return

    try:
        plans = fetch_plans()
        print(f"[INFO] {len(plans)}개 요금제 파싱됨")
    except Exception as e:
        print(f"[ERROR] 크롤링 실패: {e}")
        return

    matched = filter_plans(plans)
    print(f"[INFO] 조건 충족: {len(matched)}개")

    if matched:
        msg = build_message(matched)
        print("[INFO] 알림 발송!")
        if send_telegram(msg):
            log["last_sent"] = today
            save_sent_log(log)
    else:
        print("[INFO] 조건 충족 요금제 없음 → 알림 없음")

if __name__ == "__main__":
    main()
