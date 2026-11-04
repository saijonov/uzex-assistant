import csv
import io
import re

SOURCE_FILES = {
    "brokers.csv": (
        "brokers",
        [
            ("broker_code", "Код брокера"),
            ("name", "Наименование"),
            ("inn", "ИНН"),
            ("region", "Регион"),
        ],
    ),
    "participants.csv": (
        "participants",
        [
            ("inn", "ИНН"),
            ("name", "Наименование"),
            ("region", "Регион"),
            ("activity", "Вид деятельности"),
            ("role", "Роль"),
            ("vat_payer", "Плательщик НДС"),
        ],
    ),
}


def requested_source_file(question: str) -> str | None:
    value = re.sub(r"['‘’ʻʼ`]", "", question.casefold())
    if re.search(r"\.\.|[/\\]", value):
        return None
    if re.search(r"\b(haqida|nechta|ҳақида|хакида|нечта|сколько|about|how many)\b", value):
        return None
    if not re.search(
        r"\b(jonat\w*|yubor\w*|ber\w*|жўнат\w*|жунат\w*|юбор\w*|бер\w*|пришли|отправь\w*|скача\w*|дай|send|download)\b",
        value,
    ):
        return None
    for name in SOURCE_FILES:
        stem = name.removesuffix(".csv")
        if re.search(r"\b" + stem + r"(?:\s*\.\s*|\s+)csv\b", value):
            return name
    return None


def source_csv(database, filename: str) -> tuple[bytes, int, int]:
    if filename not in SOURCE_FILES:
        raise ValueError("Source file is not available for download")
    table, fields = SOURCE_FILES[filename]
    with database.connect() as connection:
        rows = connection.execute(
            f"SELECT {', '.join(field for field, _ in fields)} FROM {table} ORDER BY source_row"
        ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([heading for _, heading in fields])
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig"), len(rows), len(fields)
