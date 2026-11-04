import re

from uzex.database import normalize
from uzex.models import RequestReview

CLARIFICATION_TEXT = {
    "entity": (
        "Qaysi bitim, shartnoma yoki kompaniya? Raqami, nomi yoki STIRini yozing.",
        "Какая сделка, контракт или компания? Укажите номер, название или ИНН.",
    ),
    "product": ("Qaysi tovar haqida so‘rayapsiz?", "О каком товаре идёт речь?"),
    "period": ("Qaysi sana yoki davr uchun?", "За какую дату или период?"),
    "metric": (
        "Qaysi ma’lumot kerak: bitimlar soni, summa, hajm yoki narx?",
        "Что нужно узнать: количество сделок, сумму, объём или цену?",
    ),
    "unit": (
        "Qaysi o‘lchov birligida kerak, masalan kilogramm yoki tonnada?",
        "В какой единице нужно показать результат, например в килограммах или тоннах?",
    ),
    "currency": (
        "Qaysi valyutada kerak: so‘mda yoki AQSh dollarida?",
        "В какой валюте нужен результат: в сумах или долларах США?",
    ),
    "role": (
        "Sotuvchilarni nazarda tutdingizmi yoki xaridorlarni?",
        "Вы имеете в виду продавцов или покупателей?",
    ),
    "region": (
        "Qaysi hudud? Shahar yoki viloyat ekanini ham yozing.",
        "Уточните регион: город или область. Напишите название.",
    ),
    "reference": (
        "Qaysi oldingi bitim yoki natijani nazarda tutdingiz?",
        "Какую предыдущую сделку или результат вы имеете в виду?",
    ),
    "comparison": (
        "Nimalarni va qaysi ko‘rsatkich bo‘yicha taqqoslaymiz?",
        "Что сравнить и по какому показателю?",
    ),
    "ranking": (
        "Eng ko‘p bitim, eng katta summa yoki eng katta hajm bo‘yichami?",
        "По количеству сделок, общей сумме или объёму?",
    ),
    "delivery": (
        "CSV fayl yuboraymi yoki natijani matnda ko‘rsataymi?",
        "Отправить CSV или показать результат текстом?",
    ),
}


def missing_requirements(
    review: RequestReview, question: str, history: list, pending: dict | None
) -> list[str]:
    missing = list(review.missing_fields)
    if review.task == "unsupported":
        return []
    if review.task == "unknown":
        missing.append("metric")
    if review.reference == "missing":
        missing.append(
            "product" if review.task == "price" and review.subject != "deal" else "entity"
        )
    if review.reference == "specified":
        context = " ".join([question, (pending or {}).get("question", "")])
        if (
            not review.entity_text
            or not normalize(review.entity_text)
            or normalize(review.entity_text) not in normalize(context)
        ):
            missing.append("entity")
    if review.reference == "context" and not history and not pending:
        missing.append("reference")
    if review.period == "missing":
        missing.append("period")
    if review.period == "context" and not history and not pending:
        missing.append("period")
    if (
        review.task == "price"
        and review.subject not in {"deal", "contract"}
        and review.period in {"all_available", "not_needed"}
    ):
        missing.append("period")
    if review.task == "price" and review.subject not in {"deal", "contract"}:
        context = normalize(question + " " + (pending or {}).get("question", ""))
        if not re.search(
            r"\b(kg|kilogramm|kilogram|tonna|tonne|tonn|tonnu|tonnah|litr|dona|shtuka|shtuku|sht|metr|lot)\b",
            context,
        ):
            missing.append("unit")
    if review.task == "rank" and review.ranking_by in {"missing", "not_needed"}:
        missing.append("ranking")
    missing = list(dict.fromkeys(missing))
    for identity in ("product", "entity", "reference"):
        if identity in missing:
            return [identity]
    return missing[:2]


def unavailable_request(review: RequestReview, question: str) -> str | None:
    value = normalize(question)
    price_request = review.task == "price" or (
        review.task == "unsupported" and review.subject in {"product", "market"}
    )
    if price_request and re.search(
        r"\b(jonli|hozir|bugun|ertaga|seychas|segodnya|zavtra|live|today|tomorrow)\b", value
    ):
        if not re.search(r"\b20\d{2}\b", value):
            return "outside_dates"
    return None


def file_preference(question: str) -> str:
    value = normalize(question)
    if re.search(
        r"(?:csv|fayl|file).{0,25}(?:kerak emas|kerakmas|yuborma|jonatma|ne nujen|ne nuzhen|ne nado)|(?:bez|bez fayla|no|without|ne nujen|ne nuzhen|ne nado).{0,15}(?:csv|file|fayl)|faqat matn|text only|tolko tekst|ne (?:prisilay|otpravlyay).{0,15}csv|faylsiz",
        value,
    ):
        return "text"
    if re.search(r"\bcsv\b", value) and re.search(
        r"jonat|yubor|ber|format|skacha|prishli|otprav|send|download|qilib", value
    ):
        return "csv"
    if value in {"csv", "v csv", "csv formatida", "v formate csv"}:
        return "csv"
    return "auto"


def export_followup(question: str) -> bool:
    return normalize(question) in {
        "csv",
        "csv ber",
        "csv qilib ber",
        "csv formatida",
        "csv faylni yubor",
        "csv faylini yubor",
        "v csv",
        "prishli csv",
        "otprav csv",
        "skachat csv",
    }


def attach_csv(question: str, answer) -> bool:
    if answer.outcome != "answer" or not answer.evidence or not answer.evidence.rows:
        return False
    preference = file_preference(question)
    return preference != "text" and (preference == "csv" or len(answer.evidence.rows) > 10)


def resolve_pending_reply(pending: dict | None, question: str) -> dict | None:
    if not pending or not pending.get("candidates"):
        return pending
    value = normalize(question)
    ordinals = {
        "birinchisi": 1,
        "ikkinchisi": 2,
        "uchinchisi": 3,
        "tortinchisi": 4,
        "beshinchisi": 5,
        "perviy": 1,
        "vtoroy": 2,
        "tretiy": 3,
    }
    number = int(value) if value.isdecimal() and len(value) <= 2 else ordinals.get(value)
    if number and 1 <= number <= len(pending["candidates"]):
        return {**pending, "selected_candidate": pending["candidates"][number - 1]}
    return pending
