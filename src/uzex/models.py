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
    count: int = Field(ge=1, le=100)


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


class Calculation(StrictModel):
    query_id: str
    numerator: str
    denominator: str
    scale: int = Field(ge=0, le=6)
    operation: Literal["ratio", "percentage", "change_percent"]


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
    ]
    candidates_query_id: str | None


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
    expressions: dict[str, str] = Field(default_factory=dict)
    selected_record_count: int | None = None
    row_limit: int = 100
    selection: Literal["query", "random"] = "query"


class Answer(BaseModel):
    outcome: Literal["answer", "no_match", "unavailable", "clarify", "error"]
    language: Literal["uz", "ru"] = "uz"
    reason: str = "none"
    evidence: Evidence | None = None
    candidates: list[dict] = Field(default_factory=list)
    elapsed_seconds: float = 0
    request_id: str = ""
    missing_fields: list[MissingField] = Field(default_factory=list)
    continues_pending: bool = False
