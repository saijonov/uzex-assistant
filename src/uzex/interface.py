import re
from html import escape

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from uzex.database import normalize

MENU = {
    "examples": ("Misollar / Примеры", "Misollar", "Примеры"),
    "help": ("Yordam / Помощь", "Yordam", "Помощь", "Til", "Язык"),
    "reset": ("Yangi suhbat / Новый диалог", "Yangi suhbat", "Новый диалог"),
}
COPY = {
    "start": (
        "UZEX21\nBirja bitimlari haqida o‘zbek yoki rus tilida so‘rang.\n"
        "Masalan: 100001-bitimning sotuvchisi kim?",
        "Задавайте вопросы о биржевых сделках на русском или узбекском.\n"
        "Например: Кто продавец по сделке 100001?",
    ),
    "greeting": (
        "Salom! Birja bitimlari haqida savolingiz bo‘lsa, yozing.",
        "Здравствуйте! Если есть вопрос о биржевых сделках, задавайте.",
    ),
    "greeting_assalom": (
        "Va alaykum assalom! Birja bitimlari haqida savolingiz bo‘lsa, yozing.",
        "Здравствуйте! Если есть вопрос о биржевых сделках, задавайте.",
    ),
    "thanks": (
        "Arzimaydi! Yana savolingiz bo‘lsa, yozing.",
        "Пожалуйста! Если будут ещё вопросы, пишите.",
    ),
    "about": (
        "Men UZEX21: birja bitimlari reyestri bo‘yicha savollarga javob beraman.\n"
        "Bitim, shartnoma, kompaniya, broker, narx, summa va hisob-kitoblarni so‘rang.\n"
        "Masalan: 2025-yilda eng ko‘p bitim qilgan 5 ta xaridor kim?",
        "Я UZEX21: отвечаю на вопросы по реестру биржевых сделок.\n"
        "Спрашивайте о сделках, контрактах, компаниях, брокерах, ценах, суммах и расчётах.\n"
        "Например: какие 5 покупателей совершили больше всего сделок в 2025 году?",
    ),
    "help": (
        "Yordam\nBitim raqami, tovar yoki kompaniya nomini yozing. Hisob uchun davr va birlikni ham ko‘rsating.\n\n"
        "O‘zbek yoki rus tilida yozing, javob savolingiz tilida bo‘ladi. Boshqa tilda javob kerak bo‘lsa, savolda ayting.\n\n"
        "CSV kerak bo‘lsa, «CSV qilib ber» deb yozing.\n\n"
        "Bitimlar: 03.01.2022 dan 30.10.2026 gacha.\nBarcha ma’lumotlar o‘ylab topilgan.",
        "Помощь\nУкажите номер сделки, товар или компанию. Для расчёта добавьте период и единицу.\n\n"
        "Пишите на русском или узбекском, ответ придёт на языке вопроса. Другой язык можно попросить в самом вопросе.\n\n"
        "Нужен файл? Напишите «Пришли CSV».\n\n"
        "Сделки: с 03.01.2022 по 30.10.2026.\nВсе данные вымышленные.",
    ),
    "examples": (
        "Misollar\n"
        "• 100001-bitimning sotuvchisi kim?\n"
        "• 2025-yilda nechta bitim bekor qilingan?\n"
        "• 100024-bitim summasi so‘mda qancha?\n\n"
        "Savolni o‘zingiz yozishingiz ham mumkin.",
        "Примеры\n"
        "• Кто продавец по сделке 100001?\n"
        "• Сколько сделок аннулировано в 2025 году?\n"
        "• Какова сумма сделки 100024 в сумах?\n\n"
        "Можно задать свой вопрос.",
    ),
    "reset": ("Yangi suhbat. Savolingizni yozing.", "Новый диалог. Задайте вопрос."),
    "text_only": ("Savolingizni matn bilan yozing.", "Напишите вопрос текстом."),
    "shorten": ("Savolni qisqartiring.", "Сократите вопрос."),
    "expired": (
        "Bu javob topilmadi. Savolni qayta yuboring.",
        "Ответ не найден. Отправьте вопрос ещё раз.",
    ),
}


def text(key: str, language: str) -> str:
    return COPY[key][1 if language == "ru" else 0]


def both(key: str) -> str:
    return "\n\n".join(COPY[key])


