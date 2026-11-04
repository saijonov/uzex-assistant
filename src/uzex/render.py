import csv
import io
import re
from decimal import Decimal

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from uzex.database import DEAL_TABLES
from uzex.localization import localize
from uzex.models import Answer, Evidence
from uzex.policy import CLARIFICATION_TEXT
from uzex.terminology import display_value

LABELS = {
    "deal_id": ("Bitim raqami", "Номер сделки"),
    "contract_id": ("Shartnoma raqami", "Номер контракта"),
    "deal_date": ("Bitim sanasi", "Дата сделки"),
    "deal_time": ("Vaqt", "Время"),
    "product_name": ("Tovar", "Товар"),
    "product": ("Mahsulot", "Продукт"),
    "product_family": ("Tovar (umumiy nom)", "Товар (единое название)"),
    "unit_price": ("Birlik narxi", "Цена за единицу"),
    "mass_t": ("Massa, t", "Масса, т"),
    "seller_activity": ("Sotuvchi faoliyati", "Вид деятельности продавца"),
    "buyer_activity": ("Xaridor faoliyati", "Вид деятельности покупателя"),
    "seller_broker_region": ("Sotuvchi brokeri hududi", "Регион брокера продавца"),
    "buyer_broker_region": ("Xaridor brokeri hududi", "Регион брокера покупателя"),
    "broker_name": ("Broker", "Брокер"),
    "broker_region": ("Broker hududi", "Регион брокера"),
    "broker_side": ("Broker tomoni", "Сторона брокера"),
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
    "grade": ("Nav", "Сорт"),
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
    "not_found": (
        "Bu nom reyestrda topilmadi. Aniq nom yoki kodni yozing.",
        "Такого названия в реестре нет. Укажите точное название или код.",
    ),
    "needs_detail": (
        "Bu tafsilotsiz aniq javob bera olmayman. Savolni raqam, nom yoki davr bilan to‘liq yozing.",
        "Без этой детали точно ответить не могу. Напишите вопрос целиком: с номером, названием или периодом.",
    ),
}


def tr(values: tuple[str, str], language: str) -> str:
    return values[1 if language == "ru" else 0]


def error_text(language: str) -> str:
    return tr(TEXT["error"], language)


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
            if isinstance(parsed.this, exp.Distinct):
                fields = ", ".join(
                    label(item.sql(dialect="duckdb"), language) for item in parsed.this.expressions
                )
                if parsed.sql_name() == "COUNT":
                    return (
                        tr(("Turli qiymatlar soni", "Количество разных значений"), language)
                        + f": {fields}"
                    )
                prefix = tr(prefixes[parsed.sql_name()], language)
                return f"{prefix}, {tr(('takrorlanmasdan', 'без повторов'), language)}: {fields}"
            field = parsed.this.sql(dialect="duckdb")
            if field == "*":
                return tr(("Yozuvlar soni", "Количество записей"), language)
            prefix = tr(prefixes[parsed.sql_name()], language)
            return f"{prefix}: {label(field, language)}"
    except (ValueError, KeyError, AttributeError, SqlglotError):
        pass
    return expression


def source_field(expression: str) -> str | None:
    match = re.fullmatch(r"(?:\w+\.)?(\w+)", expression)
    return match.group(1) if match else None


def format_value(value, language: str, field: str | None = None) -> str:
    if value is None:
        return tr(("Ko‘rsatilmagan", "Не указано"), language)
    if isinstance(value, bool):
        return tr(("Ha", "Да"), language) if value else tr(("Yo‘q", "Нет"), language)
    protected = {
        "deal_id",
        "contract_id",
        "seller_inn",
        "buyer_inn",
        "inn",
        "hs_code",
        "brand",
        "size",
        "name",
        "seller_name",
        "buyer_name",
        "seller_broker_name",
        "buyer_broker_name",
        "warehouse_address",
    }
    number = str(value)
    if field not in protected and re.fullmatch(r"-?\d+(?:\.\d+)?", number):
        whole, dot, fraction = number.partition(".")
        fraction = fraction.rstrip("0")
        if field in {"amount", "amount_uzs", "starting_price", "base_price", "usd_uzs"}:
            fraction = fraction.ljust(2, "0")
        sign = "-" if whole.startswith("-") else ""
        whole = sign + f"{abs(int(whole)):,}".replace(",", " ")
        return whole + ("." + fraction if fraction else "")
    return display_value(str(value), language, field)


