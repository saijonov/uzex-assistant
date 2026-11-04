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
    "seller_vat_payer": ("Sotuvchi QQS to‘lovchisi", "Продавец — плательщик НДС"),
    "buyer_vat_payer": ("Xaridor QQS to‘lovchisi", "Покупатель — плательщик НДС"),
}
TEXT = {
    "answer": ("Ma’lumotlar bo‘yicha natija", "Результат по данным"),
    "no_match": (
        "Berilgan shartlarga mos yozuvlar topilmadi.",
        "Записей по заданным условиям не найдено.",
    ),
    "error": (
        "Xizmat vaqtincha javob bera olmadi. Qayta urinib ko‘ring. Bu ma’lumot yo‘qligini anglatmaydi.",
        "Сервис временно не смог ответить. Повторите запрос. Это не означает отсутствие данных.",
    ),
    "outside_dates": (
        "So‘ralgan davr to‘liq ma’lumotlarda mavjud emas. Ma’lumotlar: 03.01.2022–30.10.2026.",
        "Запрошенный период не полностью покрыт данными. Доступны данные за 03.01.2022–30.10.2026.",
    ),
    "missing_field": (
        "Bu ma’lumot berilgan to‘plamda mavjud emas.",
        "Эта информация отсутствует в предоставленном наборе данных.",
    ),
    "unsupported": (
        "Bu savolga berilgan ma’lumotlar asosida tasdiqlangan javob berib bo‘lmaydi.",
        "На этот вопрос нельзя дать подтверждённый ответ по предоставленным данным.",
    ),
    "ambiguous_entity": (
        "Qaysi kompaniya, tovar yoki hududni nazarda tutdingiz? Nomini yoki kodini aniqlashtiring.",
        "Уточните компанию, товар или регион: укажите название или код.",
    ),
    "ambiguous_metric": (
        "Qaysi ko‘rsatkich va davr kerakligini aniqlashtiring.",
        "Уточните необходимый показатель и период.",
    ),
    "mixed_units": (
        "Bir-biriga mos bo‘lmagan o‘lchov birliklari bor. Kerakli birlikni aniqlashtiring.",
        "Есть несовместимые единицы измерения. Уточните нужную единицу.",
    ),
    "mixed_currencies": (
        "Valyutani aniqlashtiring: so‘mga aylantiraymi yoki valyutalar bo‘yicha alohida ko‘rsataymi?",
        "Уточните валюту: пересчитать в сумы или показать отдельно по валютам?",
    ),
    "not_found": ("Aniq nom yoki kodni yuboring, iltimos.", "Пришлите точное название или код."),
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
    lines = [tr(TEXT[answer.outcome], lang)]
    for index, row in enumerate(data.rows[:10], 1):
        if len(data.rows) > 1:
            lines.append(f"\n{index}.")
        for key, value in row.items():
            lines.append(
                f"{label(data.expressions.get(key, key), lang)}: {format_value(value, lang)}"
            )
    lines.append("")
    if data.period_start:
        lines.append(tr(("Davr", "Период"), lang) + f": {data.period_start} — {data.period_end}")
    lines.append(
        tr(("Mos yozuvlar", "Совпавших записей"), lang)
        + f": {data.matched_count:,}".replace(",", " ")
    )
    if data.currencies:
        lines.append(
            tr(("Manba valyutalari", "Валюты исходных данных"), lang)
            + ": "
            + ", ".join(localize(value, lang) for value in data.currencies)
        )
    if data.units:
        lines.append(
            tr(("Manba birliklari", "Единицы исходных данных"), lang)
            + ": "
            + ", ".join(localize(value, lang) for value in data.units)
        )
    if len(data.rows) > 10 or data.truncated:
        lines.append(
            tr(
                (
                    "Dastlabki 10 natija ko‘rsatilgan. CSV eksporti cheklangan natijani beradi (ko‘pi bilan 100 qator).",
                    "Показаны первые 10 результатов. CSV содержит ограниченный результат запроса (не более 100 строк).",
                ),
                lang,
            )
        )
    if data.calculation:
        lines.append(tr(("Hisob", "Расчёт"), lang) + ": " + render_calculation(data, lang))
    lines.append(
        tr(
            (
                "Manbalar tugmasida shartlar va dalillar bor.",
                "Условия и подтверждения доступны по кнопке «Источники».",
            ),
            lang,
        )
    )
    return "\n".join(lines)


def render_sources(data: Evidence, language: str) -> str:
    lines = [tr(("Manbalar va hisoblash", "Источники и расчёт"), language)]
    lines.append(
        tr(
            (
                "Reyestr holati: 30.10.2026. Barcha ma’lumotlar o‘ylab topilgan.",
                "Состояние реестра: 30.10.2026. Все данные вымышленные.",
            ),
            language,
        )
    )
    lines.append(tr(("Mos yozuvlar", "Совпавших записей"), language) + f": {data.matched_count}")
    lines.append(tr(("Qo‘llangan so‘rov", "Выполненный запрос"), language) + ":\n" + data.sql)
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
                "Misollar barcha mos yozuvlar ro‘yxati emas. Bo‘sh maydon nol degani emas.",
                "Примеры не являются полным списком совпадений. Пустое поле не означает ноль.",
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
