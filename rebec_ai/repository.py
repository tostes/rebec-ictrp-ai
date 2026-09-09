# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional

import mysql.connector

from .settings import MYSQL_CONFIG
from .trial_rules import recruitment_freshness


def get_conn():
    return mysql.connector.connect(**MYSQL_CONFIG)


def _values(cur, sql: str) -> List[str]:
    cur.execute(sql)
    return [
        row["value"]
        for row in cur.fetchall()
        if row.get("value") not in (None, "")
    ]


def get_options() -> Dict[str, List[str]]:
    """
    Return closed-search options from values that actually exist
    in the normalized ICTRP database.

    Important:
    - Avoid complex DISTINCT + ORDER BY expressions because older
      MySQL configurations may reject them.
    - Deduplicate/sort in Python.
    - Expose the RAW XML values as select values.
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT study_type, study_type_raw
            FROM ictrp_trial
            WHERE study_type IN (
                'interventional',
                'observational'
            )
              AND study_type_raw IS NOT NULL
              AND study_type_raw <> ''
            """
        )
        rows = cur.fetchall()

        study_type_pairs = {}
        for row in rows:
            raw = row.get("study_type_raw")
            canonical = row.get("study_type")
            if raw:
                study_type_pairs[str(raw)] = canonical

        study_type = sorted(
            study_type_pairs.keys(),
            key=lambda x: (
                0 if study_type_pairs[x] == "interventional"
                else 1 if study_type_pairs[x] == "observational"
                else 9,
                x.lower(),
            )
        )

        cur.execute(
            """
            SELECT
                recruitment_status,
                recruitment_status_raw
            FROM ictrp_trial
            WHERE recruitment_status IS NOT NULL
              AND recruitment_status <> 'other'
              AND recruitment_status_raw IS NOT NULL
              AND recruitment_status_raw <> ''
            """
        )
        rows = cur.fetchall()

        recruitment_order = {
            "recruiting": 1,
            "not_yet_recruiting": 2,
            "active_not_recruiting": 3,
            "completed": 4,
            "data_analysis_completed": 5,
            "suspended": 6,
            "terminated": 7,
            "withdrawn": 8,
        }

        recruitment_pairs = {}
        for row in rows:
            raw = row.get("recruitment_status_raw")
            canonical = row.get("recruitment_status")
            if raw:
                recruitment_pairs[str(raw)] = canonical

        recruitment_status = sorted(
            recruitment_pairs.keys(),
            key=lambda x: (
                recruitment_order.get(
                    recruitment_pairs[x],
                    99
                ),
                x.lower(),
            )
        )

        cur.execute(
            """
            SELECT phase, phase_raw
            FROM ictrp_trial
            WHERE phase IS NOT NULL
              AND phase <> 'other'
              AND phase_raw IS NOT NULL
              AND phase_raw <> ''
            """
        )
        rows = cur.fetchall()

        phase_order = {
            "0": 0,
            "1": 1,
            "1-2": 2,
            "2": 3,
            "2-3": 4,
            "3": 5,
            "3-4": 6,
            "4": 7,
            "n/a": 99,
        }

        phase_pairs = {}
        for row in rows:
            raw = row.get("phase_raw")
            canonical = row.get("phase")
            if raw:
                phase_pairs[str(raw)] = canonical

        phase = sorted(
            phase_pairs.keys(),
            key=lambda x: (
                phase_order.get(
                    phase_pairs[x],
                    100
                ),
                x.lower(),
            )
        )

        cur.execute(
            """
            SELECT gender, gender_raw
            FROM ictrp_trial
            WHERE gender IS NOT NULL
              AND gender_raw IS NOT NULL
              AND gender_raw <> ''
            """
        )
        rows = cur.fetchall()

        gender_order = {
            "female": 1,
            "male": 2,
            "both": 3,
            "all": 3,
        }

        gender_pairs = {}
        for row in rows:
            raw = row.get("gender_raw")
            canonical = row.get("gender")
            if raw:
                gender_pairs[str(raw)] = canonical

        gender = sorted(
            gender_pairs.keys(),
            key=lambda x: (
                gender_order.get(
                    gender_pairs[x],
                    99
                ),
                x.lower(),
            )
        )

        cur.execute(
            """
            SELECT DISTINCT country_code
            FROM ictrp_trial_country
            WHERE country_code IS NOT NULL
              AND country_code <> ''
            """
        )
        country = sorted(
            {
                str(row["country_code"])
                for row in cur.fetchall()
                if row.get("country_code")
            },
            key=lambda x: x.lower(),
        )

        return {
            "study_type": study_type,
            "recruitment_status":
                recruitment_status,
            "phase": phase,
            "gender": gender,
            "country": country,
        }

    finally:
        cur.close()
        conn.close()


