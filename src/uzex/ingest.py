import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

import duckdb

SEPARATE_GOODS = re.compile(r"спот|форвард|фьючерс|мазут")

CONTRACT_FIELDS = {
    "Номер контракта": "contract_id",
    "Наименование продукта": "product",
    "Марка товара": "brand",
    "Размер товара": "size",
    "Сорт товара": "grade",
    "Тип товара": "product_type",
    "Класс товара": "product_class",
    "Код ТН ВЭД": "hs_code",
    "Группа товара": "product_group",
    "Категория товара": "category",
    "Отрасль промышленности": "industry",
    "Единица измерения": "unit",
    "Валюта": "currency",
    "Базис поставки": "delivery_basis",
    "Регион": "region_ru",
    "Адрес склада": "warehouse_address",
    "Тип торгов": "auction_type",
    "Тип контракта": "contract_type",
    "Форма контракта": "contract_form",
    "Упаковка": "packaging",
    "ИНН продавца": "seller_inn",
}
DEAL_FIELDS = {
    "Номер сделки": "deal_id",
    "Время сделки": "deal_time",
    "Тип торгов": "auction_type",
    "Номер контракта": "contract_id",
    "Наименование товара": "product_name",
    "Единица измерения": "unit",
    "Регион": "region",
    "Тип контракта": "contract_type",
    "Форма контракта": "contract_form",
    "Состояние сделки": "status",
    "ИНН продавца": "seller_inn",
    "ИНН покупателя": "buyer_inn",
    "Брокер продавца": "seller_broker_code",
    "Брокер покупателя": "buyer_broker_code",
}


def product_group(product: str, hs_code: str) -> tuple[str, str]:
    mark = SEPARATE_GOODS.search(product.casefold())
    return hs_code, mark.group() if mark else ""


def product_families(counts: list[tuple[str, str, int]]) -> dict[str, str]:
    names: dict[tuple[str, str], str] = {}
    for product, hs_code, _ in sorted(counts, key=lambda item: (-item[2], item[0])):
        names.setdefault(product_group(product, hs_code), product)
    return {product: names[product_group(product, hs_code)] for product, hs_code, _ in counts}


def text_fields(mapping: dict[str, str]) -> list[str]:
    return [f'"{source}" AS {target}' for source, target in mapping.items()]


def number(source: str, target: str, precision: str = "18,3") -> str:
    return (
        f"CAST(replace(replace(replace(\"{source}\", ' ', ''), chr(160), ''), '%', '') "
        f"AS DECIMAL({precision})) AS {target}"
    )


def date_field(source: str, target: str) -> str:
    return f"CAST(strptime(\"{source}\", '%d.%m.%Y') AS DATE) AS {target}"


