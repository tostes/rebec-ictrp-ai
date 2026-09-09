# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional


OPEN_RECRUITMENT_STATUSES = {
    "recruiting",
    "not_yet_recruiting",
    "not yet recruiting",
}


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    return None


def recruitment_freshness(
    date_enrolment: Any,
    type_enrolment: Any,
    recruitment_status: Any,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    ReBEC warning rule.

    A recruitment status is considered *possibly outdated* when:
      1. type_enrolment == "actual";
      2. the actual enrolment date is more than one year old; and
      3. the current status still indicates open recruitment.

    The third condition avoids warning on already-completed/terminated
    trials, where an old actual enrolment date is expected.
    """
    today = today or date.today()
    enrolment_date = _to_date(date_enrolment)
    enrolment_type = str(type_enrolment or "").strip().lower()
    status = str(recruitment_status or "").strip().lower()

    older_than_one_year = bool(
        enrolment_date
        and enrolment_date < (today - timedelta(days=365))
    )

    status_is_open = status in OPEN_RECRUITMENT_STATUSES

    possibly_outdated = bool(
        enrolment_type == "actual"
        and older_than_one_year
        and status_is_open
    )

    days_since = None
    if enrolment_date:
        days_since = (today - enrolment_date).days

    return {
        "possibly_outdated": possibly_outdated,
        "date_enrolment": (
            enrolment_date.isoformat()
            if enrolment_date
            else None
        ),
        "type_enrolment": type_enrolment,
        "days_since_enrolment": days_since,
        "status_is_open": status_is_open,
        "rule": (
            "type_enrolment=actual + date_enrolment older than 1 year "
            "+ recruitment status still open"
        ),
    }
