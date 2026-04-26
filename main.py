import os
import sys
from datetime import datetime, timezone, timedelta

from parsers.hh_parser import fetch_hh_vacancies
from parsers.tg_parser import fetch_tg_vacancies
from parsers.sender import send_vacancies

TG_CHANNELS = [
    "vacancies_tt",
    "Young_and_Yandex",
    "postypashki_old",
    "infosec_work",
    "tbank_education",
    "Education_Yandex",
    "competech",
    "rabotaICL",
]


def main():
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")

    if not token or not chat_id:
        print("ERROR: TG_BOT_TOKEN и TG_CHAT_ID должны быть заданы в переменных окружения")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=25)  # чуть больше суток для overlap
    date_from_iso = since.strftime("%Y-%m-%dT%H:%M:%S")
    date_label = (now + timedelta(hours=3)).strftime("%d.%m.%Y")  # МСК

    print(f"[main] Поиск вакансий с {date_from_iso} UTC")

    # Collect from hh.ru
    print("[main] Сбор с hh.ru...")
    hh_vacancies = fetch_hh_vacancies(date_from_iso)
    print(f"[main] hh.ru: {len(hh_vacancies)} вакансий")

    # Collect from TG channels
    print("[main] Сбор с TG-каналов...")
    tg_vacancies = fetch_tg_vacancies(TG_CHANNELS, since)
    print(f"[main] TG: {len(tg_vacancies)} вакансий")

    # Merge and deduplicate by URL
    all_vacancies = hh_vacancies + tg_vacancies
    seen_urls: set[str] = set()
    deduped: list[dict] = []

    for v in all_vacancies:
        url = v.get("url") or v.get("post_url", "")
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
        deduped.append(v)

    # Sort: hh.ru first, then TG; within each — by level priority
    level_order = {"Trainee/Стажёр": 0, "Junior": 1, "Middle": 2, "Не указан": 3}

    def sort_key(v):
        src_order = 0 if v["source"] == "hh.ru" else 1
        lvl_order = level_order.get(v.get("level", "Не указан"), 3)
        return (src_order, lvl_order)

    deduped.sort(key=sort_key)

    print(f"[main] Итого уникальных: {len(deduped)}")

    # Send to Telegram
    send_vacancies(deduped, token, chat_id, date_label)
    print("[main] Готово.")


if __name__ == "__main__":
    main()
