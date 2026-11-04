import re

from uzex.localization import localize

TERMS = {
    "шрот хлопковых семян": "Paxta chigiti shroti",
    "шрот хлопковый": "Paxta shroti",
    "рафинированное дезодорированное": "rafinatsiyalangan va hidsizlantirilgan",
    "обогащенная витаминно-минеральной смесью": "vitamin-mineral aralashma bilan boyitilgan",
    "обрезные хвойных пород": "qirralari kesilgan ignabargli yog‘och",
    "лист стальной горячекатаный": "Issiq prokatlangan po‘lat list",
    "газ сжиженный пропан-бутан": "Suyultirilgan propan-butan gazi",
    "сжиженный углеводородный газ": "Suyultirilgan uglevodorod gazi",
    "хлопок-сырец": "Chigitli paxta",
    "хлопок сырец": "Chigitli paxta",
    "масло хлопковое": "Paxta yog‘i",
    "хлопковое масло": "Paxta yog‘i",
    "масло подсолнечное": "Kungaboqar yog‘i",
    "подсолнечное масло": "Kungaboqar yog‘i",
    "мука пшеничная": "Bug‘doy uni",
    "пшеница продовольственная": "Oziq-ovqat bug‘doyi",
    "профиль алюминиевый": "Alyuminiy profil",
    "алюминиевый профиль": "Alyuminiy profil",
    "арматура стальная": "Po‘lat armatura",
    "бензин автомобильный": "Avtomobil benzini",
    "битум нефтяной": "Neft bitumi",
    "вода питьевая": "Ichimlik suvi",
    "питьевая вода": "Ichimlik suvi",
    "гипс строительный": "Qurilish gipsi",
    "дизельное топливо": "Dizel yoqilg‘isi",
    "топливо дизельное": "Dizel yoqilg‘isi",
    "известь негашеная": "So‘ndirilmagan ohak",
    "известь строительная": "Qurilish ohagi",
    "катод медный": "Mis katodi",
    "медный катод": "Mis katodi",
    "кабель силовой": "Kuch kabeli",
    "кирпич керамический": "Keramik g‘isht",
    "кислота серная": "Sulfat kislotasi",
    "серная кислота": "Sulfat kislotasi",
    "мазут топочный": "Pech mazuti",
    "пиломатериал обрезной": "Qirrali arralangan yog‘och",
    "проволока арматурная": "Armatura simi",
    "пряжа хлопчатобумажная": "Paxta ipi",
    "пряжа хлопковая": "Paxta ipi",
    "рис шлифованный": "Silliqlangan guruch",
    "сахар белый": "Oq shakar",
    "сахар-песок": "Donador shakar",
    "селитра аммиачная": "Ammiakli selitra",
    "аммиачная селитра": "Ammiakli selitra",
    "сжиженный газ": "Suyultirilgan gaz",
    "сода каустическая": "Kaustik soda",
    "соль поваренная пищевая": "Osh tuzi",
    "соль пищевая": "Osh tuzi",
    "стекло листовое": "List oyna",
    "стекло флоат": "Float oyna",
    "трубы полиэтиленовые": "Polietilen quvurlar",
    "труба пэ": "Polietilen quvur",
    "цемент портландский": "Portlandsement",
    "эмаль алкидная": "Alkid emali",
    "поливинилхлорид": "Polivinilxlorid",
    "полипропилен": "Polipropilen",
    "полиэтилен гранулированный": "Donador polietilen",
    "полиэтилен": "Polietilen",
    "портландцемент": "Portlandsement",
    "пиломатериалы": "Arralangan yog‘och materiallari",
    "мочевина": "Mochevina",
    "карбамид": "Karbamid",
    "арматура": "Armatura",
    "азот": "Azot",
    "аргон газообразный": "Gazsimon argon",
    "бензин": "Benzin",
    "битум": "Bitum",
    "гипс": "Gips",
    "кирпич": "G‘isht",
    "комбикорм": "Omuxta yem",
    "кормосмесь": "Yem aralashmasi",
    "мазут": "Mazut",
    "мука": "Un",
    "подшипник": "Podshipnik",
    "пшеница": "Bug‘doy",
    "рис": "Guruch",
    "эмаль": "Emal",
    "тостированный": "tostlangan",
    "высший": "oliy",
    "хлебопекарная": "non yopish uchun",
    "рафинированное": "rafinatsiyalangan",
    "йодированная": "yodlangan",
    "суспензионный": "suspenzion",
    "твердая": "qattiq",
    "техническая": "texnik",
    "дорожный": "yo‘l qurilishi uchun",
    "спот": "spot",
    "форвард": "forvard",
    "фьючерс": "fyuchers",
}
PATTERNS = [
    (re.compile(r"(?<!\w)" + re.escape(source) + r"(?!\w)", re.IGNORECASE), target)
    for source, target in sorted(TERMS.items(), key=lambda item: len(item[0]), reverse=True)
]
DESCRIPTIVE_FIELDS = {
    "product",
    "product_name",
    "grade",
    "product_type",
    "product_class",
    "size",
    "brand",
}


def translate_description(value: str) -> str:
    value = re.sub(
        r"\b(?:высший\s+сорт|высшего\s+сорта|в/с)\b", "oliy nav", value, flags=re.IGNORECASE
    )
    for source, target in {
        "первый": "1",
        "второй": "2",
        "третий": "3",
        "IV": "4",
        "III": "3",
        "II": "2",
        "I": "1",
    }.items():
        value = re.sub(
            r"\b" + source + r"[\s-]+сорт(?:а)?\b", target + "-nav", value, flags=re.IGNORECASE
        )
        value = re.sub(
            r"\b" + source + r"[\s-]+класс\b", target + "-sinf", value, flags=re.IGNORECASE
        )
    value = re.sub(r"\b([1-4])[\s-]+сорт(?:а)?\b", r"\1-nav", value, flags=re.IGNORECASE)
    value = re.sub(r"\b([1-4])[\s-]+класс\b", r"\1-sinf", value, flags=re.IGNORECASE)
    for pattern, target in PATTERNS:
        value = pattern.sub(lambda _, replacement=target: replacement, value)
    for source, target in {
        "Марка": "marka",
        "Размер": "o‘lcham",
        "Сорт": "nav",
        "Тип": "tur",
        "Класс": "sinf",
    }.items():
        value = re.sub(r"\b" + source + r"\s+", f", {target}: ", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)\s*мм\b", " mm", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)\s*л\b", " l", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)[хХ](?=\d)", "×", value)
    return re.sub(r"\s+,", ",", value)


def display_value(value: str, language: str, field: str | None = None) -> str:
    if field in {
        "seller_name",
        "buyer_name",
        "name",
        "seller_broker_name",
        "buyer_broker_name",
        "warehouse_address",
    }:
        return value
    if language == "uz" and field in DESCRIPTIVE_FIELDS:
        if field == "brand":
            return "oliy" if value.casefold() == "высший" else value
        return translate_description(value)
    return localize(value, language)