DETAIL_SECTIONS = [
    (
        ("Bitim", "Сделка"),
        [
            "deal_id",
            "deal_date",
            "deal_time",
            "status",
            "auction_type",
            "contract_id",
            "contract_type",
            "contract_form",
        ],
    ),
    (
        ("Tovar", "Товар"),
        [
            "product_name",
            "product",
            "brand",
            "size",
            "grade",
            "product_type",
            "product_class",
            "hs_code",
            "category",
            "product_group",
            "industry",
            "unit",
        ],
    ),
    (
        ("Narx va hajm", "Цена и объём"),
        [
            "quantity_lots",
            "lot_size",
            "volume",
            "mass_kg",
            "amount",
            "currency",
            "unit_price",
            "starting_price",
            "base_price",
            "amount_uzs",
            "usd_uzs",
            "deposit_percent",
        ],
    ),
    (
        ("To‘lov va yetkazish", "Оплата и поставка"),
        [
            "paid_on",
            "payment_due",
            "payment_days",
            "delivered_on",
            "delivery_due",
            "delivery_days",
            "delivered_lots",
            "delivered_volume",
            "delivered_mass_kg",
            "delivery_basis",
            "packaging",
            "region",
            "region_ru",
            "warehouse_address",
        ],
    ),
    (
        ("Ishtirokchilar", "Участники"),
        [
            "seller_name",
            "seller_inn",
            "seller_region",
            "seller_vat_payer",
            "seller_activity",
            "seller_broker_name",
            "seller_broker_code",
            "seller_broker_region",
            "buyer_name",
            "buyer_inn",
            "buyer_region",
            "buyer_vat_payer",
            "buyer_activity",
            "buyer_broker_name",
            "buyer_broker_code",
            "buyer_broker_region",
        ],
    ),
    (("Shartnoma muddati", "Срок контракта"), ["registered_on", "valid_until"]),
]


def render_detail(row: dict, data: Evidence, language: str) -> list[str]:
    identity = row["deal_id"]
    lines = [tr((f"{identity}-bitim haqida ma’lumot.", f"Данные по сделке {identity}."), language)]
    skip = {"source_file", "source_row", "product_family", "mass_t"}
    if "status" in row:
        skip.add("is_cancelled")
    if row.get("product_name"):
        skip.add("product")
    if (
        row.get("currency") == "Узбекский сум"
        and row.get("amount_uzs") is not None
        and row.get("amount") is not None
        and Decimal(str(row["amount_uzs"])) == Decimal(str(row["amount"]))
    ):
        skip.add("amount_uzs")
    if row.get("unit") == "килограмм":
        skip.update({"mass_kg", "delivered_mass_kg"})
    if localize(str(row.get("region")), language) == localize(str(row.get("region_ru")), language):
        skip.add("region_ru")
    used = set(skip)
    missing = []
    for title, fields in DETAIL_SECTIONS:
        values = []
        for key in fields:
            if key in row and key not in used:
                used.add(key)
                if row[key] is None:
                    missing.append(label(key, language).lower())
                else:
                    field = source_field(data.expressions.get(key, key))
                    values.append(
                        f"{label(data.expressions.get(key, key), language)}: {format_value(row[key], language, field)}"
                    )
        if values:
            lines.extend(["", tr(title, language), *values])
    for key, value in row.items():
        if key not in used:
            field = source_field(data.expressions.get(key, key))
            lines.append(
                f"{label(data.expressions.get(key, key), language)}: {format_value(value, language, field)}"
            )
    if missing:
        lines.extend(
            ["", tr(("Ko‘rsatilmagan", "Не указано"), language) + ": " + ", ".join(missing) + "."]
        )
    return lines


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


def cancellation_note(data: Evidence, language: str) -> str | None:
    tree = sqlglot.parse_one(data.sql, read="duckdb")
    where = tree.args.get("where")
    if where is None:
        return None
    root = where.this
    conditions = list(root.flatten()) if isinstance(root, exp.And) else [root]
    for condition in conditions:
        if isinstance(condition, exp.Not) and isinstance(condition.this, exp.Column):
            if condition.this.name == "is_cancelled":
                return tr(
                    ("Bekor qilingan bitimlar kiritilmagan.", "Аннулированные сделки исключены."),
                    language,
                )
        if isinstance(condition, exp.EQ) and isinstance(condition.this, exp.Column):
            if condition.this.name == "is_cancelled" and isinstance(
                condition.expression, exp.Boolean
            ):
                return tr(
                    ("Faqat bekor qilingan bitimlar.", "Только аннулированные сделки.")
                    if condition.expression.this
                    else (
                        "Bekor qilingan bitimlar kiritilmagan.",
                        "Аннулированные сделки исключены.",
                    ),
                    language,
                )
    return None


