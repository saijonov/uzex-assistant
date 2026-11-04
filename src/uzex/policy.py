import re

from uzex.database import TOSHKENT_REGIONS, named_regions, normalize, region_choice
from uzex.models import RequestReview

OPTIONAL_FIELDS = {"period", "unit", "currency", "ranking", "role", "region"}
UNIT_WORDS = re.compile(
    r"\b(?:kg|kilo\w*|tonn\w*|litr\w*|dona\w*|sht|shtuk\w*|metr\w*|kubometr\w*|kub|kvadrat\w*|lot\w*)\b"
)
LIVE_PRICE_WORDS = re.compile(
    r"\b(?:jonli|hozir\w*|bugun\w*|ertaga\w*|kelgusi|seychas|segodn\w*|tekush\w*|zavtra\w*|"
    r"live|today|tomorrow)\b"
)
RECORD_NUMBER = re.compile(r"\b\d{6}\b")
RECORD_KIND_WORDS = re.compile(
    r"\b(?:bitim\w*|sdelk\w*|sdelok|shartnoma\w*|kontrakt\w*|deal\w*|contract\w*)\b"
)
PERCENT_WORDS = re.compile(r"\b(?:foiz\w*|ulush\w*|protsent\w*|dol[yiu]\w*)\b")
AGGREGATE_EXPRESSION = re.compile(r"(?:COUNT|SUM|MIN|MAX|MEDIAN)\(", re.IGNORECASE)
NO_PREFERENCE = re.compile(
    r"\b(?:farqi? (?:yoq|yuq)|farq qilmaydi|bilmadim|bilmayman|istalgan\w*|ahamiyati yoq|"
    r"nevajno|vse ravno|bez raznitsi|ne znayu|lyub\w*|any|dont know|doesnt matter)\b"
)

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
    "record_kind": (
        "Bu raqam bilan ham bitim, ham shartnoma bor. Qaysi biri kerak?",
        "С этим номером есть и сделка, и контракт. Что нужно?",
    ),
}


def missing_requirements(
    review: RequestReview, question: str, history: list, pending: dict | None
) -> list[str]:
    missing = list(review.missing_fields)
    if review.task == "list" and review.reference == "not_needed":
        missing = [field for field in missing if field not in {"entity", "reference", "product"}]
        if review.period in {"all_available", "not_needed"}:
            missing = [field for field in missing if field != "period"]
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
    if review.task == "rank" and review.subject == "deal":
        missing = [field for field in missing if field != "ranking"]
    elif review.task == "rank" and review.ranking_by in {"missing", "not_needed"}:
        missing.append("ranking")
    context = " ".join([question, (pending or {}).get("question", "")])
    if UNIT_WORDS.search(normalize(context)):
        missing = [field for field in missing if field != "unit"]
    if region_is_settled(context):
        missing = [field for field in missing if field != "region"]
    if pending:
        asked = set(pending.get("missing_fields") or []) if review.continuation else set()
        indifferent = no_preference(question)
        missing = [
            field
            for field in missing
            if field not in OPTIONAL_FIELDS or not (indifferent or field in asked)
        ]
    missing = list(dict.fromkeys(missing))
    for identity in ("product", "entity", "reference"):
        if identity in missing:
            return [identity]
    return missing[:2]


def bare_record_number(review: RequestReview, question: str, pending: dict | None) -> str | None:
    if review.subject in {"deal", "contract"}:
        return None
    context = " ".join([question, (pending or {}).get("question", "")])
    if RECORD_KIND_WORDS.search(normalize(context)):
        return None
    match = RECORD_NUMBER.search(context)
    return match.group() if match else None


def answer_gap(review: RequestReview, question: str, data) -> str | None:
    if not data.rows:
        return None
    expressions = [data.expressions[key] for key in data.rows[0] if key in data.expressions]
    if review.task == "rank" and all(AGGREGATE_EXPRESSION.match(item) for item in expressions):
        return (
            "The user asked who or what ranks highest, and this result does not name it. "
            "Select the code or name with GROUP BY and ORDER BY the metric."
        )
    asks_percent = "%" in question or PERCENT_WORDS.search(normalize(question))
    is_percent = (data.calculation or "").partition("(")[0] in {
        "percentage",
        "change_percent",
        "share_percent",
    }
    if asks_percent and not is_percent and "deposit_percent" not in data.sql:
        return (
            "The user asked for a percentage, and this result has none. Use calculate_ratio with "
            "percentage, change_percent or share_percent on this result."
        )
    return None


