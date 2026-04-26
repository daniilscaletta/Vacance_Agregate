import requests
import time

TG_API = "https://api.telegram.org/bot{token}/{method}"


def _send(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    url = TG_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[sender] Ошибка отправки: {e}")
        return False


def _format_vacancy(v: dict, idx: int) -> str:
    lines = [f"<b>{idx}. {v['title']}</b>"]

    if v.get("company"):
        lines.append(f"🏢 {v['company']}")

    level = v.get("level", "")
    if level and level != "Не указан":
        lines.append(f"📊 {level}")

    if v.get("salary"):
        lines.append(f"💰 {v['salary']}")

    schedule = v.get("schedule", "")
    location = v.get("location", "")
    if schedule and location:
        lines.append(f"🏠 {schedule} · {location}")
    elif schedule:
        lines.append(f"🏠 {schedule}")
    elif location:
        lines.append(f"📍 {location}")

    source = v.get("source", "")
    if source:
        lines.append(f"📌 {source}")

    url = v.get("url") or v.get("post_url", "")
    if url:
        lines.append(f'🔗 <a href="{url}">Открыть вакансию</a>')

    return "\n".join(lines)


def send_vacancies(vacancies: list[dict], token: str, chat_id: str, date_label: str):
    if not vacancies:
        _send(token, chat_id, f"🔍 Вакансии за {date_label}\n\nНовых вакансий не найдено.")
        return

    header = (
        f"🔍 <b>Вакансии по ИБ за {date_label}</b>\n"
        f"Найдено: <b>{len(vacancies)}</b> вакансий\n"
        f"{'—' * 20}"
    )
    _send(token, chat_id, header)
    time.sleep(0.5)

    # Send in batches to avoid flood limits
    BATCH_SIZE = 5
    for i, vacancy in enumerate(vacancies, start=1):
        msg = _format_vacancy(vacancy, i)
        _send(token, chat_id, msg)
        if i % BATCH_SIZE == 0:
            time.sleep(2)
        else:
            time.sleep(0.3)

    footer = f"✅ Готово. Следующая рассылка завтра в 08:00 МСК."
    time.sleep(1)
    _send(token, chat_id, footer)
