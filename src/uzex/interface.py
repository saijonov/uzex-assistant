from html import escape

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MENU = {
    "examples": ("Misollar", "Примеры"),
    "help": ("Yordam", "Помощь"),
    "language": ("Til", "Язык"),
    "reset": ("Yangi suhbat", "Новый диалог"),
}
COPY = {
    "intro": (
        "UZEX21\nBirja bitimlari haqida so‘rang.",
        "UZEX21\nЗадавайте вопросы о биржевых сделках.",
    ),
    "choose_language": ("Tilni tanlang / Выберите язык", "Tilni tanlang / Выберите язык"),
    "ready": (
        "Savolingizni o‘zbek yoki rus tilida yozing.\nMasalan: 100001-bitimning sotuvchisi kim?",
        "Задайте вопрос на русском или узбекском.\nНапример: Кто продавец по сделке 100001?",
    ),
    "menu": ("Menyu", "Меню"),
    "help": (
        "Yordam\nBitim raqami, tovar yoki kompaniya nomini yozing. Hisob uchun davr va birlikni ham ko‘rsating.\n\n"
        "Menyu tilini o‘zgartirsangiz ham, javob savolingiz tilida bo‘ladi. Boshqa tilda javob kerak bo‘lsa, savolda ayting.\n\n"
        "Bitimlar: 03.01.2022 dan 30.10.2026 gacha.\nBarcha ma’lumotlar o‘ylab topilgan.",
        "Помощь\nУкажите номер сделки, товар или компанию. Для расчёта добавьте период и единицу.\n\n"
        "Язык меню не меняет язык ответов. Отвечаем на языке вопроса. Другой язык можно попросить в самом вопросе.\n\n"
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


def menu_action(value: str) -> str | None:
    return next((action for action, labels in MENU.items() if value in labels), None)


def main_keyboard(language: str) -> ReplyKeyboardMarkup:
    index = 1 if language == "ru" else 0
    buttons = {key: KeyboardButton(text=labels[index]) for key, labels in MENU.items()}
    return ReplyKeyboardMarkup(
        keyboard=[[buttons["examples"], buttons["help"]], [buttons["language"], buttons["reset"]]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Savolingizni yozing" if language == "uz" else "Задайте вопрос",
    )


def telegram_html(value: str) -> str:
    titles = {
        "UZEX21",
        "Menyu",
        "Меню",
        "Yordam",
        "Помощь",
        "Misollar",
        "Примеры",
        "Manbalar",
        "Источники",
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