def render_answer(answer: Answer, page: int = 0) -> str:
    lang = answer.language
    if answer.outcome == "error":
        return tr(TEXT["error"], lang)
    if answer.outcome in {"unavailable", "clarify"}:
        lines = (
            [tr(CLARIFICATION_TEXT[field], lang) for field in answer.missing_fields]
            if answer.missing_fields
            else [tr(TEXT.get(answer.reason, TEXT["unsupported"]), lang)]
        )
        for index, item in enumerate(answer.candidates, 1):
            parts = [str(item["name"])] if item.get("name") else []
            if item.get("inn"):
                parts.append(tr(("STIR", "ИНН"), lang) + ": " + str(item["inn"]))
            if item.get("broker_code"):
                parts.append(str(item["broker_code"]))
            if item.get("region_ru"):
                parts = [localize(str(item["region_ru"]), lang)]
            lines.append(f"{index}. " + "; ".join(parts))
        return "\n".join(lines)
    data = answer.evidence
    if data is None:
        return tr(TEXT["error"], lang)
    if page < 0 or page > max((len(data.rows) - 1) // 10, 0):
        raise ValueError("Result page does not exist")
    start = page * 10
    lines = [tr(TEXT["no_match"], lang)] if answer.outcome == "no_match" else []
    for index, row in enumerate(data.rows[start : start + 10], start + 1):
        if len(data.rows) > 1:
            lines.append(f"\n{index}.")
        if len(row) >= 15 and source_field(data.expressions.get("deal_id", "")) == "deal_id":
            lines.extend(render_detail(row, data, lang))
            continue
        for key, value in row.items():
            if source_field(data.expressions.get(key, key)) in {"source_file", "source_row"}:
                continue
            field = source_field(data.expressions.get(key, key))
            lines.append(
                f"{label(data.expressions.get(key, key), lang)}: {format_value(value, lang, field)}"
            )
    lines.append("")
    if data.selection == "random":
        lines.append(tr(("Tanlov: tasodifiy yozuvlar.", "Выборка: случайные записи."), lang))
    already_shows_date = len(data.rows) == 1 and any(
        source_field(value) == "deal_date" for value in data.expressions.values()
    )
    if data.period_start and not already_shows_date:
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
    record_count = (
        data.selected_record_count if data.selected_record_count is not None else data.matched_count
    )
    if record_count != 1:
        lines.append(
            tr(
                ("Hisobga olingan yozuvlar", "Учтено записей")
                if data.table in DEAL_TABLES
                else ("Topilgan yozuvlar", "Найдено записей"),
                lang,
            )
            + f": {record_count:,}".replace(",", " ")
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
                    f"Ko‘rsatilgan: {start + 1} dan {min(start + 10, len(data.rows))} gacha. Jami natija: {len(data.rows)}.",
                    f"Показаны записи с {start + 1} по {min(start + 10, len(data.rows))}. Всего в результате: {len(data.rows)}.",
                ),
                lang,
            )
        )
    if data.calculation:
        lines.append(tr(("Hisob", "Расчёт"), lang) + ": " + render_calculation(data, lang))
    note = cancellation_note(data, lang)
    if note:
        lines.append(note)
    if data.truncated:
        lines.append(
            tr(
                (
                    f"Natija dastlabki {data.row_limit} qator bilan cheklangan.",
                    f"Результат ограничен первыми {data.row_limit} строками.",
                ),
                lang,
            )
        )
    source_names = {
        "contracts": "contracts.csv",
        "participants": "participants.csv",
        "brokers": "brokers.csv",
        "usd_rates": "usd_rates.csv",
    }
    if data.table == "registry":
        if data.selected_record_count == 1 and data.samples:
            sample = data.samples[0]
            source = str(sample["source_file"]) + tr(
                (f", {sample['source_row']}-qator", f", строка {sample['source_row']}"), lang
            )
        else:
            source = tr(("birja bitimlari reyestri", "реестр биржевых сделок"), lang)
    else:
        source = source_names.get(data.table, data.table)
    lines.append(tr(("Manba", "Источник"), lang) + ": " + source)
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
    lines.append(
        tr(("Qidiruvdagi yozuvlar", "Записей в области поиска"), language)
        + f": {data.matched_count}"
    )
    if data.selected_record_count is not None:
        lines.append(
            tr(("Tanlangan bitimlar", "Выбрано сделок"), language)
            + f": {data.selected_record_count}"
        )
    lines.append(tr(("Hisoblash sharti", "Условия расчёта"), language) + ":\n" + data.sql)
    if data.calculation:
        lines.append(data.calculation)
    originals = []
    for row in data.rows[:3]:
        for key in ("product_name", "product"):
            if row.get(key) and row[key] not in originals:
                originals.append(row[key])
    if originals:
        lines.append(
            tr(("Manbadagi tovar nomlari", "Названия товаров в источнике"), language) + ":"
        )
        lines.extend(originals)
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