def get_trial_detail(trial_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                t.id,
                t.trial_id,
                t.utrn,
                t.date_registration_raw,
                t.date_registration,
                t.primary_sponsor,
                t.public_title,
                t.acronym,
                t.scientific_title,
                t.scientific_acronym,
                t.date_enrolment_raw,
                t.date_enrolment,
                t.type_enrolment,
                t.target_size_raw,
                t.target_size,
                t.recruitment_status_raw,
                t.recruitment_status,
                t.url,
                t.study_type_raw,
                t.study_type,
                t.study_design,
                t.phase_raw,
                t.phase,
                t.hc_freetext,
                t.i_freetext,
                t.inclusion_criteria,
                t.exclusion_criteria,
                t.age_min_raw,
                t.age_max_raw,
                t.age_min_years,
                t.age_max_years,
                t.gender_raw,
                t.gender,
                t.results_actual_enrolment,
                t.results_date_completed,
                t.results_url_link,
                t.results_summary,
                r.registry_name,
                r.registry_code,
                r.registry_country
            FROM ictrp_trial t
            JOIN ictrp_registry r
              ON r.id = t.registry_id
            WHERE t.trial_id = %s
            LIMIT 1
            """,
            (trial_id,),
        )

        trial = cur.fetchone()

        if not trial:
            return None

        trial_pk = trial["id"]

        children = {
            "countries": (
                "ictrp_trial_country",
                "country_code"
            ),
            "condition_codes": (
                "ictrp_trial_condition_code",
                "condition_code"
            ),
            "condition_keywords": (
                "ictrp_trial_condition_keyword",
                "keyword"
            ),
            "intervention_codes": (
                "ictrp_trial_intervention_code",
                "intervention_code"
            ),
            "intervention_keywords": (
                "ictrp_trial_intervention_keyword",
                "keyword"
            ),
            "secondary_sponsors": (
                "ictrp_trial_secondary_sponsor",
                "sponsor_name"
            ),
        }

        out = dict(trial)

        for key, (table, field) in children.items():
            cur.execute(
                f"""
                SELECT {field} AS value
                FROM {table}
                WHERE trial_pk = %s
                ORDER BY {field}
                """,
                (trial_pk,),
            )
            out[key] = [
                row["value"]
                for row in cur.fetchall()
                if row.get("value") not in (None, "")
            ]

        cur.execute(
            """
            SELECT secondary_id, issuing_authority
            FROM ictrp_trial_secondary_id
            WHERE trial_pk = %s
            ORDER BY id
            """,
            (trial_pk,),
        )
        out["secondary_ids"] = cur.fetchall()

        cur.execute(
            """
            SELECT outcome_text
            FROM ictrp_trial_primary_outcome
            WHERE trial_pk = %s
            ORDER BY id
            """,
            (trial_pk,),
        )
        out["primary_outcomes"] = [
            row["outcome_text"]
            for row in cur.fetchall()
            if row.get("outcome_text")
        ]

        cur.execute(
            """
            SELECT outcome_text
            FROM ictrp_trial_secondary_outcome
            WHERE trial_pk = %s
            ORDER BY id
            """,
            (trial_pk,),
        )
        out["secondary_outcomes"] = [
            row["outcome_text"]
            for row in cur.fetchall()
            if row.get("outcome_text")
        ]

        freshness = recruitment_freshness(
            trial.get("date_enrolment"),
            trial.get("type_enrolment"),
            trial.get("recruitment_status"),
        )

        out["recruitment_freshness"] = freshness
        out["registration_url"] = trial.get("url")

        return out

    finally:
        cur.close()
        conn.close()


def get_trial_xml(trial_id: str) -> Optional[str]:
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT x.trial_xml
            FROM ictrp_trial_xml x
            JOIN ictrp_trial t ON t.id = x.trial_pk
            WHERE t.trial_id = %s
            LIMIT 1
            """,
            (trial_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()


def get_trials_xml(trial_ids: List[str]) -> List[Dict[str, str]]:
    ids = [x for x in trial_ids if x]

    if not ids:
        return []

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    try:
        by_id = {}
        chunk_size = 500

        for offset in range(0, len(ids), chunk_size):
            chunk = ids[offset:offset + chunk_size]
            placeholders = ",".join(["%s"] * len(chunk))

            cur.execute(
                f"""
                SELECT
                    t.trial_id,
                    x.trial_xml
                FROM ictrp_trial t
                JOIN ictrp_trial_xml x
                  ON x.trial_pk = t.id
                WHERE t.trial_id IN ({placeholders})
                """,
                tuple(chunk),
            )

            for row in cur.fetchall():
                by_id[row["trial_id"]] = row["trial_xml"]

        return [
            {
                "trial_id": trial_id,
                "trial_xml": by_id[trial_id],
            }
            for trial_id in ids
            if trial_id in by_id
        ]

    finally:
        cur.close()
        conn.close()
