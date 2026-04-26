import requests
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup

TG_WEB_URL = "https://t.me/s/{channel}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

IB_KEYWORDS = [
    # Пентест
    "пентест", "pentest", "penetration test", "тестирование на проникновение",
    "анализ защищённости", "анализ защищенности",
    # ИБ — стемы для покрытия всех падежей
    "информационной безопасност",
    "информационная безопасност",
    "информационную безопасност",
    "по информационной",
    "кибербезопасност",
    "защита информации", "защите информации", "защиты информации",
    "аудит безопасности", "аудит информационной",
    " иб ", " иб,", " иб.", "(иб)", "иб-специалист", "иб-аналитик",
    "аналитик иб", "специалист иб", "инженер иб",
    # English
    "appsec", "application security", "security engineer", "security analyst",
    "security researcher", "security specialist", "infosec", "information security",
    "offensive security", "defensive security", "cybersecurity",
    # SOC / SIEM / Threat
    "soc аналитик", "soc-аналитик", "soc analyst", "siem",
    "threat hunting", "threat intelligence", "threat analyst",
    "киберугроз", "кибератак",
    # Red/Blue team
    "red team", "redteam", "blue team", "purple team",
    # Прочее ИБ
    "dfir", "bug bounty", "vulnerability", "cve",
    "специалист по безопасности", "специалиста по безопасности",
    "специалисту по безопасности",
    "инженер безопасности", "инженера безопасности",
    "инженер по безопасности",
    "ибшник", "ибшница",
    "безопасност приложений",
    "безопасность приложений",
    "стажировка по безопасност",
    "стажёр по безопасност", "стажер по безопасност",
    "стажировка иб", "стажёр иб", "стажер иб",
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
        if not any(kw in low for kw in IB_KEYWORDS):
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


def _get_msg_id(msg) -> int | None:
    link = msg.find("a", class_="tgme_widget_message_date")
    if link and link.get("href"):
        parts = link["href"].rstrip("/").split("/")
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


def _fetch_page(channel: str, before_id: int | None = None) -> BeautifulSoup | None:
    url = TG_WEB_URL.format(channel=channel)
    if before_id:
        url += f"?before={before_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[tg] Ошибка загрузки @{channel} (before={before_id}): {e}")
        return None


def _parse_msg(msg, channel: str) -> dict | None:
    time_tag = msg.find("time", datetime=True)
    if not time_tag:
        return None

    try:
        post_dt = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
    except Exception:
        return None

    text_tag = msg.find("div", class_="tgme_widget_message_text")
    if not text_tag:
        return None

    text = text_tag.get_text(separator="\n", strip=True)
    if not text or len(text) < 30:
        return None

    if not is_ib_relevant(text):
        return None

    level = detect_level(text)
    if level is None:
        return None

    post_url = ""
    date_link = msg.find("a", class_="tgme_widget_message_date")
    if date_link and date_link.get("href"):
        post_url = date_link["href"]

    ext_links = extract_links(text_tag)
    link_str = ext_links[0] if ext_links else post_url

    first_line = text.split("\n")[0].strip()
    title = first_line[:120] if first_line else text[:80]

    return {
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
        "posted_at": post_dt,
    }


def parse_channel(channel: str, since: datetime) -> list[dict]:
    results = []
    oldest_id: int | None = None
    max_pages = 5

    for page_num in range(max_pages):
        soup = _fetch_page(channel, before_id=oldest_id)
        if not soup:
            break

        messages = soup.find_all("div", class_="tgme_widget_message")
        if not messages:
            break

        oldest_on_page: int | None = None
        any_newer_than_since = False

        for msg in messages:
            # track oldest ID for next-page fetch
            msg_id = _get_msg_id(msg)
            if msg_id:
                if oldest_on_page is None or msg_id < oldest_on_page:
                    oldest_on_page = msg_id

            # check post datetime
            time_tag = msg.find("time", datetime=True)
            if not time_tag:
                continue
            try:
                post_dt = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
            except Exception:
                continue

            if post_dt >= since:
                any_newer_than_since = True
                parsed = _parse_msg(msg, channel)
                if parsed:
                    results.append(parsed)

        # If oldest on this page is also newer than since, fetch more
        if oldest_on_page:
            oldest_id = oldest_on_page

        if not any_newer_than_since:
            break  # all posts on this page are older than window

        if page_num < max_pages - 1:
            time.sleep(1.0)

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
