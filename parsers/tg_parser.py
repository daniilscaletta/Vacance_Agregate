import requests
import re
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TG_WEB_URL = "https://t.me/s/{channel}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

IB_KEYWORDS = [
    "пентест", "pentest", "penetration", "тестирование на проникновение",
    "анализ защищённости", "анализ защищенности", "аудит безопасности",
    "информационная безопасность", "кибербезопасность", "appsec",
    "application security", "безопасность приложений", "soc аналитик",
    "soc-аналитик", "red team", "redteam", "dfir", "threat hunting",
    "threat intelligence", "специалист по безопасности", "инженер безопасности",
    "bug bounty", "vulnerability", "ибшник", "ибшница", "ibшник",
    "infosec", "information security", "offensive security",
    "стажировка безопасность", "стажёр безопасность",
]

EXCLUDE_KEYWORDS = [
    "разработчик", "программист", "developer", "frontend", "backend",
    "fullstack", "data scientist", "devops", "системный администратор",
    "sysadmin", "аналитик данных", "data analyst", "дизайнер", "designer",
    "маркетолог", "hr ", "рекрутер", "бухгалтер", "юрист",
]

SENIOR_KEYWORDS = [
    "senior", "сеньор", " lead", "лид", "head of", "chief", "руководитель",
    "директор", "principal", "architect",
]

LEVEL_MAP = {
    "Trainee/Стажёр": ["стажёр", "стажер", "trainee", "intern", "практикант", "стажировка"],
    "Junior": ["junior", "джуниор", "джун", "jun", "начинающий"],
    "Middle": ["middle", "мидл"],
}


def is_ib_relevant(text: str) -> bool:
    low = text.lower()
    if any(kw in low for kw in EXCLUDE_KEYWORDS):
        has_ib = any(kw in low for kw in IB_KEYWORDS)
        if not has_ib:
            return False
    return any(kw in low for kw in IB_KEYWORDS)


def detect_level(text: str) -> str | None:
    low = text.lower()
    if any(kw in low for kw in SENIOR_KEYWORDS):
        return None
    for level, keywords in LEVEL_MAP.items():
        if any(kw in low for kw in keywords):
            return level
    return "Не указан"


def extract_links(tag) -> list[str]:
    links = []
    for a in tag.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "t.me" not in href:
            links.append(href)
    return links


def parse_channel(channel: str, since: datetime) -> list[dict]:
    url = TG_WEB_URL.format(channel=channel)
    results = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[tg] Не удалось получить {channel}: {e}")
        return results

    soup = BeautifulSoup(resp.text, "lxml")
    messages = soup.find_all("div", class_="tgme_widget_message")

    for msg in messages:
        # Get datetime
        time_tag = msg.find("time", datetime=True)
        if not time_tag:
            continue

        try:
            dt_str = time_tag["datetime"]
            post_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            continue

        if post_dt < since:
            continue

        # Get text content
        text_tag = msg.find("div", class_="tgme_widget_message_text")
        if not text_tag:
            continue

        text = text_tag.get_text(separator="\n", strip=True)
        if not text or len(text) < 30:
            continue

        if not is_ib_relevant(text):
            continue

        level = detect_level(text)
        if level is None:
            continue  # skip senior+

        # Get post URL
        post_url = ""
        date_link = msg.find("a", class_="tgme_widget_message_date")
        if date_link and date_link.get("href"):
            post_url = date_link["href"]

        # Extract external links from post
        ext_links = extract_links(text_tag)
        link_str = ext_links[0] if ext_links else post_url

        # Try to extract vacancy title from first line
        first_line = text.split("\n")[0].strip()
        title = first_line[:120] if first_line else text[:80]

        results.append({
            "title": title,
            "url": link_str,
            "post_url": post_url,
            "company": f"@{channel}",
            "level": level,
            "salary": "",
            "schedule": "",
            "location": "",
            "source": f"TG @{channel}",
            "text_preview": text[:300],
        })

    return results


def fetch_tg_vacancies(channels: list[str], since: datetime) -> list[dict]:
    all_results = []
    seen_urls: set[str] = set()

    for channel in channels:
        print(f"[tg] Парсю @{channel}...")
        posts = parse_channel(channel, since)
        for post in posts:
            key = post.get("post_url") or post.get("url")
            if key and key in seen_urls:
                continue
            if key:
                seen_urls.add(key)
            all_results.append(post)
        time.sleep(1.5)

    return all_results
