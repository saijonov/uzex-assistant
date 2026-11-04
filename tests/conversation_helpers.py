from uzex.models import Answer, RequestReview


def enqueue(service, text, update=1, chat=1):
    service.state.enqueue(update, chat, {"type": "message", "text": text})
    return service.state.claim()


def price_review(**overrides):
    values = {
        "language": "uz",
        "task": "price",
        "subject": "product",
        "reference": "specified",
        "entity_text": "Shakar",
        "period": "specified",
        "ranking_by": "not_needed",
        "missing_fields": [],
        "continuation": False,
    }
    return RequestReview(**{**values, **overrides})


def stored(sample_database, sql, language="uz"):
    return Answer(outcome="answer", language=language, evidence=sample_database.query(sql, "q1"))


def raw(sample_database, sql):
    with sample_database.connect() as db:
        return db.execute(sql).fetchone()[0]