def import_archive(archive: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_db = destination.with_suffix(".building.duckdb")
    temporary_db.unlink(missing_ok=True)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    try:
        with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(archive) as zipped:
            filenames = ["contracts", "participants", "brokers", "usd_rates"] + [
                f"deals_{year}" for year in range(2022, 2027)
            ]
            for name in filenames:
                member = f"uzex_spot_data/{name}.csv"
                Path(folder, f"{name}.csv").write_bytes(zipped.read(member))
            with duckdb.connect(str(temporary_db)) as db:

                def load(name: str, table: str, fields: list[str], append: bool = False):
                    db.execute(
                        "CREATE OR REPLACE TEMP TABLE raw AS "
                        "SELECT * FROM read_csv(?, all_varchar=true)",
                        [str(Path(folder, f"{name}.csv"))],
                    )
                    fields = [
                        *fields,
                        f"'{name}.csv' AS source_file",
                        "row_number() OVER () + 1 AS source_row",
                    ]
                    prefix = f"INSERT INTO {table}" if append else f"CREATE TABLE {table} AS"
                    db.execute(f"{prefix} SELECT {', '.join(fields)} FROM raw")

                load(
                    "contracts",
                    "contracts",
                    [
                        *text_fields(CONTRACT_FIELDS),
                        number("Лот", "lot_size"),
                        number("Базисная цена", "base_price", "24,2"),
                        number("Сумма залога", "deposit_percent", "8,3"),
                        'CAST("Срок оплаты" AS INTEGER) AS payment_days',
                        'CAST("Срок поставки" AS INTEGER) AS delivery_days',
                        date_field("Дата регистрации", "registered_on"),
                        date_field("Действует до", "valid_until"),
                    ],
                )
                load(
                    "participants",
                    "participants",
                    text_fields(
                        {
                            "ИНН": "inn",
                            "Наименование": "name",
                            "Регион": "region",
                            "Вид деятельности": "activity",
                            "Роль": "role",
                            "Плательщик НДС": "vat_payer",
                        }
                    ),
                )
                load(
                    "brokers",
                    "brokers",
                    text_fields(
                        {
                            "Код брокера": "broker_code",
                            "Наименование": "name",
                            "ИНН": "inn",
                            "Регион": "region",
                        }
                    ),
                )
                load(
                    "usd_rates",
                    "usd_rates",
                    [
                        date_field("Дата", "rate_date"),
                        number("Курс", "usd_uzs", "12,2"),
                    ],
                )
                for year in range(2022, 2027):
                    load(
                        f"deals_{year}",
                        "deals",
                        [
                            *text_fields(DEAL_FIELDS),
                            date_field("Дата сделки", "deal_date"),
                            date_field("Дата оплаты", "paid_on"),
                            date_field("Дата поставки", "delivered_on"),
                            number("Количество", "quantity_lots"),
                            number("Лот", "lot_size"),
                            number("Сумма сделки", "amount", "24,2"),
                            number("Стартовая цена", "starting_price", "24,2"),
                            number("Поставлено", "delivered_lots"),
                        ],
                        append=year != 2022,
                    )
                for table, key in [
                    ("deals", "deal_id"),
                    ("contracts", "contract_id"),
                    ("participants", "inn"),
                    ("brokers", "broker_code"),
                    ("usd_rates", "rate_date"),
                ]:
                    duplicates = db.execute(
                        f"SELECT count(*) - count(DISTINCT {key}) FROM {table}"
                    ).fetchone()[0]
                    if duplicates:
                        raise ValueError(f"Duplicate or null keys in {table}")
                counts = db.execute(
                    "SELECT c.product, c.hs_code, count(d.deal_id) FROM contracts c "
                    "LEFT JOIN deals d USING (contract_id) GROUP BY c.product, c.hs_code"
                ).fetchall()
                db.execute("ALTER TABLE contracts ADD COLUMN product_family VARCHAR")
                db.executemany(
                    "UPDATE contracts SET product_family = ? WHERE product = ?",
                    [(family, product) for product, family in product_families(counts).items()],
                )
                db.execute("""
                    CREATE VIEW registry AS SELECT
                      d.*, c.product, c.product_family, c.brand, c.size, c.grade, c.product_type,
                      c.product_class, c.hs_code, c.category, c.product_group, c.industry,
                      c.region_ru, c.currency, c.base_price, c.deposit_percent,
                      c.delivery_basis, c.packaging, c.warehouse_address,
                      c.payment_days, c.delivery_days, c.registered_on, c.valid_until,
                      s.name AS seller_name, s.region AS seller_region,
                      s.vat_payer AS seller_vat_payer, s.activity AS seller_activity,
                      b.name AS buyer_name, b.region AS buyer_region,
                      b.vat_payer AS buyer_vat_payer, b.activity AS buyer_activity,
                      sb.name AS seller_broker_name, sb.region AS seller_broker_region,
                      bb.name AS buyer_broker_name, bb.region AS buyer_broker_region,
                      fx.usd_uzs,
                      d.quantity_lots * d.lot_size AS volume,
                      d.delivered_lots * d.lot_size AS delivered_volume,
                      CASE WHEN d.unit = 'килограмм' THEN volume
                        WHEN d.unit = 'тонна' THEN volume * 1000 END AS mass_kg,
                      CASE WHEN d.unit = 'килограмм' THEN volume * 0.001
                        WHEN d.unit = 'тонна' THEN volume END AS mass_t,
                      CAST(round(d.amount / volume, 2) AS DECIMAL(24,2)) AS unit_price,
                      CASE WHEN d.unit = 'килограмм' THEN delivered_volume
                        WHEN d.unit = 'тонна' THEN delivered_volume * 1000 END AS delivered_mass_kg,
                      CASE WHEN c.currency = 'Доллар США'
                        THEN d.amount * fx.usd_uzs ELSE d.amount END AS amount_uzs,
                      CASE WHEN c.currency = 'Доллар США' THEN d.amount
                        ELSE CAST(d.amount / fx.usd_uzs AS DECIMAL(24,6)) END AS amount_usd,
                      d.paid_on - d.deal_date AS days_to_payment,
                      d.delivered_on - d.deal_date AS days_to_delivery,
                      d.delivered_on - d.paid_on AS days_payment_to_delivery,
                      d.deal_date + c.payment_days AS payment_due,
                      d.paid_on + c.delivery_days AS delivery_due,
                      d.status = 'Аннулирован(Не оплачен)' AS is_cancelled
                    FROM deals d
                    LEFT JOIN contracts c USING (contract_id)
                    LEFT JOIN participants s ON d.seller_inn = s.inn
                    LEFT JOIN participants b ON d.buyer_inn = b.inn
                    LEFT JOIN brokers sb ON d.seller_broker_code = sb.broker_code
                    LEFT JOIN brokers bb ON d.buyer_broker_code = bb.broker_code
                    LEFT JOIN usd_rates fx ON d.deal_date = fx.rate_date
                """)
                db.execute("""
                    CREATE TABLE broker_deal_links AS
                    SELECT deal_id, seller_broker_code AS broker_code,
                      CASE WHEN seller_broker_code = buyer_broker_code
                        THEN 'Обе стороны' ELSE 'Продавец' END AS broker_side
                    FROM deals
                    UNION ALL
                    SELECT deal_id, buyer_broker_code, 'Покупатель' FROM deals
                    WHERE buyer_broker_code <> seller_broker_code
                """)
                db.execute("""
                    CREATE VIEW broker_deals AS
                    SELECT r.*, l.broker_code, l.broker_side, x.name AS broker_name,
                      x.region AS broker_region
                    FROM broker_deal_links l
                    JOIN registry r USING (deal_id)
                    JOIN brokers x ON l.broker_code = x.broker_code
                """)
                invalid = db.execute("""
                    SELECT count(*) FROM registry WHERE currency IS NULL OR seller_name IS NULL
                    OR buyer_name IS NULL OR seller_broker_name IS NULL
                    OR buyer_broker_name IS NULL OR usd_uzs IS NULL
                    OR quantity_lots <= 0 OR lot_size <= 0 OR amount < 0
                    OR delivered_lots < 0 OR delivered_lots > quantity_lots
                """).fetchone()[0]
                if invalid:
                    raise ValueError(f"Invalid rows or broken references: {invalid}")
                manifest = {
                    "archive_sha256": sha,
                    "counts": {
                        name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                        for name in ["deals", "contracts", "participants", "brokers", "usd_rates"]
                    },
                    "first_date": str(db.execute("SELECT min(deal_date) FROM deals").fetchone()[0]),
                    "snapshot_date": str(
                        db.execute("SELECT max(deal_date) FROM deals").fetchone()[0]
                    ),
                    "fictional": True,
                }
                db.execute("CREATE TABLE metadata (manifest VARCHAR)")
                db.execute("INSERT INTO metadata VALUES (?)", [json.dumps(manifest)])
                db.execute("CHECKPOINT")
        os.replace(temporary_db, destination)
        destination.with_suffix(".manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        return manifest
    except BaseException:
        temporary_db.unlink(missing_ok=True)
        temporary_db.with_suffix(".duckdb.wal").unlink(missing_ok=True)
        raise