def no_preference(question: str) -> bool:
    return bool(NO_PREFERENCE.search(normalize(question)))


def region_is_settled(text: str) -> bool:
    names = named_regions(text)
    return bool(names) and not all(name in names for name in TOSHKENT_REGIONS)


def repeats_question(fields: list[str], pending: dict | None, continuation: bool) -> bool:
    return bool(
        pending
        and continuation
        and fields
        and set(fields) <= set(pending.get("missing_fields") or [])
    )


def settle_candidates(
    rows: list[dict], kind: str, question: str, pending: dict | None
) -> list[dict]:
    selected = (pending or {}).get("selected_candidate") or {}
    for key in ("inn", "broker_code", "name"):
        chosen = [row for row in rows if selected.get(key) and row.get(key) == selected[key]]
        if chosen:
            return [{**chosen[0], "match": "exact"}]
    if kind == "region" and len(rows) > 1:
        context = " ".join([question, (pending or {}).get("question", "")])
        choice = region_choice(context)
        chosen = [row for row in rows if row.get("name") == choice]
        if chosen:
            return [{**chosen[0], "match": "exact"}]
    return rows


def unavailable_request(review: RequestReview, question: str) -> str | None:
    value = normalize(question)
    price_request = (review.task == "price" and review.subject not in {"deal", "contract"}) or (
        review.task == "unsupported" and review.subject in {"product", "market"}
    )
    if price_request and LIVE_PRICE_WORDS.search(value):
        if not re.search(r"\b20\d{2}\b", value) and not RECORD_NUMBER.search(value):
            return "outside_dates"
    return None


FILE_TERM = r"\b(?:csv|excel|xlsx|eksel\w*|fayl\w*|file\w*)"
DECLINES_FILE = re.compile(
    FILE_TERM
    + r".{0,25}\b(?:kerak emas|kerakmas|yuborma\w*|jonatma\w*|berma\w*|qilma\w*|ne nujen|ne nado)"
    + r"|\b(?:bez|no|without|ne nujen|ne nado|ne prisilay\w*|ne otpravlyay\w*)\b.{0,15}"
    + FILE_TERM
    + r"|\bfaqat matn|\btext only|\btolko tekst|\bfaylsiz\b"
)
ASKS_FOR_FILE = re.compile(
    r"\b(?:jonat\w*|yubor\w*|ber\w{0,5}|format\w*|skacha\w*|skin\w*|prishli\w*|otprav\w*|"
    r"send|download|qil\w*|day|dayte)\b"
)


def file_preference(question: str) -> str:
    value = normalize(question)
    if DECLINES_FILE.search(value):
        return "text"
    if re.search(FILE_TERM, value) and ASKS_FOR_FILE.search(value):
        return "csv"
    if value in {"csv", "v csv", "csv formatida", "v formate csv"}:
        return "csv"
    return "auto"


FILE_WORD = re.compile(r"(?:csv|excel|xlsx|eksel\w*|fayl\w*|file\w*)")
EXPORT_FILLER = set(
    "shu shuni shularni shunday bu buni bularni natija natijani natijalarni javob javobni "
    "hammasi hammasini iltimos menga mana ham ni qilib qil qiling qilibber ber bering berib "
    "yubor yuboring yuborib jonat jonating jonatib formatida formatda formatga korinishida "
    "tashla tashlang v vide formate kak eto etot etu eti rezultat tablitsu mne pojaluysta "
    "prishli prishlite otprav otpravte day dayte skachat skinte skin send give me it this "
    "as please download export".split()
)


def export_followup(question: str) -> bool:
    if DECLINES_FILE.search(normalize(question)):
        return False
    tokens = normalize(question).split()
    has_file_word = any(FILE_WORD.fullmatch(token) for token in tokens)
    return has_file_word and all(
        FILE_WORD.fullmatch(token) or token in EXPORT_FILLER for token in tokens
    )


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
