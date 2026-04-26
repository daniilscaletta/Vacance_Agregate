import requests
import time
from datetime import datetime, timezone

HH_API_URL = "https://api.hh.ru/vacancies"
HEADERS = {"User-Agent": "VacanceAgregate/1.0 (daniilmustetsov@gmail.com)"}

SEARCH_TEXT = (
    "пентест OR pentest OR \"тестирование на проникновение\" OR "
    "\"анализ защищённости\" OR \"анализ защищенности\" OR AppSec OR "
    "\"информационная безопасность\" OR \"кибербезопасность\" OR "
    "\"аудит безопасности\" OR \"red team\" OR DFIR OR "
    "\"threat hunting\" OR \"SOC аналитик\" OR \"безопасность приложений\" OR "
    "\"специалист по безопасности\" OR \"инженер безопасности\""
)

SENIOR_KEYWORDS = [
    "senior", "сеньор", "lead", "лид", "head", "руководитель", "chief",
    "principal", "architect", "архитектор", "директор"
]

LEVEL_MAP = {
    "trainee": ["стажёр", "стажер", "trainee", "intern", "практикант", "стажировка"],
    "junior": ["junior", "джуниор", "джун", "jun ", "jun+", "начинающий"],
    "middle": ["middle", "мидл", "mid "],
}

CURRENCY_SYM = {"RUR": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "BYR": "Br"}


def detect_level(title: str) -> str | None:
    low = title.lower()
    if any(kw in low for kw in SENIOR_KEYWORDS):
        return None
    for level, keywords in LEVEL_MAP.items():
        if any(kw in low for kw in keywords):
            return level.capitalize()
    return "Не указан"


def format_salary(salary_data: dict | None) -> str:
    if not salary_data:
        return ""
    frm = salary_data.get("from")
    to = salary_data.get("to")
    currency = salary_data.get("currency", "RUR")
    sym = CURRENCY_SYM.get(currency, currency)
    gross = " gross" if salary_data.get("gross") else ""
    if frm and to:
        return f"от {frm:,} до {to:,} {sym}{gross}".replace(",", " ")
    if frm:
        return f"от {frm:,} {sym}{gross}".replace(",", " ")
    if to:
        return f"до {to:,} {sym}{gross}".replace(",", " ")
    return ""


def _fetch_page(params: dict) -> dict | None:
    try:
        resp = requests.get(HH_API_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[hh] Ошибка запроса: {e}")
        return None


def fetch_hh_vacancies(date_from: str) -> list[dict]:
    results = []
    seen_ids: set[str] = set()

    # Two passes: remote (anywhere) + SPb (hybrid/flexible)
    configs = [
        {"schedule": "remote"},
        {"area": 2, "schedule": "flexible"},  # SPb hybrid
        {"area": 2},                            # SPb all — post-filter fullDay
    ]

    for config in configs:
        page = 0
        while page < 10:
            params = {
                "text": SEARCH_TEXT,
                "date_from": date_from,
                "per_page": 100,
                "page": page,
                **config,
            }

            data = _fetch_page(params)
            if not data:
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                vac_id = item["id"]
                if vac_id in seen_ids:
                    continue

                title = item.get("name", "")
                schedule_id = item.get("schedule", {}).get("id", "")
                schedule_name = item.get("schedule", {}).get("name", "")

                # For SPb "all" pass — skip pure office
                if config.get("area") == 2 and "schedule" not in config:
                    if schedule_id == "fullDay":
                        continue

                level = detect_level(title)
                if level is None:
                    continue  # skip senior+

                area_name = item.get("area", {}).get("name", "")
                employer = item.get("employer", {}).get("name", "")
                url = item.get("alternate_url", "")
                salary_str = format_salary(item.get("salary"))

                seen_ids.add(vac_id)
                results.append({
                    "title": title,
                    "url": url,
                    "company": employer,
                    "level": level,
                    "salary": salary_str,
                    "schedule": schedule_name,
                    "location": area_name,
                    "source": "hh.ru",
                })

            total_pages = data.get("pages", 1)
            page += 1
            if page >= total_pages:
                break

            time.sleep(0.5)

    return results
