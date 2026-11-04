import re
import unicodedata
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
        "Menyu tilini o‘zgartirsangiz ham, javob savolingiz tilida bo‘ladi. Boshqa tilda javob kerak bo‘lsa, savolda ayting.\n\n"
        "CSV kerak bo‘lsa, «CSV qilib ber» deb yozing.\n\n"
        "Bitimlar: 03.01.2022 dan 30.10.2026 gacha.\nBarcha ma’lumotlar o‘ylab topilgan.",
        "Помощь\nУкажите номер сделки, товар или компанию. Для расчёта добавьте период и единицу.\n\n"
        "Язык меню не меняет язык ответов. Отвечаем на языке вопроса. Другой язык можно попросить в самом вопросе.\n\n"
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


def menu_action(value: str) -> str | None:
    return next((action for action, labels in MENU.items() if value in labels), None)


def greeting(value: str) -> tuple[str, str] | None:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = " ".join(re.sub(r"[^\w\s]", " ", normalized).split())
    if normalized in {
        "assalomu alaykum",
        "assalomu aleykum",
        "assalom alaykum",
        "assalom aleykum",
        "salom alaykum",
        "salom aleykum",
        "assalomalaykum",
        "salomaleykum",
        "ассалому алайкум",
        "ассалому алейкум",
        "ассалом алайкум",
        "салом алайкум",
    }:
        return "greeting_assalom", "uz"
    if normalized in {
        "rahmat",
        "raxmat",
        "katta rahmat",
        "ok rahmat",
        "tashakkur",
        "рахмат",
        "катта рахмат",
        "ташаккур",
        "thanks",
        "thank you",
    }:
        return "thanks", "uz"
    if normalized in {
        "спасибо",
        "спасибо большое",
        "большое спасибо",
        "спасибо понятно",
        "понятно спасибо",
        "благодарю",
    }:
        return "thanks", "ru"
    if normalized in {
        "nima qila olasan",
        "nimalar qila olasan",
        "nima qilasan",
        "qanday yordam bera olasan",
        "sen kimsan",
        "siz kimsiz",
        "нима қила оласан",
        "сен кимсан",
        "сиз кимсиз",
        "what can you do",
        "who are you",
    }:
        return "about", "uz"
    if normalized in {
        "что ты умеешь",
        "что умеешь",
        "что вы умеете",
        "кто ты",
        "кто вы",
        "чем можешь помочь",
        "чем можете помочь",
    }:
        return "about", "ru"
    if normalized in {
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
        "салом",
        "ассалом",
        "яхшимисиз",
        "хайрли тонг",
        "хайрли кун",
        "хайрли кеч",
    }:
        return "greeting", "uz"
    if normalized in {
        "привет",
        "приветствую",
        "здравствуйте",
        "здравствуй",
        "здрасьте",
        "добрый день",
        "доброе утро",
        "добрый вечер",
        "привет как дела",
        "здравствуйте как дела",
        "салам",
    }:
        return "greeting", "ru"
    return None


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
