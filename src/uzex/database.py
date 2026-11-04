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

TABLES = {"registry", "broker_deals", "contracts", "participants", "brokers", "usd_rates"}
DEAL_TABLES = {"registry", "broker_deals"}
CURRENCY_COLUMNS = {"amount", "starting_price", "base_price", "unit_price"}
UNIT_COLUMNS = {
    "volume",
    "delivered_volume",
    "lot_size",
    "starting_price",
    "base_price",
    "unit_price",
}
ROW_LIMITS = {
    "registry": 100,
    "broker_deals": 100,
    "contracts": 7000,
    "participants": 15000,
    "brokers": 1000,
    "usd_rates": 2000,
}
GROUPED_ROW_LIMIT = 20000
LARGEST_ASKED_LIMIT = 500000
BROKER_SCOPE_COLUMNS = {"broker_code", "broker_name", "broker_side", "broker_region"}
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
    "MEDIAN",
    "TIMESTAMP_TRUNC",
    "TIME_TO_STR",
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
PROMPT_VALUE_COLUMNS = {
    "registry": (
        "status",
        "currency",
        "unit",
        "contract_type",
        "contract_form",
        "auction_type",
        "region",
        "category",
        "product_group",
        "industry",
        "delivery_basis",
        "packaging",
    ),
    "participants": ("role", "activity", "vat_payer"),
}
ENFORCED_VALUE_COLUMNS = {
    "registry": (
        "region_ru",
        "seller_region",
        "buyer_region",
        "seller_vat_payer",
        "buyer_vat_payer",
        "product",
        "product_family",
        "product_name",
        "seller_name",
        "buyer_name",
        "seller_activity",
        "buyer_activity",
        "seller_broker_name",
        "buyer_broker_name",
        "seller_broker_region",
        "buyer_broker_region",
    ),
    "broker_deals": ("broker_side", "broker_name", "broker_region"),
    "participants": ("region", "name"),
    "brokers": ("region", "name"),
}
NAME_LOOKUP_KINDS = {"company", "broker"}
NAME_MATCH_THRESHOLD = 80
PRODUCT_MATCH_THRESHOLD = 78
GENERIC_NAME_WORDS = {
    "mchj",
    "aj",
    "ok",
    "xk",
    "qk",
    "oaj",
    "llc",
    "masuliyati",
    "cheklangan",
    "jamiyati",
    "broker",
}
PRODUCT_DESCRIPTION_WORDS = {
    "marka",
    "razmer",
    "sort",
    "sorta",
    "tip",
    "klass",
    "klassa",
    "tovar",
    "spot",
    "forvard",
    "fyuchers",
    "pervyy",
    "pervii",
    "perviy",
    "vtoroy",
    "tretiy",
    "visshiy",
    "visshego",
    "ne",
    "mm",
    "ii",
    "iii",
    "iv",
}
PRODUCT_ALIASES = {
    "shakar": "Сахар",
    "oq shakar": "Сахар белый",
    "bugdoy": "Пшеница",
    "un": "Мука",
    "paxta": "Хлопок",
    "xlopk": "Хлопок",
    "paxta yogi": "Масло хлопковое",
    "sement": "Цемент",
    "benzin": "Бензин",
    "dizel": "Топливо дизельное",
    "mis": "Медь",
    "karbamid": "Карбамид",
    "selitra": "Селитра",
    "polietilen": "Полиэтилен",
    "guruch": "Рис",
    "kungaboqar yogi": "Масло подсолнечное",
    "yog": "Масло",
    "gisht": "Кирпич",
    "oyna": "Стекло",
    "shisha": "Стекло",
    "tuz": "Соль",
    "quvur": "Труб",
    "ohak": "Известь",
    "kunjara": "Шрот",
    "kungaboqar": "Подсолнечное",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower().translate(TRANSLITERATION)
    value = re.sub(r"['‘’ʻʼ`\"«»]", "", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


REGION_STEMS = {
    "Andijon viloyati": ("andijon", "andijan"),
    "Buxoro viloyati": ("buxoro", "buxar", "buhar", "bukhar"),
    "Farg‘ona viloyati": ("fargona", "fergan"),
    "Jizzax viloyati": ("jizzax", "jizax", "jizak", "djizak", "dzhizak"),
    "Namangan viloyati": ("namangan",),
    "Navoiy viloyati": ("navoiy", "navoi", "navoy"),
    "Qashqadaryo viloyati": ("qashqadar", "kashkadar"),
    "Qoraqalpog‘iston Respublikasi": ("qoraqalpog", "karakalpak", "qaraqalpaq"),
    "Samarqand viloyati": ("samarqand", "samarkand"),
    "Sirdaryo viloyati": ("sirdar",),
    "Surxondaryo viloyati": ("surxon", "surxan", "surhan"),
    "Toshkent shahri": ("toshkent", "tashkent"),
    "Toshkent viloyati": ("toshkent", "tashkent"),
    "Xorazm viloyati": ("xorazm", "xorezm", "horazm", "horezm"),
}
TOSHKENT_REGIONS = ("Toshkent shahri", "Toshkent viloyati")
CITY_WORD = re.compile(
    r"\bsha[hx]ar\w*|\bsha[hx]ri?\b|\bshahri(?:da|dagi|ga|ni|ning|dan)\b|\bgorod\w*|\bcity\b"
)
CITY_PREFIX = re.compile(r"\bg (?:toshkent|tashkent)")
OBLAST_WORD = re.compile(r"\bviloyat\w*|\boblast\w*")


def product_aliases(needle: str) -> list[str]:
    tokens = needle.split()
    return [
        alias
        for word, alias in PRODUCT_ALIASES.items()
        if word == needle or (len(word) >= 4 and any(token.startswith(word) for token in tokens))
    ]


def product_score(needle: str, value: str) -> float:
    words = value.split()
    tokens = [
        token
        for token in needle.split()
        if token not in PRODUCT_DESCRIPTION_WORDS and not token.isdigit()
    ]
    if not words or not tokens:
        return 0
    return max(
        max(
            fuzz.ratio(token, word),
            fuzz.partial_ratio(token, word) if 6 <= len(token) <= len(word) else 0,
        )
        for token in tokens
        for word in words
    )


def distinctive_name(value: str) -> str:
    return " ".join(word for word in normalize(value).split() if word not in GENERIC_NAME_WORDS)


def named_regions(text: str) -> list[str]:
    value = normalize(text)
    tokens = value.split()
    names = [
        name
        for name, stems in REGION_STEMS.items()
        if any(token.startswith(stems) for token in tokens)
    ]
    if all(name in names for name in TOSHKENT_REGIONS):
        city = bool(CITY_WORD.search(value) or CITY_PREFIX.search(value))
        oblast = bool(OBLAST_WORD.search(value))
        if city != oblast:
            names.remove(TOSHKENT_REGIONS[1] if city else TOSHKENT_REGIONS[0])
    return names


def region_choice(text: str) -> str | None:
    value = normalize(text)
    city = bool(CITY_WORD.search(value) or CITY_PREFIX.search(value))
    oblast = bool(OBLAST_WORD.search(value))
    if city == oblast:
        return None
    return TOSHKENT_REGIONS[0] if city else TOSHKENT_REGIONS[1]


def serial(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    return value


def derived_source(tree: exp.Select) -> exp.Expression | None:
    source = tree.args.get("from_")
    return source.this.this if source and isinstance(source.this, exp.Subquery) else None


def validate_query(sql: str) -> tuple[exp.Select, str]:
    if len(sql) > 8000:
        raise ValueError("Query too long")
    statements = sqlglot.parse(sql, read="duckdb")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Exactly one SELECT is allowed")
    tree = statements[0]
    inner = derived_source(tree)
    if inner is None:
        return tree, validate_select(tree)
    projection = tree.expressions[0] if len(tree.expressions) == 1 else None
    projection = projection.this if isinstance(projection, exp.Alias) else projection
    if (
        any(value and key not in {"expressions", "from_"} for key, value in tree.args.items())
        or not isinstance(projection, exp.Count)
        or not isinstance(projection.this, exp.Star)
        or not isinstance(inner, exp.Select)
    ):
        raise ValueError("The only allowed FROM subquery is SELECT COUNT(*) FROM (grouped SELECT)")
    return tree, validate_select(inner)


def validate_membership_subquery(select: exp.Select, root: exp.Select) -> None:
    subquery = select.parent
    if not isinstance(subquery, exp.Subquery) or not isinstance(subquery.parent, exp.In):
        raise ValueError("Nested queries are only allowed as column IN (SELECT column FROM table)")
    if subquery.find_ancestor(exp.Where) is not root.args.get("where"):
        raise ValueError("A membership subquery belongs in the main WHERE")
    if any(
        value and key not in {"expressions", "from_", "where"} for key, value in select.args.items()
    ):
        raise ValueError("A membership subquery may only select a column with optional WHERE")
    source = select.args.get("from_")
    if (
        len(select.expressions) != 1
        or not isinstance(select.expressions[0], exp.Column)
        or source is None
        or not isinstance(source.this, exp.Table)
    ):
        raise ValueError("A membership subquery selects one column from one approved table")


def row_limit_for(tree: exp.Select, table: str) -> int:
    if table in DEAL_TABLES and (tree.args.get("group") or tree.args.get("distinct")):
        return GROUPED_ROW_LIMIT
    return ROW_LIMITS[table]


def validate_broker_scope(tree: exp.Select) -> None:
    aggregates = list(tree.find_all(exp.AggFunc))
    if not aggregates:
        return
    columns = {
        column.name
        for part in (tree.args.get("where"), tree.args.get("group"))
        if part
        for column in part.find_all(exp.Column)
    }
    if tree.args.get("group"):
        columns |= {
            column.name
            for item in tree.expressions
            if not item.find(exp.AggFunc)
            for column in item.find_all(exp.Column)
        }
    if columns & BROKER_SCOPE_COLUMNS:
        return
    if all(
        isinstance(item, exp.Count) and isinstance(item.this, exp.Distinct) for item in aggregates
    ):
        return
    raise ValueError(
        "broker_deals has one row per deal and broker, so this total counts deals twice. "
        "Use registry for totals, and broker_deals only to group or filter by broker."
    )


def validate_select(tree: exp.Select) -> str:
    allowed_clauses = {
        "expressions",
        "from_",
        "where",
        "group",
        "having",
        "order",
        "limit",
        "offset",
        "distinct",
    }
    if any(value and key not in allowed_clauses for key, value in tree.args.items()):
        raise ValueError("Unsupported SELECT clause; use WHERE filters and ordinary grouping")
    if tree.args.get("with_") or tree.args.get("joins") or tree.args.get("into"):
        raise ValueError("Use one approved view without joins, CTEs or INTO")
    having = tree.args.get("having")
    if having and not having.find(exp.AggFunc):
        raise ValueError("Put scope filters in WHERE; HAVING may only test an aggregate")
    source = tree.args.get("from_")
    if source is None or not isinstance(source.this, exp.Table):
        raise ValueError("Use exactly one approved table")
    for select in tree.find_all(exp.Select):
        if select is not tree:
            validate_membership_subquery(select, tree)
    for table in tree.find_all(exp.Table):
        if table.name not in TABLES:
            raise ValueError("Use only approved tables")
        if not isinstance(table.this, exp.Identifier) or table.db or table.catalog:
            raise ValueError("External and qualified sources are forbidden")
        if any(value and key not in {"this", "alias"} for key, value in table.args.items()):
            raise ValueError("Table transformations and sampling are forbidden")
    table = source.this
    if tree.find(exp.Window):
        raise ValueError("Window functions are unsupported")
    if tree.args.get("offset") and not (tree.args.get("limit") and tree.args.get("order")):
        raise ValueError("OFFSET needs both ORDER BY and LIMIT")
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
        if not 1 <= limit_value <= LARGEST_ASKED_LIMIT:
            raise ValueError(f"Limit must be between 1 and {LARGEST_ASKED_LIMIT}")
    if table.name == "broker_deals":
        validate_broker_scope(tree)
    return table.name


class Database:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            self.manifest = json.loads(db.execute("SELECT manifest FROM metadata").fetchone()[0])
            first_rate, last_rate = db.execute(
                "SELECT min(rate_date), max(rate_date) FROM usd_rates"
            ).fetchone()
            self.manifest["usd_rates_coverage"] = [str(first_rate), str(last_rate)]
            existing = {
                row[0]
                for row in db.execute("SELECT table_name FROM information_schema.tables").fetchall()
            }
            self.schema = {
                table: [(r[0], r[1]) for r in db.execute(f"DESCRIBE {table}").fetchall()]
                for table in sorted(TABLES & existing)
            }
            self.catalog = self._catalog(db)
            self.product_words = self._product_words()
            self.values = self._column_values(db, PROMPT_VALUE_COLUMNS)
            self.known_values = {column: set(values) for column, values in self.values.items()}
            for column, values in self._column_values(db, ENFORCED_VALUE_COLUMNS).items():
                self.known_values.setdefault(column, set()).update(values)

    def _product_words(self) -> set[str]:
        sources = [entry["name"] for entry in self.catalog["product"]]
        sources += list(PRODUCT_ALIASES) + list(PRODUCT_ALIASES.values())
        return {
            word
            for source in sources
            for word in normalize(source).split()
            if word.isalpha() and len(word) >= 2 and word not in PRODUCT_DESCRIPTION_WORDS
        }

    def names_product(self, text: str) -> bool:
        for token in normalize(text).split():
            if token in self.product_words:
                return True
            if len(token) >= 5 and any(
                len(word) >= 4 and (token.startswith(word) or word.startswith(token))
                for word in self.product_words
            ):
                return True
        return False

    def _column_values(self, db, columns: dict[str, tuple[str, ...]]) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        for table, names in columns.items():
            present = {column[0] for column in self.schema.get(table, [])}
            for name in names:
                if name not in present:
                    continue
                rows = db.execute(
                    f"SELECT DISTINCT {name} FROM {table} WHERE {name} IS NOT NULL ORDER BY 1"
                ).fetchall()
                merged = set(values.get(name, [])) | {str(row[0]) for row in rows}
                values[name] = sorted(merged)
        return values

    def check_filter_values(self, tree: exp.Select) -> None:
        for node in tree.find_all(exp.EQ, exp.NEQ, exp.In, exp.Like, exp.ILike):
            target = node.this
            folded = isinstance(node, exp.ILike)
            while isinstance(target, (exp.Lower, exp.Upper, exp.Paren)):
                folded = folded or not isinstance(target, exp.Paren)
                target = target.this
            if not isinstance(target, exp.Column) or target.name not in self.known_values:
                continue
            known = self.known_values[target.name]
            operands = node.expressions if isinstance(node, exp.In) else [node.expression]
            for operand in operands:
                if not isinstance(operand, exp.Literal) or not operand.is_string:
                    continue
                if isinstance(node, (exp.Like, exp.ILike)):
                    pattern = re.escape(operand.name).replace("%", ".*").replace("_", ".")
                    flags = re.IGNORECASE | re.DOTALL if folded else re.DOTALL
                    matched = any(re.fullmatch(pattern, value, flags) for value in known)
                elif folded:
                    matched = operand.name.casefold() in {value.casefold() for value in known}
                else:
                    matched = operand.name in known
                if not matched:
                    hint = (
                        f"Real values: {sorted(known)}"
                        if len(known) <= 30
                        else "Use lookup_entities to find the real source strings"
                    )
                    raise ValueError(
                        f"No record has {target.name} matching {operand.name!r}. {hint}. "
                        "Correct the filter; this rejection is not evidence of absence."
                    )

    def record_kinds(self, number: str) -> list[str]:
        with self.connect() as db:
            kinds = []
            if db.execute("SELECT 1 FROM deals WHERE deal_id = ? LIMIT 1", [number]).fetchone():
                kinds.append("deal")
            if db.execute(
                "SELECT 1 FROM contracts WHERE contract_id = ? LIMIT 1", [number]
            ).fetchone():
                kinds.append("contract")
        return kinds

    def identifier_suggestions(self, number: str) -> list[str]:
        shorter = {number[:index] + number[index + 1 :] for index in range(len(number))}
        known = set()
        with self.connect() as db:
            for value in sorted(shorter):
                if len(value) == 6 and (
                    db.execute("SELECT 1 FROM deals WHERE deal_id = ? LIMIT 1", [value]).fetchone()
                    or db.execute(
                        "SELECT 1 FROM contracts WHERE contract_id = ? LIMIT 1", [value]
                    ).fetchone()
                ):
                    known.add(value)
                if len(value) == 9 and (
                    db.execute(
                        "SELECT 1 FROM participants WHERE inn = ? LIMIT 1", [value]
                    ).fetchone()
                    or db.execute("SELECT 1 FROM brokers WHERE inn = ? LIMIT 1", [value]).fetchone()
                ):
                    known.add(value)
        return sorted(known)[:3]

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

        family = (
            ", product_family"
            if any(c[0] == "product_family" for c in self.schema["registry"])
            else ""
        )
        return {
            "product": fetch(f"SELECT DISTINCT product_name AS name{family} FROM registry"),
            "company": fetch("SELECT inn, name, role FROM participants"),
            "broker": fetch("SELECT broker_code, inn, name FROM brokers"),
            "region": fetch("SELECT DISTINCT region AS name, region_ru FROM registry"),
            "status": fetch("SELECT DISTINCT status AS name FROM registry"),
            "category": fetch("SELECT DISTINCT category AS name FROM contracts"),
        }

    def lookup(self, kind: str, text: str) -> list[dict]:
        needle = normalize(text)
        if kind == "region":
            names = named_regions(text)
            rows = [entry for entry in self.catalog[kind] if entry["name"] in names]
            if rows:
                match = "exact" if len(rows) == 1 else "partial"
                return [{**entry, "match": match, "score": 100.0} for entry in rows]
        needles = [needle]
        if kind == "product":
            needles += [normalize(alias) for alias in product_aliases(needle)]
        named = kind in NAME_LOOKUP_KINDS
        distinct = distinctive_name(text) if named else ""
        threshold = (
            NAME_MATCH_THRESHOLD if named else PRODUCT_MATCH_THRESHOLD if kind == "product" else 65
        )
        candidates = []
        for entry in self.catalog[kind]:
            values = [normalize(str(value)) for value in entry.values()]
            exact = any(n in values for n in needles)
            partial = any(n and n in v for n in needles for v in values)
            if named:
                fuzzy_ready = bool(distinct) and not distinct.isdigit()
                score = fuzz.ratio(distinct, distinctive_name(entry["name"])) if fuzzy_ready else 0
            elif kind == "product":
                score = max(product_score(n, v) for n in needles for v in values)
            else:
                score = max(fuzz.WRatio(n, v) for n in needles for v in values)
            if exact or partial or score >= threshold:
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
        self.check_filter_values(tree)
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
        }.get(table)
        if key is None:
            raise ValueError("Sample deals from registry, not broker_deals")
        draw = tree.copy()
        draw.set("expressions", [exp.column(key)])
        draw = draw.order_by(exp.Rand()).limit(count)
        population_query = tree.copy()
        population_query.set("expressions", sqlglot.parse_one("SELECT count(*)").expressions)
        with self.connect() as db:
            timer = threading.Timer(timeout, db.interrupt)
            timer.start()
            try:
                keys = [row[0] for row in db.execute(draw.sql(dialect="duckdb")).fetchall()]
                population = db.execute(population_query.sql(dialect="duckdb")).fetchone()[0]
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
        return result.model_copy(update={"selection": "random", "population": population})

    def query(self, sql: str, query_id: str, timeout: float = 8) -> Evidence:
        tree, table = validate_query(sql)
        self.check_filter_values(tree)
        row_limit = row_limit_for(tree, table)
        limit = tree.args.get("limit")
        asked = int(limit.expression.this) if limit else None
        if asked is None or asked > row_limit:
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
                inner = derived_source(tree)
                for index, item in enumerate(tree.expressions):
                    if inner is not None:
                        expressions[columns[index]] = "group_count"
                        break
                    if isinstance(item, exp.Star):
                        expressions.update({column: column for column in columns})
                        break
                    expression = item.this if isinstance(item, exp.Alias) else item
                    expressions[columns[index]] = expression.sql(dialect="duckdb")
                selection_tree = inner if inner is not None else tree
                scope = selection_tree.copy()
                for key in ("group", "having", "order", "limit", "offset", "distinct"):
                    scope.set(key, None)
                if table in DEAL_TABLES:
                    records = "count(DISTINCT deal_id)" if table == "broker_deals" else "count(*)"
                    scope.set(
                        "expressions",
                        sqlglot.parse_one(
                            f"SELECT {records} AS n, min(deal_date), max(deal_date), "
                            "list(DISTINCT currency), list(DISTINCT unit), "
                            f"{records} FILTER (WHERE is_cancelled)"
                        ).expressions,
                    )
                    count, start, end, currencies, units, cancelled = db.execute(
                        scope.sql(dialect="duckdb")
                    ).fetchone()
                    grouped = {
                        column.name
                        for group in (
                            selection_tree.args["group"].expressions
                            if selection_tree.args.get("group")
                            else []
                        )
                        for column in group.find_all(exp.Column)
                    }
                    aggregate_columns = {
                        col.name
                        for aggregate in selection_tree.find_all(exp.AggFunc)
                        for col in aggregate.find_all(exp.Column)
                    }
                    if (
                        len(currencies or []) > 1
                        and aggregate_columns & CURRENCY_COLUMNS
                        and "currency" not in grouped
                    ):
                        raise ValueError("Mixed currencies: group by currency or use amount_uzs")
                    if (
                        len(units or []) > 1
                        and aggregate_columns & UNIT_COLUMNS
                        and "unit" not in grouped
                    ):
                        raise ValueError(
                            "Mixed units: group by unit or use mass_kg for kg/tonne only"
                        )
                    ordered = {
                        column.name
                        for item in (
                            tree.args["order"].expressions if tree.args.get("order") else []
                        )
                        for column in item.find_all(exp.Column)
                    }
                    if not grouped:
                        if len(currencies or []) > 1 and ordered & CURRENCY_COLUMNS:
                            raise ValueError(
                                "Mixed currencies cannot be ranked: ORDER BY amount_uzs or filter one currency"
                            )
                        if len(units or []) > 1 and ordered & UNIT_COLUMNS:
                            raise ValueError("Mixed units cannot be ranked: filter one unit")
                    if aggregate_columns & {"mass_kg", "mass_t", "delivered_mass_kg"} and set(
                        units or []
                    ) - {
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
                    start = end = cancelled = None
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
                    table in DEAL_TABLES
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
                    requested_count=asked if asked and len(rows) > row_limit else None,
                    row_limit=row_limit,
                    expressions=expressions,
                    selected_record_count=selected_count,
                    cancelled_records=cancelled,
                    grouped=bool(selection_tree.args.get("group") or tree.find(exp.AggFunc)),
                    available_columns=[
                        column[0]
                        for column in self.schema[table]
                        if column[0] not in {"source_file", "source_row"}
                    ],
                )
            finally:
                timer.cancel()


def calculated_value(operation: str, n: Decimal, d: Decimal) -> Decimal | None:
    if operation == "difference":
        return n - d
    if operation == "add":
        return n + d
    if operation == "multiply":
        return n * d
    if operation == "percent_of":
        return n * d / 100
    if operation == "range_size":
        return n - d + 1
    if d == 0:
        return None
    if operation == "change_percent":
        return (n - d) / d * 100
    if operation in {"percentage", "share_percent"}:
        return n / d * 100
    return n / d


def result_column_name(row: dict) -> str:
    if "ratio" not in row:
        return "ratio"
    index = 2
    while f"ratio_{index}" in row:
        index += 1
    return f"ratio_{index}"


def arrange_result(
    evidence: Evidence, column: str, direction: str, keep_first: int | None
) -> Evidence:
    if evidence.capped:
        raise ValueError("Sorting needs the complete result, not a capped one")
    if not evidence.rows or column not in evidence.rows[0]:
        raise ValueError("The sorting field must exist in the cited result")
    if keep_first is not None and keep_first < 1:
        raise ValueError("keep_first must be at least 1")
    known = sorted(
        (row for row in evidence.rows if row[column] is not None),
        key=lambda row: Decimal(str(row[column])),
        reverse=direction == "descending",
    )
    blanks = [row for row in evidence.rows if row[column] is None]
    if keep_first is None:
        return evidence.model_copy(update={"rows": known + blanks})
    end = min(keep_first, len(known))
    while 0 < end < len(known) and Decimal(str(known[end][column])) == Decimal(
        str(known[end - 1][column])
    ):
        end += 1
    return evidence.model_copy(update={"rows": known[:end]})


def calculate_ratio(
    evidence: Evidence, numerator: str, denominator: str, scale: int, operation: str = "ratio"
) -> Evidence:
    if not evidence.rows or not 0 <= scale <= 6:
        raise ValueError("A nonempty query and scale between 0 and 6 are required")
    measures = evidence.expressions
    if operation != "share_percent" and measures.get(numerator, numerator) == measures.get(
        denominator, denominator
    ):
        raise ValueError(
            "Numerator and denominator are the same measure, so the result means nothing. "
            "Select two different measures, for example COUNT(*) FILTER (WHERE ...) and COUNT(*), "
            "or one column per period."
        )
    total = None
    if operation == "share_percent":
        if evidence.capped:
            raise ValueError("A share of the total needs the complete result, not a capped one")
        if numerator not in evidence.rows[0]:
            raise ValueError("Calculation fields must exist in the cited result")
        with localcontext() as context:
            context.prec = 50
            total = sum(
                (
                    Decimal(str(row[numerator]))
                    for row in evidence.rows
                    if row[numerator] is not None
                ),
                Decimal(0),
            )
    rows = []
    column = result_column_name(evidence.rows[0])
    for row in evidence.rows:
        if numerator not in row or (total is None and denominator not in row):
            raise ValueError("Calculation fields must exist in the cited result")
        if row[numerator] is None or (total is None and row[denominator] is None):
            value = None
        else:
            with localcontext() as context:
                context.prec = 50
                n = Decimal(str(row[numerator]))
                d = total if total is not None else Decimal(str(row[denominator]))
                computed = (
                    calculated_value(operation, n, d) if n.is_finite() and d.is_finite() else None
                )
                value = (
                    None
                    if computed is None
                    else str(computed.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP))
                )
        rows.append({**row, column: value})
    text = f"{operation}({numerator}, {denominator}); ROUND_HALF_UP, {scale} decimals"
    return evidence.model_copy(
        update={
            "rows": rows,
            "calculation": text,
            "computed_columns": {**evidence.computed_columns, column: text},
        }
    )
