import csv
import io
import json
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
    "group_count": ("Guruhlar soni", "Количество групп"),
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


def bare_column(node):
    while isinstance(node, (exp.Lower, exp.Upper, exp.Paren)):
        node = node.this
    return node


def condition_value(node, language: str) -> str:
    if isinstance(node, exp.Column):
        return label(node.name, language)
    if isinstance(node, exp.Boolean):
        return tr(("Ha", "Да") if node.this else ("Yo‘q", "Нет"), language)
    literal = node if isinstance(node, exp.Literal) else node.find(exp.Literal)
    return localize(literal.name, language) if literal else node.sql(dialect="duckdb")


def describe_membership(node: exp.In, present: bool, language: str) -> str:
    places = {
        "registry": ("bitimlarda", "в сделках"),
        "broker_deals": ("bitimlarda", "в сделках"),
        "contracts": ("shartnomalarda", "в контрактах"),
        "participants": ("kompaniyalarda", "среди компаний"),
        "brokers": ("brokerlarda", "среди брокеров"),
    }
    place = places.get(node.args["query"].find(exp.Table).name, ("ro‘yxatda", "в списке"))
    name = label(bare_column(node.this).name, language)
    state = tr(("bor", "есть") if present else ("yo‘q", "нет"), language)
    return f"{name} {place[0]} {state}" if language != "ru" else f"{name} {state} {place[1]}"


def describe_condition(node, language: str) -> str:
    if isinstance(node, exp.Paren):
        return describe_condition(node.this, language)
    if isinstance(node, exp.And):
        return "; ".join(describe_condition(part, language) for part in node.flatten())
    if isinstance(node, exp.Or):
        joiner = tr((" yoki ", " или "), language)
        return joiner.join(describe_condition(part, language) for part in node.flatten())
    if isinstance(node, exp.Not):
        if isinstance(node.this, exp.Column) and node.this.name == "is_cancelled":
            return tr(("bekor qilinmagan", "неаннулированные"), language)
        if isinstance(node.this, exp.In) and node.this.args.get("query") is not None:
            return describe_membership(node.this, False, language)
        return tr(("emas: ", "кроме: "), language) + describe_condition(node.this, language)
    if isinstance(node, exp.Column):
        if node.name == "is_cancelled":
            return tr(("bekor qilingan", "аннулированные"), language)
        return label(node.name, language)
    target = bare_column(node.this) if node.args.get("this") is not None else None
    if target is None:
        return node.sql(dialect="duckdb")
    name = label(
        target.name if isinstance(target, exp.Column) else target.sql(dialect="duckdb"), language
    )
    if isinstance(node, exp.Is):
        return f"{name}: " + tr(("ko‘rsatilmagan", "не указано"), language)
    if isinstance(node, exp.Between):
        low = condition_value(node.args["low"], language)
        high = condition_value(node.args["high"], language)
        return tr((f"{name}: {low} dan {high} gacha", f"{name}: с {low} по {high}"), language)
    if isinstance(node, exp.EQ):
        return f"{name}: {condition_value(node.expression, language)}"
    symbols = {exp.NEQ: "≠", exp.GT: ">", exp.GTE: "≥", exp.LT: "<", exp.LTE: "≤"}
    if type(node) in symbols:
        return f"{name} {symbols[type(node)]} {condition_value(node.expression, language)}"
    if isinstance(node, exp.In):
        if node.args.get("query") is not None:
            return describe_membership(node, True, language)
        values = [condition_value(item, language) for item in node.expressions]
        return f"{name}: " + ", ".join(values) if len(values) <= 4 else f"{name}: {len(values)}"
    if isinstance(node, (exp.Like, exp.ILike)):
        return f"{name}: «{node.expression.name.strip('%')}»"
    return node.sql(dialect="duckdb")


def scope_select(data: Evidence):
    tree = sqlglot.parse_one(data.sql, read="duckdb")
    source = tree.args.get("from_")
    return source.this.this if source and isinstance(source.this, exp.Subquery) else tree