def menu_action(value: str) -> str | None:
    return next((action for action, labels in MENU.items() if value in labels), None)


SMALL_TALK = {
    ("greeting_assalom", "uz"): {
        "assalomu alaykum",
        "assalomu aleykum",
        "assalom alaykum",
        "assalom aleykum",
        "salom alaykum",
        "salom aleykum",
        "assalomalaykum",
        "salomaleykum",
    },
    ("thanks", "uz"): {
        "rahmat",
        "raxmat",
        "katta rahmat",
        "katta raxmat",
        "ok rahmat",
        "tashakkur",
        "thanks",
        "thank you",
    },
    ("thanks", "ru"): {
        "spasibo",
        "spasibo bolshoe",
        "bolshoe spasibo",
        "spasibo ponyatno",
        "ponyatno spasibo",
        "blagodaryu",
    },
    ("about", "uz"): {
        "nima qila olasan",
        "nimalar qila olasan",
        "nima qilasan",
        "qanday yordam bera olasan",
        "sen kimsan",
        "siz kimsiz",
        "what can you do",
        "who are you",
    },
    ("about", "ru"): {
        "chto ti umeesh",
        "chto ty umeesh",
        "chto umeesh",
        "chto vi umeete",
        "chto vy umeete",
        "kto ti",
        "kto ty",
        "kto vi",
        "kto vy",
        "chem mojesh pomoch",
        "chem mozhesh pomoch",
        "chem mojete pomoch",
        "chem mozhete pomoch",
    },
    ("greeting", "uz"): {
        "hello",
        "hi",
        "hey",
        "salom",
        "assalom",
        "salom yaxshimisiz",
        "yaxshimisiz",
        "xayrli tong",
        "xayrli kun",
        "xayrli kech",
        "nma gap",
        "nima gap",
        "nma gaplar",
        "nima gaplar",
        "salom nma gap",
        "salom nima gap",
        "ishlar qalay",
        "ishlar yaxshimi",
        "ahvollar qalay",
        "qalay",
        "qalaysiz",
        "qalesiz",
        "salom qalaysiz",
        "yaxshimisan",
    },
    ("greeting", "ru"): {
        "privet",
        "privetstvuyu",
        "zdravstvuyte",
        "zdravstvuite",
        "zdrastvuyte",
        "zdravstvuy",
        "zdraste",
        "zdrasti",
        "dobriy den",
        "dobryy den",
        "dobry den",
        "dobroe utro",
        "dobriy vecher",
        "dobryy vecher",
        "dobry vecher",
        "privet kak dela",
        "zdravstvuyte kak dela",
        "kak dela",
        "kak vi",
        "kak ti",
    },
}


def greeting(value: str) -> tuple[str, str] | None:
    normalized = normalize(value)
    if normalized == "salam":
        return "greeting", "ru" if re.search("[а-яА-ЯёЁ]", value) else "uz"
    for reply, phrases in SMALL_TALK.items():
        if normalized in phrases:
            return reply
    return None


def main_keyboard() -> ReplyKeyboardMarkup:
    buttons = {key: KeyboardButton(text=labels[0]) for key, labels in MENU.items()}
    return ReplyKeyboardMarkup(
        keyboard=[[buttons["examples"], buttons["help"]], [buttons["reset"]]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Savolingizni yozing / Задайте вопрос",
    )


def telegram_html(value: str) -> str:
    titles = {
        "UZEX21",
        "Yordam",
        "Помощь",
        "Misollar",
        "Примеры",
        "Manbalar",
        "Источники",
        "Bitim",
        "Сделка",
        "Tovar",
        "Товар",
        "Narx va hajm",
        "Цена и объём",
        "To‘lov va yetkazish",
        "Оплата и поставка",
        "Ishtirokchilar",
        "Участники",
        "Shartnoma muddati",
        "Срок контракта",
    }
    lines = []
    for line in value.split("\n"):
        if line in titles:
            lines.append(f"<b>{escape(line)}</b>")
        elif ": " in line and len(line.partition(": ")[0]) <= 65:
            key, _, content = line.partition(": ")
            lines.append(f"<b>{escape(key)}:</b> {escape(content)}")
        else:
            lines.append(escape(line))
    return "\n".join(lines)
