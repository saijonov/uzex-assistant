import csv
import io
import re

import sqlglot
from sqlglot import exp

from uzex.localization import localize
from uzex.models import Answer, Evidence

LABELS = {
    "deal_id": ("Bitim raqami", "Номер сделки"),
    "contract_id": ("Shartnoma raqami", "Номер контракта"),
    "deal_date": ("Bitim sanasi", "Дата сделки"),
    "deal_time": ("Vaqt", "Время"),
    "product_name": ("Tovar", "Товар"),
    "product": ("Mahsulot", "Продукт"),
    "seller_name": ("Sotuvchi", "Продавец"),
    "buyer_name": ("Xaridor", "Покупатель"),
    "seller_inn": ("Sotuvchi STIR", "ИНН продавца"),
    "buyer_inn": ("Xaridor STIR", "ИНН покупателя"),
    "seller_region": ("Sotuvchi ro‘yxat hududi", "Регион регистрации продавца"),
    "buyer_region": ("Xaridor ro‘yxat hududi", "Регион регистрации покупателя"),
    "seller_broker_code": ("Sotuvchi brokeri kodi", "Код брокера продавца"),
    "buyer_broker_code": ("Xaridor brokeri kodi", "Код брокера покупателя"),
    "seller_broker_name": ("Sotuvchi brokeri", "Брокер продавца"),
    "buyer_broker_name": ("Xaridor brokeri", "Брокер покупателя"),
    "quantity_lots": ("Lotlar soni", "Количество лотов"),
    "lot_size": ("Bir lot hajmi", "Размер лота"),
    "volume": ("Hajm", "Объём"),
    "mass_kg": ("Massa, kg", "Масса, кг"),
    "delivered_mass_kg": ("Yetkazilgan massa, kg", "Поставленная масса, кг"),
    "delivered_volume": ("Yetkazilgan hajm", "Поставленный объём"),
    "delivered_lots": ("Yetkazilgan lotlar", "Поставлено лотов"),
    "amount": ("Summa, shartnoma valyutasida", "Сумма в валюте контракта"),
    "amount_uzs": ("Summa, so‘m", "Сумма, сум"),
    "starting_price": ("Boshlang‘ich birlik narxi", "Стартовая цена за единицу"),
    "base_price": ("Bazaviy birlik narxi", "Базисная цена за единицу"),
    "currency": ("Valyuta", "Валюта"),
    "unit": ("O‘lchov birligi", "Единица измерения"),
    "region": ("Hudud", "Регион"),
    "region_ru": ("Ombor hududi", "Регион склада"),
    "status": ("Holat", "Состояние"),
    "category": ("Toifa", "Категория"),
    "brand": ("Marka", "Марка"),
    "grade": ("Sort", "Сорт"),
    "size": ("O‘lcham", "Размер"),
    "product_type": ("Mahsulot turi", "Тип товара"),
    "product_class": ("Sinf", "Класс"),
    "hs_code": ("TIF TN kodi", "Код ТН ВЭД"),
    "auction_type": ("Savdo turi", "Тип торгов"),
    "contract_type": ("Shartnoma turi", "Тип контракта"),
    "contract_form": ("Shartnoma shakli", "Форма контракта"),
    "paid_on": ("To‘lov sanasi", "Дата оплаты"),
    "delivered_on": ("Yetkazish sanasi", "Дата поставки"),
    "payment_days": ("To‘lov muddati, kalendar kun", "Срок оплаты, календарных дней"),
    "delivery_days": ("Yetkazish muddati, kalendar kun", "Срок поставки, календарных дней"),
    "payment_due": ("To‘lovning oxirgi sanasi", "Крайняя дата оплаты"),
    "delivery_due": ("Yetkazishning oxirgi sanasi", "Крайняя дата поставки"),
    "deposit_percent": ("Garov, %", "Залог, %"),
    "usd_uzs": ("1 USD uchun so‘m", "Сум за 1 USD"),
    "rate_date": ("Kurs sanasi", "Дата курса"),
    "inn": ("STIR", "ИНН"),
    "name": ("Nomi", "Наименование"),
    "broker_code": ("Broker kodi", "Код брокера"),
    "role": ("Rol", "Роль"),
    "vat_payer": ("QQS to‘lovchisi", "Плательщик НДС"),
    "activity": ("Faoliyat", "Вид деятельности"),
    "is_cancelled": ("Bekor qilingan", "Аннулирована"),
    "source_file": ("Manba fayli", "Файл-источник"),
    "source_row": ("CSV qatori", "Строка CSV"),
    "ratio": ("Hisoblangan nisbat", "Вычисленное отношение"),
    "industry": ("Sanoat tarmog‘i", "Отрасль промышленности"),
    "product_group": ("Tovar guruhi", "Группа товара"),
    "delivery_basis": ("Yetkazish bazisi", "Базис поставки"),
    "packaging": ("Qadoqlash", "Упаковка"),
    "warehouse_address": ("Ombor manzili", "Адрес склада"),
    "registered_on": ("Ro‘yxatdan o‘tgan sana", "Дата регистрации"),
    "valid_until": ("Amal qilish muddati", "Действует до"),
    "seller_vat_payer": ("Sotuvchi QQS to‘lovchisi", "Продавец, плательщик НДС"),
    "buyer_vat_payer": ("Xaridor QQS to‘lovchisi", "Покупатель, плательщик НДС"),
}
TEXT = {
    "answer": ("Natija", "Результат"),
    "no_match": (
        "Bu shartlarga mos yozuv topilmadi.",
        "Записей по этим условиям нет.",
    ),
    "error": (
        "Javobni hisoblay olmadik. Qayta urinib ko‘ring. Bu ma’lumot yo‘q degani emas.",
        "Не удалось получить ответ. Попробуйте ещё раз. Это не значит, что данных нет.",
    ),
    "outside_dates": (
        "Bu davr uchun to‘liq ma’lumot yo‘q. Bitimlar: 03.01.2022 dan 30.10.2026 gacha.",
        "За этот период нет полных данных. Сделки: с 03.01.2022 по 30.10.2026.",
    ),
    "missing_field": (
        "Bu ma’lumot reyestrda yo‘q.",
        "Этих сведений в реестре нет.",
    ),
    "unsupported": (
        "Bu ma’lumotlardan savolga aniq javob topib bo‘lmaydi.",
        "По этим данным нельзя дать точный ответ.",
    ),
    "ambiguous_entity": (
        "Qaysi kompaniya, tovar yoki hudud? Aniq nomi yoki kodini yozing.",
        "О какой компании, товаре или регионе речь? Укажите название или код.",
    ),
    "ambiguous_metric": (
        "Qaysi ko‘rsatkich va davr kerakligini aniqlashtiring.",
        "Уточните необходимый показатель и период.",
    ),
    "mixed_units": (
        "Bu birliklarni qo‘shib bo‘lmaydi. Qaysi birlik kerak?",
        "Эти единицы нельзя складывать. Какая единица нужна?",
    ),
    "mixed_currencies": (
        "Valyutani aniqlashtiring: so‘mga aylantiraymi yoki valyutalar bo‘yicha alohida ko‘rsataymi?",
        "Уточните валюту: пересчитать в сумы или показать отдельно по валютам?",
    ),
    "not_found": ("Aniq nom yoki kodni yozing.", "Укажите точное название или код."),
}