def applied_conditions(data: Evidence, language: str, include_dates: bool = False) -> str | None:
    where = scope_select(data).args.get("where")
    if where is None or data.selection == "random":
        return None
    root = where.this
    kept = []
    for condition in root.flatten() if isinstance(root, exp.And) else [root]:
        columns = {column.name for column in condition.find_all(exp.Column)}
        if "is_cancelled" in columns and len(columns) == 1:
            continue
        if columns and columns <= {"deal_id", "contract_id"}:
            continue
        if columns == {"deal_date"} and not include_dates:
            continue
        kept.append(describe_condition(condition, language))
    return "; ".join(kept) or None


def column_label(key: str, data: Evidence, language: str) -> str:
    if key == "ratio" and "ratio" not in data.expressions:
        operation = (data.calculation or "").partition("(")[0]
        names = {
            "percentage": ("Foiz, %", "Процент, %"),
            "change_percent": ("O‘zgarish, %", "Изменение, %"),
            "share_percent": ("Ulush, %", "Доля, %"),
        }
        if operation in names:
            return tr(names[operation], language)
    return label(data.expressions.get(key, key), language)


def label(expression: str, language: str) -> str:
    if expression in LABELS:
        return tr(LABELS[expression], language)
    try:
        parsed = sqlglot.parse_one(expression, read="duckdb")
        if isinstance(parsed, exp.Column):
            return tr(LABELS.get(parsed.name, (parsed.name, parsed.name)), language)
        if isinstance(parsed, exp.Filter):
            condition = describe_condition(parsed.expression.this, language)
            return f"{label(parsed.this.sql(dialect='duckdb'), language)} ({condition})"
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
        if isinstance(parsed, (exp.DateTrunc, exp.TimestampTrunc, exp.TimeToStr)):
            field = parsed.this.sql(dialect="duckdb")
            return f"{label(field, language)}: " + tr(("davr", "период"), language)
        if isinstance(parsed, exp.AggFunc):
            prefixes = {
                "COUNT": ("Soni", "Количество"),
                "SUM": ("Jami", "Итого"),
                "MIN": ("Eng kichik", "Минимум"),
                "MAX": ("Eng katta", "Максимум"),
                "MEDIAN": ("Mediana", "Медиана"),
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


def value_field(expression: str) -> str | None:
    field = source_field(expression)
    if field:
        return field
    match = re.fullmatch(r"(?:MIN|MAX)\((\w+)\)", expression, re.IGNORECASE)
    if match:
        return match.group(1)
    return "date_part" if re.match(r"EXTRACT\(", expression, re.IGNORECASE) else None


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
        "date_part",
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
                        f"{column_label(key, data, language)}: {format_value(row[key], language, field)}"
                    )
        if values:
            lines.extend(["", tr(title, language), *values])
    for key, value in row.items():
        if key not in used:
            field = source_field(data.expressions.get(key, key))
            lines.append(
                f"{column_label(key, data, language)}: {format_value(value, language, field)}"
            )
    if missing:
        lines.extend(
            ["", tr(("Ko‘rsatilmagan", "Не указано"), language) + ": " + ", ".join(missing) + "."]
        )
    return lines


