from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Lookup(StrictModel):
    kind: Literal["product", "company", "broker", "region", "status", "category"]
    text: str = Field(min_length=1, max_length=200)


class Query(StrictModel):
    sql: str = Field(min_length=1, max_length=8000)


class SampleQuery(Query):
    count: int = Field(ge=1)


MissingField = Literal[
    "entity",
    "product",
    "period",
    "metric",
    "unit",
    "currency",
    "role",
    "region",
    "reference",
    "comparison",
    "ranking",
    "delivery",
    "record_kind",
]


class RequestReview(StrictModel):
    language: Literal["uz", "ru"]
    task: Literal[
        "detail",
        "count",
        "turnover",
        "price",
        "volume",
        "rank",
        "compare",
        "list",
        "deadline",
        "rate",
        "unsupported",
        "unknown",
    ]
    subject: Literal["deal", "contract", "company", "broker", "product", "market", "unknown"]
    reference: Literal["specified", "context", "not_needed", "missing"]
    entity_text: str | None
    period: Literal["specified", "context", "all_available", "not_needed", "missing"]
    ranking_by: Literal["count", "amount", "volume", "not_needed", "missing"]
    missing_fields: list[MissingField]
    continuation: bool


class AskClarification(StrictModel):
    language: Literal["uz", "ru"]
    fields: list[MissingField] = Field(min_length=1, max_length=3)
    candidates_query_id: str | None


class AboutPrevious(StrictModel):
    language: Literal["uz", "ru"]
    topic: Literal[
        "completeness",
        "method",
        "source",
        "cancellation",
        "confidence",
        "next_page",
        "export",
    ]


class Calculation(StrictModel):
    query_id: str
    numerator: str
    denominator: str
    scale: int = Field(ge=0, le=6)
    operation: Literal[
        "ratio",
        "percentage",
        "change_percent",
        "share_percent",
        "difference",
        "add",
        "multiply",
        "percent_of",
        "range_size",
    ]


class Arrangement(StrictModel):
    query_id: str
    column: str
    direction: Literal["descending", "ascending"]
    keep_first: int | None


class Finish(StrictModel):
    outcome: Literal["answer", "no_match", "unavailable", "clarify"]
    query_id: str | None
    language: Literal["uz", "ru"]
    reason: Literal[
        "none",
        "outside_dates",
        "missing_field",
        "ambiguous_entity",
        "ambiguous_metric",
        "mixed_units",
        "mixed_currencies",
        "unsupported",
        "not_found",
        "out_of_scope",
    ]
    candidates_query_id: str | None
    also_query_ids: list[str]


class Evidence(BaseModel):
    query_id: str
    sql: str
    table: str
    rows: list[dict]
    matched_count: int
    samples: list[dict]
    period_start: str | None
    period_end: str | None
    currencies: list[str]
    units: list[str]
    filters: str | None
    truncated: bool = False
    calculation: str | None = None
    computed_columns: dict[str, str] = Field(default_factory=dict)
    expressions: dict[str, str] = Field(default_factory=dict)
    selected_record_count: int | None = None
    row_limit: int = 100
    selection: Literal["query", "random"] = "query"
    population: int | None = None
    available_columns: list[str] = Field(default_factory=list)
    requested_count: int | None = None
    grouped: bool = False
    cancelled_records: int | None = None

    @property
    def capped(self) -> bool:
        return self.truncated or (
            not self.grouped
            and len(self.rows) >= self.row_limit
            and self.matched_count > len(self.rows)
        )


class Answer(BaseModel):
    outcome: Literal["answer", "no_match", "unavailable", "clarify", "error", "about"]
    language: Literal["uz", "ru"] = "uz"
    reason: str = "none"
    topic: str | None = None
    identifier: str | None = None
    evidence: Evidence | None = None
    extra_evidence: list[Evidence] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    elapsed_seconds: float = 0
    request_id: str = ""
    missing_fields: list[MissingField] = Field(default_factory=list)
    continues_pending: bool = False