def tr(values: tuple[str, str], language: str) -> str:
    return values[1 if language == "ru" else 0]


def label(expression: str, language: str) -> str:
    if expression in LABELS:
        return tr(LABELS[expression], language)
    try:
        parsed = sqlglot.parse_one(expression, read="duckdb")
        if isinstance(parsed, exp.Column):
            return tr(LABELS.get(parsed.name, (parsed.name, parsed.name)), language)
        if isinstance(parsed, exp.Filter):
            return (
                tr(("Shartga mos", "По условию"), language)
                + ": "
                + label(parsed.this.sql(dialect="duckdb"), language)
            )
        if isinstance(parsed, exp.Extract):
            parts = {
                "YEAR": ("yil", "год"),
                "MONTH": ("oy", "месяц"),
                "DAY": ("kun", "день"),
                "QUARTER": ("chorak", "квартал"),
            }
            part = str(parsed.this).upper()
            if part in parts:
                return (
                    label(parsed.expression.sql(dialect="duckdb"), language)
                    + ": "
                    + tr(parts[part], language)
                )
        if isinstance(parsed, exp.AggFunc):
            prefixes = {
                "COUNT": ("Soni", "Количество"),
                "SUM": ("Jami", "Итого"),
                "MIN": ("Eng kichik", "Минимум"),
                "MAX": ("Eng katta", "Максимум"),
            }
            field = parsed.this.sql(dialect="duckdb")
            if field == "*":
                return tr(("Yozuvlar soni", "Количество записей"), language)
            prefix = tr(prefixes[parsed.sql_name()], language)
            return f"{prefix}: {label(field, language)}"
    except (ValueError, KeyError, AttributeError):
        pass
    return expression


def format_value(value, language: str) -> str:
    if value is None:
        return tr(("Ko‘rsatilmagan", "Не указано"), language)
    if isinstance(value, bool):
        return tr(("Ha", "Да"), language) if value else tr(("Yo‘q", "Нет"), language)
    return localize(str(value), language)


def render_calculation(data: Evidence, language: str) -> str:
    match = re.fullmatch(
        r"(ratio|percentage|change_percent)\((\w+), (\w+)\); ROUND_HALF_UP, (\d) decimals",
        data.calculation or "",
    )
    if not match:
        return data.calculation or ""
    operation, numerator, denominator, scale = match.groups()
    n = label(data.expressions.get(numerator, numerator), language)
    d = label(data.expressions.get(denominator, denominator), language)
    formula = f"({n}) ÷ ({d})"
    if operation == "percentage":
        formula += " × 100%"
    elif operation == "change_percent":
        formula = f"(({n}) − ({d})) ÷ ({d}) × 100%"
    precision = tr(
        (f"{scale} kasr xonasigacha yaxlitlangan", f"округлено до {scale} знаков"), language
    )
    return f"{formula}; {precision}"