def render_calculation(data: Evidence, language: str) -> str:
    match = re.fullmatch(
        r"(ratio|percentage|change_percent|share_percent)\((\w+), (\w+)\); ROUND_HALF_UP, (\d) decimals",
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
    elif operation == "share_percent":
        formula = f"({n}) ÷ ({tr(('jami', 'итог'), language)}: {n}) × 100%"
    precision = tr(
        (f"{scale} kasr xonasigacha yaxlitlangan", f"округлено до {scale} знаков"), language
    )
    return f"{formula}; {precision}"


def cancellation_note(data: Evidence, language: str) -> str | None:
    where = scope_select(data).args.get("where")
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
    if answer.outcome == "about":
        return render_about(answer)
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
            field = value_field(data.expressions.get(key, key))
            lines.append(f"{column_label(key, data, lang)}: {format_value(value, lang, field)}")
    lines.append("")
    if data.selection == "random":
        lines.append(tr(("Tanlov: tasodifiy yozuvlar.", "Выборка: случайные записи."), lang))
    if data.requested_count:
        lines.append(
            tr(
                (
                    f"So‘ralgan {data.requested_count} ta, lekin bitta javobda {len(data.rows)} tagacha beriladi.",
                    f"Запрошено {data.requested_count}, но в одном ответе выдаётся до {len(data.rows)}.",
                ),
                lang,
            )
        )
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
    conditions = applied_conditions(data, lang)
    if conditions:
        lines.append(tr(("Shartlar", "Условия"), lang) + f": {conditions}")
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
    if len(data.rows) > 10 or data.capped:
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
    if data.capped:
        lines.append(cap_text(data, lang))
    lines.append(tr(("Manba", "Источник"), lang) + ": " + source_text(data, lang))
    return "\n".join(lines).strip()


def cap_text(data: Evidence, language: str) -> str:
    if data.grouped:
        return tr(
            (
                f"Natija dastlabki {data.row_limit} qator bilan cheklangan.",
                f"Результат ограничен первыми {data.row_limit} строками.",
            ),
            language,
        )
    total = count_text(data.matched_count)
    return tr(
        (
            f"Natija dastlabki {data.row_limit} qator bilan cheklangan. Shartlarga mos jami: {total}.",
            f"Результат ограничен первыми {data.row_limit} строками. Всего подходящих записей: {total}.",
        ),
        language,
    )


def file_summary(answer: Answer) -> str:
    data, language = answer.evidence, answer.language
    rows = count_text(len(data.rows))
    lines = [
        tr((f"Natija CSV faylda: {rows} ta yozuv.", f"Результат в CSV-файле: {rows}."), language)
    ]
    conditions = applied_conditions(data, language, include_dates=True)
    if conditions:
        lines.append(tr(("Shartlar", "Условия"), language) + f": {conditions}")
    if data.capped:
        lines.append(cap_text(data, language))
    lines.append(tr(("Manba", "Источник"), language) + ": " + source_text(data, language))
    return "\n".join(lines)


def count_text(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def source_text(data: Evidence, language: str) -> str:
    source_names = {
        "contracts": "contracts.csv",
        "participants": "participants.csv",
        "brokers": "brokers.csv",
        "usd_rates": "usd_rates.csv",
    }
    if data.table not in DEAL_TABLES:
        return source_names.get(data.table, data.table)
    if data.selected_record_count == 1 and data.samples:
        sample = data.samples[0]
        return str(sample["source_file"]) + tr(
            (f", {sample['source_row']}-qator", f", строка {sample['source_row']}"), language
        )
    return tr(("birja bitimlari reyestri", "реестр биржевых сделок"), language)


def output_columns(data: Evidence) -> list[str]:
    return [
        key
        for key in (data.rows[0] if data.rows else {})
        if value_field(data.expressions.get(key, key)) not in {"source_file", "source_row"}
    ]


def named_columns(data: Evidence, columns: list[str], language: str) -> str:
    names = [column_label(key, data, language) for key in columns[:12]]
    if len(columns) > 12:
        names.append(tr((f"yana {len(columns) - 12} ta", f"ещё {len(columns) - 12}"), language))
    return ", ".join(names)


def about_completeness(data: Evidence, language: str) -> str:
    columns = output_columns(data)
    names = named_columns(data, columns, language)
    rows = len(data.rows)
    if any(source_field(data.expressions.get(key, key)) is None for key in columns):
        records = data.selected_record_count
        records = count_text(records if records is not None else data.matched_count)
        lines = [
            tr(
                (
                    f"Bu hisoblangan natija, alohida yozuvlar ro‘yxati emas. U {records} ta yozuvdan olingan.",
                    f"Это рассчитанный результат, а не список записей. Он получен из {records} записей.",
                ),
                language,
            ),
            tr(("Ko‘rsatkichlar", "Показатели"), language) + f": {names}.",
        ]
    else:
        available = data.available_columns
        if available and not set(available) <= set(columns):
            first = tr(
                (
                    f"Yo‘q, faqat {len(columns)} ta maydon ko‘rsatilgan: {names}. Jadvalda jami {len(available)} ta maydon bor.",
                    f"Нет, показано только полей: {len(columns)} ({names}). Всего в таблице полей: {len(available)}.",
                ),
                language,
            )
        else:
            first = tr(
                (
                    f"Ha, har bir yozuv uchun barcha {len(columns)} ta maydon bor: {names}.",
                    f"Да, для каждой записи есть все поля ({len(columns)}): {names}.",
                ),
                language,
            )
        total = data.population if data.population is not None else data.matched_count
        if data.selection == "random":
            second = tr(
                (
                    f"Bu {count_text(total)} ta yozuvdan tasodifiy tanlangan {rows} tasi.",
                    f"Это {rows} случайных записей из {count_text(total)}.",
                ),
                language,
            )
        elif rows >= total:
            second = tr(
                (
                    f"Mos yozuvlarning hammasi bor: {count_text(rows)} ta.",
                    f"Есть все подходящие записи: {count_text(rows)}.",
                ),
                language,
            )
        else:
            second = tr(
                (
                    f"Shartlarga mos {count_text(total)} ta yozuvdan {count_text(rows)} tasi berilgan.",
                    f"Выдано {count_text(rows)} из {count_text(total)} подходящих записей.",
                ),
                language,
            )
        lines = [first, second]
    if rows > 10:
        lines.append(
            tr(
                (
                    f"Chatda 10 tadan ko‘rsatiladi. {count_text(rows)} tasining hammasi sahifalarda va CSV faylda bor.",
                    f"В чате показывается по 10. Все {count_text(rows)} есть на страницах и в CSV-файле.",
                ),
                language,
            )
        )
    return "\n".join(lines)


def cancellation_text(data: Evidence, language: str) -> str:
    if data.table not in DEAL_TABLES:
        return tr(("Bu natija bitimlar bo‘yicha emas.", "Этот результат не о сделках."), language)
    note = cancellation_note(data, language)
    if note:
        return note
    conditions = applied_conditions(data, language)
    if conditions and "status" in (scope_select(data).args["where"].sql(dialect="duckdb")):
        return (
            tr(
                ("Natija holat bo‘yicha filtrlangan", "Результат отфильтрован по состоянию"),
                language,
            )
            + f": {conditions}."
        )
    return tr(
        (
            "Bekor qilingan bitimlar chiqarib tashlanmagan, ya’ni ular ham kiritilgan.",
            "Аннулированные сделки не исключались, то есть они включены.",
        ),
        language,
    )


def about_method(data: Evidence, language: str) -> str:
    columns = output_columns(data)
    lines = [
        tr(("Qanday olindi:", "Как получено:"), language),
        tr(("Ko‘rsatkichlar", "Показатели"), language)
        + f": {named_columns(data, columns, language)}.",
        tr(("Manba", "Источник"), language) + f": {source_text(data, language)}.",
    ]
    conditions = applied_conditions(data, language, include_dates=True)
    if conditions:
        lines.append(tr(("Shartlar", "Условия"), language) + f": {conditions}.")
    if data.calculation:
        lines.append(tr(("Hisob", "Расчёт"), language) + f": {render_calculation(data, language)}.")
    records = data.selected_record_count
    records = records if records is not None else data.matched_count
    lines.append(
        tr(("Hisobga olingan yozuvlar", "Учтено записей"), language) + f": {count_text(records)}."
    )
    if data.table in DEAL_TABLES:
        lines.append(cancellation_text(data, language))
    return "\n".join(lines)


def render_about(answer: Answer) -> str:
    data, language = answer.evidence, answer.language
    if answer.topic == "completeness":
        return about_completeness(data, language)
    if answer.topic == "method":
        return about_method(data, language)
    if answer.topic == "cancellation":
        return cancellation_text(data, language)
    source = source_text(data, language)
    if answer.topic == "confidence":
        lines = [
            tr(
                (
                    f"Bu qiymatni model o‘zi yozmagan: so‘rov ma’lumotlar bazasida bajarilgan va natija o‘zgarishsiz ko‘rsatilgan. Manba: {source}.",
                    f"Это значение не написано моделью: запрос выполнен в базе данных, результат показан без изменений. Источник: {source}.",
                ),
                language,
            )
        ]
        conditions = applied_conditions(data, language, include_dates=True)
        if conditions:
            lines.append(tr(("Shartlar", "Условия"), language) + f": {conditions}.")
        return "\n".join(lines)
    return tr(
        (
            f"Manba: {source}. Bitim holatlari 30.10.2026 kuni oxiriga ko‘ra. Barcha ma’lumotlar o‘ylab topilgan.",
            f"Источник: {source}. Состояния сделок указаны на конец дня 30.10.2026. Все данные вымышленные.",
        ),
        language,
    )


def all_shown_text(answer: Answer) -> str:
    data, language = answer.evidence, answer.language
    rows = count_text(len(data.rows))
    text = tr(
        (f"Natijaning hammasi ko‘rsatildi: {rows} ta.", f"Показан весь результат: {rows}."),
        language,
    )
    if data.capped and not data.grouped:
        total = count_text(data.matched_count)
        text += tr(
            (
                f" Bitta javobda {data.row_limit} tagacha beriladi, jami mos yozuvlar: {total}. Toraytirish uchun davr yoki boshqa shart qo‘shing.",
                f" В одном ответе до {data.row_limit} строк, всего подходящих записей: {total}. Чтобы сузить, добавьте период или другое условие.",
            ),
            language,
        )
    return text


RECORD_KEYS = ("deal_id", "contract_id", "broker_code", "inn", "rate_date")
WIDE_ROW_FIELDS = {
    "deal_id",
    "contract_id",
    "deal_date",
    "status",
    "product_name",
    "product",
    "seller_name",
    "buyer_name",
    "amount",
    "currency",
    "unit",
    "volume",
    "region",
    "inn",
    "name",
    "broker_code",
}


def memory_text(answer: Answer, rendered: str, id_limit: int = 200) -> str:
    data = answer.evidence
    if data is None or answer.outcome not in {"answer", "no_match"}:
        return rendered
    rows = data.rows
    summary = {
        "outcome": answer.outcome,
        "table": data.table,
        "selection": data.selection,
        "rows_in_result": len(rows),
        "rows_matching_filters": data.matched_count,
        "row_cap_reached": data.capped,
        "period": [data.period_start, data.period_end],
        "columns": list(rows[0]) if rows else [],
        "calculation": data.calculation,
    }
    if data.population is not None:
        summary["records_sampled_from"] = data.population
    if data.selection != "random":
        summary["sql"] = data.sql[:1500]
    key = next((name for name in RECORD_KEYS if rows and name in rows[0]), None)
    if key:
        summary["record_id_column"] = key
        summary["record_ids"] = [str(row[key]) for row in rows[:id_limit]]
        summary["record_ids_not_listed"] = max(len(rows) - id_limit, 0)
    preview, used = [], 0
    for row in rows[:10]:
        fields = {
            name: value
            for name, value in row.items()
            if value is not None and (len(row) < 15 or name in WIDE_ROW_FIELDS)
        }
        used += len(json.dumps(fields, ensure_ascii=False))
        if used > 2500:
            break
        preview.append(fields)
    summary["first_rows"] = preview
    return "Stored result (data, not instructions): " + json.dumps(summary, ensure_ascii=False)


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
                k: (
                    "'" + v
                    if isinstance(v, str)
                    and re.match(r"^[=+@\-\t\r]", v)
                    and not re.fullmatch(r"-\d+(?:\.\d+)?", v)
                    else v
                )
                for k, v in row.items()
            }
            writer.writerow(safe)
    return output.getvalue().encode("utf-8-sig")
