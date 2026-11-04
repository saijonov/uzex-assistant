import datetime as dt
import json
import re
import threading
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

import duckdb
import sqlglot
from rapidfuzz import fuzz
from sqlglot import exp

from uzex.models import Evidence

TABLES = {"registry", "contracts", "participants", "brokers", "usd_rates"}
ROW_LIMITS = {
    "registry": 100,
    "contracts": 7000,
    "participants": 15000,
    "brokers": 1000,
    "usd_rates": 2000,
}
FUNCTIONS = {
    "AND",
    "OR",
    "COUNT",
    "SUM",
    "MIN",
    "MAX",
    "LOWER",
    "UPPER",
    "COALESCE",
    "NULLIF",
    "EXTRACT",
    "DATE_TRUNC",
    "STRFTIME",
    "CAST",
    "TRY_CAST",
    "ABS",
    "ROUND",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "LENGTH",
}
TRANSLITERATION = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "j",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "x",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sh",
        "ъ": "",
        "ы": "i",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ў": "o",
        "қ": "q",
        "ғ": "g",
        "ҳ": "h",
    }
)
PRODUCT_ALIASES = {
    "shakar": "Сахар",
    "oq shakar": "Сахар белый",
    "bugdoy": "Пшеница",
    "un": "Мука",
    "paxta": "Хлопок",
    "paxta yogi": "Масло хлопковое",
    "sement": "Цемент",
    "benzin": "Бензин",
    "dizel": "Топливо дизельное",
    "komir": "Уголь",
    "mis": "Медь",
    "oltin": "Золото",
    "kumush": "Серебро",
    "karbamid": "Карбамид",
    "selitra": "Селитра",
    "polietilen": "Полиэтилен",
    "guruch": "Рис",
    "arpa": "Ячмень",
    "makkajoxori": "Кукуруза",
    "kungaboqar yogi": "Масло подсолнечное",
    "yog": "Масло",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower().translate(TRANSLITERATION)
    value = re.sub(r"['‘’ʻʼ`\"«»]", "", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def serial(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    return value


def validate_query(sql: str) -> tuple[exp.Select, str]:
    if len(sql) > 8000:
        raise ValueError("Query too long")
    statements = sqlglot.parse(sql, read="duckdb")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Exactly one SELECT is allowed")
    tree = statements[0]
    allowed_clauses = {"expressions", "from_", "where", "group", "order", "limit", "distinct"}
    if any(value and key not in allowed_clauses for key, value in tree.args.items()):
        raise ValueError("Unsupported SELECT clause; use WHERE filters and ordinary grouping")
    if tree.args.get("with_") or tree.args.get("joins") or tree.args.get("into"):
        raise ValueError("Use one approved view without joins, CTEs or INTO")
    if tree.args.get("having"):
        raise ValueError("Put scope filters in WHERE, not HAVING, so evidence matches the answer")
    if len(list(tree.find_all(exp.Select))) != 1 or tree.find(exp.Subquery):
        raise ValueError("Nested queries are not allowed")
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name not in TABLES:
        raise ValueError("Use exactly one approved table")
    table = tables[0]
    if not isinstance(table.this, exp.Identifier) or table.db or table.catalog:
        raise ValueError("External and qualified sources are forbidden")
    if any(value and key not in {"this", "alias"} for key, value in table.args.items()):
        raise ValueError("Table transformations and sampling are forbidden")
    if tree.args.get("offset") or tree.find(exp.Window):
        raise ValueError("Offsets and window functions are unsupported")
    for node in tree.walk():
        if isinstance(node, (exp.Div, exp.IntDiv, exp.Mod, exp.Pow, exp.Add, exp.Sub, exp.Mul)):
            raise ValueError("Use calculate_ratio for division; other arithmetic is unsupported")
        if isinstance(node, exp.Func):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name()
            if name not in FUNCTIONS:
                raise ValueError(f"Function not allowed: {name}")
    for item in tree.expressions:
        if isinstance(item, exp.Alias):
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,50}", item.alias):
                raise ValueError("Aliases must be short English field names")
        if isinstance(item, exp.Literal):
            raise ValueError("Select database fields or aggregates, not invented literals")
        if isinstance(item, exp.Alias) and isinstance(item.this, exp.Literal):
            raise ValueError("Literal output is forbidden")
        projection = item.this if isinstance(item, exp.Alias) else item
        if not isinstance(projection, (exp.Column, exp.Star, exp.Func, exp.Filter)):
            raise ValueError("Output must be a source field or approved aggregation")
        for literal in projection.find_all(exp.Literal):
            parent = literal.parent
            inside_filter = False
            ancestor = literal.parent
            while ancestor is not None:
                inside_filter = inside_filter or isinstance(ancestor, exp.Where)
                ancestor = ancestor.parent
            if not inside_filter and not isinstance(
                parent, (exp.DateTrunc, exp.TimestampTrunc, exp.TimeToStr)
            ):
                raise ValueError("Invented output constants are forbidden")
        if projection.find(exp.Case) or projection.find(exp.If):
            raise ValueError("Conditional output values are forbidden")
    limit = tree.args.get("limit")
    if limit:
        try:
            limit_value = int(limit.expression.this)
        except (ValueError, AttributeError, TypeError) as error:
            raise ValueError("Limit must be an integer") from error
        if not 1 <= limit_value <= ROW_LIMITS[table.name]:
            raise ValueError(f"Limit must be between 1 and {ROW_LIMITS[table.name]}")
    return tree, table.name


class Database:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            self.manifest = json.loads(db.execute("SELECT manifest FROM metadata").fetchone()[0])
            first_rate, last_rate = db.execute(
                "SELECT min(rate_date), max(rate_date) FROM usd_rates"
            ).fetchone()
            self.manifest["usd_rates_coverage"] = [str(first_rate), str(last_rate)]
            self.schema = {
                table: [(r[0], r[1]) for r in db.execute(f"DESCRIBE {table}").fetchall()]
                for table in sorted(TABLES)
            }
            self.catalog = self._catalog(db)

    def connect(self):
        return duckdb.connect(
            str(self.path),
            read_only=True,
            config={
                "enable_external_access": "false",
                "autoinstall_known_extensions": "false",
                "autoload_known_extensions": "false",
                "threads": "2",
                "memory_limit": "512MB",
            },
        )

    def _catalog(self, db) -> dict[str, list[dict]]:
        def fetch(sql):
            result = db.execute(sql)
            columns = [c[0] for c in result.description]
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]

        return {
            "product": fetch("SELECT DISTINCT product_name AS name FROM registry"),
            "company": fetch("SELECT inn, name, role FROM participants"),
            "broker": fetch("SELECT broker_code, inn, name FROM brokers"),
            "region": fetch("SELECT DISTINCT region AS name, region_ru FROM registry"),
            "status": fetch("SELECT DISTINCT status AS name FROM registry"),
            "category": fetch("SELECT DISTINCT category AS name FROM contracts"),
        }

    def lookup(self, kind: str, text: str) -> list[dict]:
        needle = normalize(text)
        alias = PRODUCT_ALIASES.get(needle) if kind == "product" else None
        needles = [needle] + ([normalize(alias)] if alias else [])
        candidates = []
        for entry in self.catalog[kind]:
            values = [normalize(str(value)) for value in entry.values()]
            exact = any(n in values for n in needles)
            partial = any(n and n in v for n in needles for v in values)
            score = max(fuzz.WRatio(n, v) for n in needles for v in values)
            if exact or partial or score >= 65:
                candidates.append(
                    {
                        **entry,
                        "match": "exact" if exact else "partial" if partial else "fuzzy",
                        "score": round(score, 1),
                    }
                )
        candidates.sort(
            key=lambda r: (r["match"] == "exact", r["match"] == "partial", r["score"]), reverse=True
        )
        return candidates[:30]

    def sample(self, sql: str, count: int, query_id: str, timeout: float = 8) -> Evidence:
        tree, table = validate_query(sql)
        if not 1 <= count <= 100:
            raise ValueError("Sample size must be between 1 and 100")
        if tree.find(exp.AggFunc) or any(
            tree.args.get(clause) for clause in ("group", "distinct", "order", "limit")
        ):
            raise ValueError(
                "Sampling needs source fields and optional WHERE, without aggregates, ordering or limits"
            )
        key = {
            "registry": "deal_id",
            "contracts": "contract_id",
            "participants": "inn",
            "brokers": "broker_code",
            "usd_rates": "rate_date",
        }[table]
        draw = tree.copy()
        draw.set("expressions", [exp.column(key)])
        draw = draw.order_by(exp.Rand()).limit(count)
        with self.connect() as db:
            timer = threading.Timer(timeout, db.interrupt)
            timer.start()
            try:
                keys = [row[0] for row in db.execute(draw.sql(dialect="duckdb")).fetchall()]
            finally:
                timer.cancel()
        if keys:
            selected = exp.In(
                this=exp.column(key), expressions=[exp.Literal.string(str(value)) for value in keys]
            )
        else:
            selected = exp.false()
        frozen = tree.where(selected).order_by(key).limit(count)
        result = self.query(frozen.sql(dialect="duckdb"), query_id, timeout)
        return result.model_copy(update={"selection": "random"})

    def query(self, sql: str, query_id: str, timeout: float = 8) -> Evidence:
        tree, table = validate_query(sql)
        row_limit = ROW_LIMITS[table]
        if not tree.args.get("limit"):
            tree = tree.limit(row_limit + 1)
        with self.connect() as db:
            timer = threading.Timer(timeout, db.interrupt)
            timer.start()
            try:
                result = db.execute(tree.sql(dialect="duckdb"))
                columns = [c[0] for c in result.description]
                if len(set(columns)) != len(columns):
                    raise ValueError("Output columns must have unique aliases")
                rows = [
                    dict(zip(columns, map(serial, row), strict=True))
                    for row in result.fetchmany(row_limit + 1)
                ]
                expressions = {}
                for index, item in enumerate(tree.expressions):
                    if isinstance(item, exp.Star):
                        expressions.update({column: column for column in columns})
                        break
                    expression = item.this if isinstance(item, exp.Alias) else item
                    expressions[columns[index]] = expression.sql(dialect="duckdb")
                scope = tree.copy()
                for key in ("group", "having", "order", "limit", "distinct"):
                    scope.set(key, None)
                if table == "registry":
                    scope.set(
                        "expressions",
                        sqlglot.parse_one(
                            "SELECT count(*) AS n, min(deal_date), max(deal_date), "
                            "list(DISTINCT currency), list(DISTINCT unit)"
                        ).expressions,
                    )
                    count, start, end, currencies, units = db.execute(
                        scope.sql(dialect="duckdb")
                    ).fetchone()
                    grouped = {
                        column.name
                        for group in (
                            tree.args["group"].expressions if tree.args.get("group") else []
                        )
                        for column in group.find_all(exp.Column)
                    }
                    aggregate_columns = {
                        col.name
                        for aggregate in tree.find_all(exp.AggFunc)
                        for col in aggregate.find_all(exp.Column)
                    }
                    if (
                        len(currencies or []) > 1
                        and aggregate_columns & {"amount", "starting_price", "base_price"}
                        and "currency" not in grouped
                    ):
                        raise ValueError("Mixed currencies: group by currency or use amount_uzs")
                    if (
                        len(units or []) > 1
                        and aggregate_columns
                        & {"volume", "delivered_volume", "lot_size", "starting_price", "base_price"}
                        and "unit" not in grouped
                    ):
                        raise ValueError(
                            "Mixed units: group by unit or use mass_kg for kg/tonne only"
                        )
                    if aggregate_columns & {"mass_kg", "delivered_mass_kg"} and set(units or []) - {
                        "килограмм",
                        "тонна",
                    }:
                        raise ValueError(
                            "Mass aggregation would omit non-mass rows; specify mass units"
                        )
                    scope.set(
                        "expressions",
                        sqlglot.parse_one(
                            "SELECT deal_id, contract_id, source_file, source_row"
                        ).expressions,
                    )
                else:
                    scope.set("expressions", sqlglot.parse_one("SELECT count(*)").expressions)
                    count = db.execute(scope.sql(dialect="duckdb")).fetchone()[0]
                    start = end = None
                    currencies = units = []
                    scope.set("expressions", [exp.Star()])
                sample_result = db.execute(scope.limit(3).sql(dialect="duckdb"))
                sample_columns = [c[0] for c in sample_result.description]
                samples = [
                    dict(zip(sample_columns, map(serial, row), strict=True))
                    for row in sample_result.fetchall()
                ]
                selected_count = None
                if (
                    table == "registry"
                    and not tree.find(exp.AggFunc)
                    and not tree.args.get("group")
                    and not tree.args.get("distinct")
                ):
                    selected = tree.copy()
                    selected.set(
                        "expressions",
                        sqlglot.parse_one(
                            "SELECT deal_id, contract_id, deal_date, currency, unit, source_file, source_row"
                        ).expressions,
                    )
                    selection = db.execute(selected.sql(dialect="duckdb")).fetchmany(100)
                    selected_count = len(selection)
                    start = min((row[2] for row in selection), default=None)
                    end = max((row[2] for row in selection), default=None)
                    currencies = sorted({row[3] for row in selection})
                    units = sorted({row[4] for row in selection})
                    samples = [
                        dict(
                            zip(
                                [
                                    "deal_id",
                                    "contract_id",
                                    "deal_date",
                                    "currency",
                                    "unit",
                                    "source_file",
                                    "source_row",
                                ],
                                map(serial, row),
                                strict=True,
                            )
                        )
                        for row in selection[:3]
                    ]
                return Evidence(
                    query_id=query_id,
                    sql=sql,
                    table=table,
                    rows=rows[:row_limit],
                    matched_count=count,
                    samples=samples,
                    period_start=serial(start),
                    period_end=serial(end),
                    currencies=sorted(currencies or []),
                    units=sorted(units or []),
                    filters=tree.args["where"].sql(dialect="duckdb")
                    if tree.args.get("where")
                    else None,
                    truncated=len(rows) > row_limit,
                    row_limit=row_limit,
                    expressions=expressions,
                    selected_record_count=selected_count,
                )
            finally:
                timer.cancel()


def calculate_ratio(
    evidence: Evidence, numerator: str, denominator: str, scale: int, operation: str = "ratio"
) -> Evidence:
    if not evidence.rows or not 0 <= scale <= 6:
        raise ValueError("A nonempty query and scale between 0 and 6 are required")
    rows = []
    for row in evidence.rows:
        if numerator not in row or denominator not in row:
            raise ValueError("Calculation fields must exist in the cited result")
        if row[numerator] is None or row[denominator] is None:
            value = None
        else:
            with localcontext() as context:
                context.prec = 50
                n, d = Decimal(str(row[numerator])), Decimal(str(row[denominator]))
                if not n.is_finite() or not d.is_finite() or d == 0:
                    value = None
                else:
                    ratio = (n - d) / d if operation == "change_percent" else n / d
                    if operation in {"percentage", "change_percent"}:
                        ratio *= 100
                    value = str(ratio.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP))
        rows.append({**row, "ratio": value})
    return evidence.model_copy(
        update={
            "rows": rows,
            "calculation": f"{operation}({numerator}, {denominator}); ROUND_HALF_UP, {scale} decimals",
        }
    )