def render_answer(answer: Answer) -> str:
    lang = answer.language
    if answer.outcome == "error":
        return tr(TEXT["error"], lang)
    if answer.outcome in {"unavailable", "clarify"}:
        lines = [tr(TEXT.get(answer.reason, TEXT["unsupported"]), lang)]
        for item in answer.candidates:
            lines.append(" · ".join(str(v) for k, v in item.items() if k not in {"score", "match"}))
        return "\n".join(lines)
    data = answer.evidence
    if data is None:
        return tr(TEXT["error"], lang)
    lines = [tr(TEXT["no_match"], lang)] if answer.outcome == "no_match" else []
    for index, row in enumerate(data.rows[:10], 1):
        if len(data.rows) > 1:
            lines.append(f"\n{index}.")
        for key, value in row.items():
            lines.append(
                f"{label(data.expressions.get(key, key), lang)}: {format_value(value, lang)}"
            )
    lines.append("")
    if data.period_start:
        if data.period_start == data.period_end:
            lines.append(tr(("Sana", "Дата"), lang) + f": {data.period_start}")
        else:
            period = tr(
                (
                    f"{data.period_start} dan {data.period_end} gacha",
                    f"с {data.period_start} по {data.period_end}",
                ),
                lang,
            )
            lines.append(tr(("Davr", "Период"), lang) + f": {period}")
    if data.matched_count != 1:
        lines.append(
            tr(("Hisobga olingan yozuvlar", "Учтено записей"), lang)
            + f": {data.matched_count:,}".replace(",", " ")
        )
    expressions = " ".join(data.expressions.values()).lower()
    if (
        data.currencies
        and re.search(r"\b(amount|starting_price|base_price)\b", expressions)
        and not re.search(r"\bcurrency\b", expressions)
    ):
        lines.append(
            tr(("Valyuta", "Валюта"), lang)
            + ": "
            + ", ".join(localize(value, lang) for value in data.currencies)
        )
    if (
        data.units
        and re.search(
            r"\b(volume|delivered_volume|starting_price|base_price|lot_size)\b", expressions
        )
        and not re.search(r"\bunit\b", expressions)
    ):
        lines.append(
            tr(("Birlik", "Единица"), lang)
            + ": "
            + ", ".join(localize(value, lang) for value in data.units)
        )
    if len(data.rows) > 10 or data.truncated:
        lines.append(
            tr(
                (
                    f"Ko‘rsatilgan: {min(len(data.rows), 10)} natija. CSVda: {len(data.rows)} qator.",
                    f"Показано: {min(len(data.rows), 10)} результатов. В CSV: {len(data.rows)} строк.",
                ),
                lang,
            )
        )
    if data.calculation:
        lines.append(tr(("Hisob", "Расчёт"), lang) + ": " + render_calculation(data, lang))
    if data.truncated:
        lines.append(
            tr(
                (
                    "Natija dastlabki 100 qator bilan cheklangan.",
                    "Результат ограничен первыми 100 строками.",
                ),
                lang,
            )
        )
    return "\n".join(lines).strip()


def render_sources(data: Evidence, language: str) -> str:
    lines = [tr(("Manbalar", "Источники"), language)]
    lines.append(
        tr(
            (
                "Bitimlar holati: 30.10.2026. Ma’lumotlar o‘ylab topilgan.",
                "Состояние сделок: 30.10.2026. Данные вымышленные.",
            ),
            language,
        )
    )
    lines.append(tr(("Mos yozuvlar", "Совпавших записей"), language) + f": {data.matched_count}")
    lines.append(tr(("Hisoblash sharti", "Условия расчёта"), language) + ":\n" + data.sql)
    if data.calculation:
        lines.append(data.calculation)
    lines.append(tr(("Mos yozuvlardan misollar", "Примеры исходных записей"), language) + ":")
    for row in data.samples:
        lines.append(
            "; ".join(f"{label(k, language)}: {format_value(v, language)}" for k, v in row.items())
        )
    lines.append(
        tr(
            (
                "Bu faqat misollar. Bo‘sh maydon nol degani emas.",
                "Это примеры записей. Пустое поле не означает ноль.",
            ),
            language,
        )
    )
    return "\n".join(lines)


def split_text(text: str, limit: int = 3500) -> list[str]:
    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current.rstrip())
            current = ""
        current += line
    if current:
        chunks.append(current.rstrip())
    return chunks or [""]


def export_csv(data: Evidence) -> bytes:
    output = io.StringIO()
    if data.rows:
        writer = csv.DictWriter(output, fieldnames=list(data.rows[0]))
        writer.writeheader()
        for row in data.rows:
            safe = {
                k: ("'" + v if isinstance(v, str) and re.match(r"^[=+@\-\t\r]", v) else v)
                for k, v in row.items()
            }
            writer.writerow(safe)
    return output.getvalue().encode("utf-8-sig")
