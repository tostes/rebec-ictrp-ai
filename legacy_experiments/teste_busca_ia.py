#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path

import requests
import mysql.connector

from config import MYSQL_CONFIG


# ============================================================
# CONFIGURAÇÃO
# ============================================================

LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
PROMPT_FILE = Path(__file__).with_name("rebec_system_prompt.txt")
LOG_FILE = Path(__file__).with_name("rebec_ai_search.log")

DEFAULT_SYSTEM_PROMPT = """
You are ReBEC Search Parser.

Return only valid JSON with these fields:
condition
intervention
title
recruitment_status
phase
gender
age_min_years
age_max_years
country
sponsor
study_type
registration_date_from
registration_date_to

Return null for unspecified fields.
Never invent filters.
"""


# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("rebec_ai_search")


# ============================================================
# EXPANSÕES SEMÂNTICAS PONDERADAS
# ============================================================

CONDITION_EXPANSIONS = {
    "balance problems": {
        "strong": [
            "balance problems",
            "postural balance",
            "balance control",
            "equilibrium",
            "postural instability",
            "body imbalance",
        ],
        "medium": [
            "risk of falls",
            "prevention of falls",
            "accidental falls",
            "falls",
            "fall risk",
        ],
        "weak": [
            "mobility limitation",
        ],
    },

    "balance disorder": {
        "strong": [
            "balance disorder",
            "postural balance",
            "balance control",
            "equilibrium",
            "postural instability",
            "body imbalance",
        ],
        "medium": [
            "accidental falls",
            "falls",
            "fall risk",
        ],
        "weak": [
            "mobility limitation",
        ],
    },

    "hypertension": {
        "strong": [
            "hypertension",
            "arterial hypertension",
            "systemic arterial hypertension",
            "high blood pressure",
        ],
        "medium": [],
        "weak": [],
    },

    "diabetes mellitus": {
        "strong": [
            "diabetes mellitus",
            "type 1 diabetes",
            "type 2 diabetes",
            "diabetes",
        ],
        "medium": [
            "hyperglycemia",
        ],
        "weak": [],
    },

    "breast cancer": {
        "strong": [
            "breast cancer",
            "breast carcinoma",
            "breast neoplasm",
            "malignant neoplasm of breast",
        ],
        "medium": [],
        "weak": [],
    },

    "hiv": {
        "strong": [
            "hiv",
            "human immunodeficiency virus",
            "hiv infection",
            "hiv infections",
            "hiv/aids",
            "hiv aids",
        ],
        "medium": [],
        "weak": [],
    },

    "aids": {
        "strong": [
            "aids",
            "acquired immunodeficiency syndrome",
            "hiv/aids",
        ],
        "medium": [
            "human immunodeficiency virus",
        ],
        "weak": [],
    },

    "copd": {
        "strong": [
            "copd",
            "chronic obstructive pulmonary disease",
            "chronic obstructive lung disease",
        ],
        "medium": [],
        "weak": [],
    },

    "stroke": {
        "strong": [
            "stroke",
            "cerebrovascular accident",
            "cerebrovascular disease",
            "post-stroke",
        ],
        "medium": [
            "hemiparesis",
        ],
        "weak": [],
    },

    "parkinson disease": {
        "strong": [
            "parkinson disease",
            "parkinson's disease",
            "parkinsonism",
        ],
        "medium": [],
        "weak": [],
    },

    "alzheimer disease": {
        "strong": [
            "alzheimer disease",
            "alzheimer's disease",
            "dementia in alzheimer",
        ],
        "medium": [
            "dementia",
        ],
        "weak": [],
    },

    "obesity": {
        "strong": [
            "obesity",
            "obese",
        ],
        "medium": [
            "overweight",
        ],
        "weak": [
            "body mass index",
        ],
    },
}


INTERVENTION_EXPANSIONS = {
    "physical exercise": {
        "strong": [
            "physical exercise",
            "physical exercises",
            "exercise training",
            "exercise program",
            "physical training",
            "strength training",
            "resistance training",
            "functional training",
            "aerobic exercise",
            "water aerobics",
            "gymnastics",
        ],
        "medium": [
            "physical activity",
            "exercise therapy",
            "strengthening exercises",
            "muscle strengthening",
        ],
        "weak": [
            "exercise",
            "training",
        ],
    },

    "physiotherapy": {
        "strong": [
            "physiotherapy",
            "physical therapy",
            "physical rehabilitation",
        ],
        "medium": [
            "rehabilitation",
            "physiotherapeutic",
        ],
        "weak": [],
    },

    "rehabilitation": {
        "strong": [
            "rehabilitation",
            "physical rehabilitation",
        ],
        "medium": [
            "physiotherapy",
            "physical therapy",
        ],
        "weak": [],
    },

    "strength training": {
        "strong": [
            "strength training",
            "resistance training",
            "strengthening exercises",
            "muscle strengthening",
        ],
        "medium": [
            "physical exercise",
        ],
        "weak": [
            "exercise",
        ],
    },

    "vaccine": {
        "strong": [
            "vaccine",
            "vaccination",
            "immunization",
        ],
        "medium": [],
        "weak": [],
    },

    "telemedicine": {
        "strong": [
            "telemedicine",
            "telehealth",
        ],
        "medium": [
            "remote monitoring",
            "telephone",
        ],
        "weak": [],
    },
}


WEIGHTS = {
    "exact": 30,
    "strong": 15,
    "medium": 8,
    "weak": 2,
}

SOURCE_WEIGHTS_CONDITION = {
    "hc_code": 1.30,
    "hc_keyword": 1.20,
    "hc_freetext": 1.00,
    "translations.hc_freetext": 0.90,
}

SOURCE_WEIGHTS_INTERVENTION = {
    "i_code": 1.25,
    "intervention_keyword": 1.25,
    "i_freetext": 1.00,
    "translations.i_freetext": 0.90,
}

DEFAULT_SOURCE_WEIGHT = 1.00

SATURATION_CONDITION = 40.0
SATURATION_INTERVENTION = 50.0

TITLE_BONUS = {
    "condition": 10.0,
    "intervention": 10.0,
    "older_adult": 5.0,
}


# ============================================================
# UTILITÁRIOS
# ============================================================

def load_system_prompt():
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8")
    return DEFAULT_SYSTEM_PROMPT


SYSTEM_PROMPT = load_system_prompt()


def clean_text(value):
    if value is None:
        return ""

    value = str(value).lower().strip()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )
    value = re.sub(r"\s+", " ", value)
    return value


def safe_list(value):
    return value if isinstance(value, list) else []


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def age_to_years(value, unit):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    unit = clean_text(unit).upper()

    if unit == "Y":
        return value
    if unit == "M":
        return value / 12.0
    if unit == "W":
        return value / 52.1429
    if unit == "D":
        return value / 365.25

    return None



def numeric_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def source_text_map_condition(trial):
    """
    Retorna os textos de condição separados por origem para permitir
    explicação de onde cada match foi encontrado.
    """
    sources = {}

    value = trial.get("hc_freetext")
    if value:
        sources["hc_freetext"] = clean_text(value)

    translated = []
    for translation in safe_list(trial.get("translations")):
        translation = safe_dict(translation)
        value = translation.get("hc_freetext")
        if value:
            translated.append(str(value))

    if translated:
        sources["translations.hc_freetext"] = clean_text(
            " ".join(translated)
        )

    for key in ("hc_code", "hc_keyword"):
        parts = []
        for item in safe_list(trial.get(key)):
            item = safe_dict(item)

            for field in ("text", "description", "label"):
                value = item.get(field)
                if value:
                    parts.append(str(value))

            for translation in safe_list(item.get("translations")):
                translation = safe_dict(translation)

                for field in ("text", "description", "label"):
                    value = translation.get(field)
                    if value:
                        parts.append(str(value))

        if parts:
            sources[key] = clean_text(" ".join(parts))

    return sources


def source_text_map_intervention(trial):
    """
    Retorna os textos de intervenção separados por origem.
    """
    sources = {}

    value = trial.get("i_freetext")
    if value:
        sources["i_freetext"] = clean_text(value)

    translated = []
    for translation in safe_list(trial.get("translations")):
        translation = safe_dict(translation)
        value = translation.get("i_freetext")
        if value:
            translated.append(str(value))

    if translated:
        sources["translations.i_freetext"] = clean_text(
            " ".join(translated)
        )

    for key in ("intervention_keyword", "i_code"):
        parts = []

        for item in safe_list(trial.get(key)):
            item = safe_dict(item)

            for field in ("text", "description", "label"):
                value = item.get(field)
                if value:
                    parts.append(str(value))

            for translation in safe_list(item.get("translations")):
                translation = safe_dict(translation)

                for field in ("text", "description", "label"):
                    value = translation.get(field)
                    if value:
                        parts.append(str(value))

        if parts:
            sources[key] = clean_text(" ".join(parts))

    return sources


def find_sources_for_term(term, source_map):
    cleaned = clean_text(term)

    return [
        source
        for source, text in source_map.items()
        if cleaned and cleaned in text
    ]


def empty_filter_dict():
    return {
        "condition": None,
        "intervention": None,
        "title": None,
        "recruitment_status": None,
        "phase": None,
        "gender": None,
        "age_min_years": None,
        "age_max_years": None,
        "country": None,
        "sponsor": None,
        "study_type": None,
        "registration_date_from": None,
        "registration_date_to": None,
    }


# ============================================================
# EXPANSÃO SEMÂNTICA
# ============================================================

def weighted_expansion(value, dictionary):
    if not value:
        return {
            "concept": None,
            "strong": [],
            "medium": [],
            "weak": [],
        }

    key = clean_text(value)

    result = {
        "concept": value,
        "strong": [],
        "medium": [],
        "weak": [],
    }

    if key in dictionary:
        for level in ("strong", "medium", "weak"):
            result[level] = list(
                dictionary[key].get(level, [])
            )
    else:
        result["strong"] = [value]

    # Garante que o conceito original esteja presente
    if value not in result["strong"]:
        result["strong"].insert(0, value)

    return result


def build_semantic_expansions(filters):
    return {
        "condition":
            weighted_expansion(
                filters.get("condition"),
                CONDITION_EXPANSIONS
            ),

        "intervention":
            weighted_expansion(
                filters.get("intervention"),
                INTERVENTION_EXPANSIONS
            ),
    }


# ============================================================
# EXTRAÇÃO DETERMINÍSTICA
# ============================================================


def detect_age_intent(query):
    """
    Distingue uma faixa etária explícita de uma população descrita
    semanticamente como idosa/older adults.
    """
    q = clean_text(query)

    older_adult_terms = (
        "older adults",
        "elderly",
        "older people",
        "idosos",
        "idosas",
        "adultos maiores",
        "adultos mayores",
        "personnes agees",
        "personnes âgées",
    )

    for term in older_adult_terms:
        if term in q:
            return "older_adult"

    return None


def explicit_filters_from_query(query):
    q = clean_text(query)
    result = empty_filter_dict()

    roman = {
        "i": "1",
        "ii": "2",
        "iii": "3",
        "iv": "4",
    }

    m = re.search(
        r"\b(?:phase|fase)\s*(1|2|3|4|i{1,3}|iv)\b",
        q,
        re.IGNORECASE
    )
    if m:
        v = m.group(1).lower()
        result["phase"] = roman.get(v, v)

    if re.search(
        r"\b(recruiting|recrutando|reclutando|en recrutement)\b",
        q
    ):
        result["recruitment_status"] = "recruiting"

    elif re.search(
        r"\b(not yet recruiting|ainda nao recrutando|todavia no reclutando)\b",
        q
    ):
        result["recruitment_status"] = "not-yet-recruiting"

    elif re.search(
        r"\b(completed|concluido|concluidos|completado|terminado)\b",
        q
    ):
        result["recruitment_status"] = "completed"

    if re.search(
        r"\b(women|woman|female|mulheres|mulher|mujeres|mujer|femmes|femme)\b",
        q
    ):
        result["gender"] = "female"

    elif re.search(
        r"\b(men|man|male|homens|homem|hombres|hombre|hommes|homme)\b",
        q
    ):
        result["gender"] = "male"

    m = re.search(
        r"\b(?:above|over|older than|mais de|acima de|maiores de|mayores de)\s*(\d{1,3})\b",
        q
    )
    if m:
        result["age_min_years"] = float(m.group(1))

    m = re.search(
        r"\b(?:under|younger than|menos de|abaixo de|menores de)\s*(\d{1,3})\b",
        q
    )
    if m:
        result["age_max_years"] = float(m.group(1))

    m = re.search(
        r"\b(\d{1,3})\s*(?:-|to|a)\s*(\d{1,3})\s*(?:years|anos|anos de idade)?\b",
        q
    )
    if m:
        result["age_min_years"] = float(m.group(1))
        result["age_max_years"] = float(m.group(2))

    if re.search(
        r"\b(older adults|elderly|older people|idosos|idosas|adultos maiores|adultos mayores|personnes agees|personnes âgées)\b",
        q
    ):
        if result["age_min_years"] is None:
            result["age_min_years"] = 60.0

    acronyms = [
        "HIV",
        "AIDS",
        "HPV",
        "COPD",
        "COVID-19",
        "COVID19",
        "HCV",
        "HBV",
        "SARS-COV-2",
    ]

    original_upper = query.upper()

    for acronym in acronyms:
        if re.search(
            r"\b" + re.escape(acronym) + r"\b",
            original_upper
        ):
            result["condition"] = acronym
            break

    return result


def merge_filters(llm_filters, explicit_filters):
    merged = dict(llm_filters)

    for key, value in explicit_filters.items():
        if value is not None:
            merged[key] = value

    return merged


def has_any_filter(filters):
    return any(
        value is not None
        for value in filters.values()
    )


# ============================================================
# LLM
# ============================================================

def ask_llm(query, debug=False):
    payload = {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "temperature": 0,
        "max_tokens": 300,
        "chat_template_kwargs": {
            "enable_thinking": False
        }
    }

    response = requests.post(
        LLM_URL,
        json=payload,
        timeout=60
    )

    response.raise_for_status()
    data = response.json()

    if debug:
        print("\n===== RESPOSTA BRUTA DO LLM =====")
        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            )
        )
        print("=================================\n")

    message = data["choices"][0]["message"]
    content = (message.get("content") or "").strip()

    if not content:
        raise RuntimeError(
            "O LLM retornou content vazio."
        )

    if content.startswith("```"):
        content = (
            content
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

    filters = json.loads(content)
    normalized = empty_filter_dict()

    for field in normalized:
        normalized[field] = filters.get(field)

    return normalized


# ============================================================
# EXTRAÇÃO DO JSON REBEC
# ============================================================

def add_item_text(parts, item):
    item = safe_dict(item)

    for field in (
        "text",
        "description",
        "label"
    ):
        value = item.get(field)
        if value:
            parts.append(str(value))

    for translation in safe_list(
        item.get("translations")
    ):
        translation = safe_dict(translation)

        for field in (
            "text",
            "description",
            "label"
        ):
            value = translation.get(field)
            if value:
                parts.append(str(value))


def build_condition_text(trial):
    parts = []

    value = trial.get("hc_freetext")
    if value:
        parts.append(str(value))

    for translation in safe_list(
        trial.get("translations")
    ):
        translation = safe_dict(translation)
        value = translation.get("hc_freetext")

        if value:
            parts.append(str(value))

    for key in (
        "hc_code",
        "hc_keyword"
    ):
        for item in safe_list(
            trial.get(key)
        ):
            add_item_text(parts, item)

    return clean_text(" ".join(parts))


def build_intervention_text(trial):
    parts = []

    value = trial.get("i_freetext")
    if value:
        parts.append(str(value))

    for translation in safe_list(
        trial.get("translations")
    ):
        translation = safe_dict(translation)
        value = translation.get("i_freetext")

        if value:
            parts.append(str(value))

    for item in safe_list(
        trial.get("intervention_keyword")
    ):
        add_item_text(parts, item)

    for item in safe_list(
        trial.get("i_code")
    ):
        add_item_text(parts, item)

    return clean_text(" ".join(parts))


def build_title_text(trial):
    parts = []

    for field in (
        "public_title",
        "scientific_title",
        "acronym",
        "scientific_acronym",
    ):
        value = trial.get(field)
        if value:
            parts.append(str(value))

    for translation in safe_list(
        trial.get("translations")
    ):
        translation = safe_dict(translation)

        for field in (
            "public_title",
            "scientific_title",
            "acronym",
            "scientific_acronym",
        ):
            value = translation.get(field)
            if value:
                parts.append(str(value))

    return clean_text(" ".join(parts))


# ============================================================
# SCORE EXPLICÁVEL
# ============================================================


def extract_snippet(text, term, radius=70):
    """
    Retorna um pequeno trecho do texto ao redor do termo encontrado.
    """
    if not text or not term:
        return ""

    cleaned_text = clean_text(text)
    cleaned_term = clean_text(term)

    pos = cleaned_text.find(cleaned_term)

    if pos < 0:
        return ""

    start = max(
        0,
        pos - radius
    )

    end = min(
        len(cleaned_text),
        pos + len(cleaned_term) + radius
    )

    snippet = cleaned_text[
        start:end
    ].strip()

    if start > 0:
        snippet = "..." + snippet

    if end < len(cleaned_text):
        snippet = snippet + "..."

    return snippet


def best_source_and_snippet(
    term,
    source_map,
    source_weights
):
    """
    Retorna a origem de maior peso onde o termo foi encontrado,
    juntamente com um trecho explicativo.
    """
    cleaned = clean_text(term)

    matches = []

    for source, text in source_map.items():
        if cleaned and cleaned in text:
            weight = source_weights.get(
                source,
                DEFAULT_SOURCE_WEIGHT
            )

            matches.append({
                "source": source,
                "weight": weight,
                "snippet": extract_snippet(
                    text,
                    term
                )
            })

    if not matches:
        return {
            "source": None,
            "weight": DEFAULT_SOURCE_WEIGHT,
            "snippet": ""
        }

    matches.sort(
        key=lambda item: item["weight"],
        reverse=True
    )

    return matches[0]



def soft_saturation(raw_score, saturation):
    """
    Saturação suave:
        final = saturation * raw / (raw + saturation)

    Mantém diferenças entre scores altos sem permitir crescimento ilimitado.
    """
    if raw_score <= 0:
        return 0.0

    return round(
        saturation
        * raw_score
        / (raw_score + saturation),
        2
    )


def global_match_strength(details):
    """
    Classifica a força global da dimensão com base no melhor
    match efetivamente aceito.

    Ordem:
        exact > strong > medium > weak > none
    """
    levels = {
        item.get("level")
        for item in details
    }

    if "exact" in levels:
        return "exact"

    if "strong" in levels:
        return "strong"

    if "medium" in levels:
        return "medium"

    if "weak" in levels:
        return "weak"

    return "none"


def evaluate_weighted_terms(
    haystack,
    expansion,
    source_map=None,
    source_weights=None
):
    """
    Score semântico ponderado por:
    - força do termo (exact/strong/medium/weak)
    - origem do metadado (hc_code, hc_keyword, i_code etc.)
    - supressão de sobreposição de termos
    """

    source_map = source_map or {}
    source_weights = source_weights or {}

    concept = clean_text(
        expansion.get("concept")
    )

    candidates = []

    if concept and concept in haystack:
        source_info = best_source_and_snippet(
            expansion["concept"],
            source_map,
            source_weights
        )

        base_points = WEIGHTS["exact"]

        weighted_points = round(
            base_points
            * source_info["weight"],
            2
        )

        candidates.append({
            "term": expansion["concept"],
            "cleaned": concept,
            "level": "exact",
            "base_points": base_points,
            "source_weight": source_info["weight"],
            "points": weighted_points,
            "source": source_info["source"],
            "snippet": source_info["snippet"],
        })

    seen = set()

    for level in (
        "strong",
        "medium",
        "weak"
    ):
        for term in expansion.get(
            level,
            []
        ):
            cleaned = clean_text(term)

            if (
                not cleaned
                or cleaned in seen
            ):
                continue

            seen.add(cleaned)

            if (
                concept
                and cleaned == concept
            ):
                continue

            if cleaned in haystack:
                source_info = best_source_and_snippet(
                    term,
                    source_map,
                    source_weights
                )

                base_points = WEIGHTS[level]

                weighted_points = round(
                    base_points
                    * source_info["weight"],
                    2
                )

                candidates.append({
                    "term": term,
                    "cleaned": cleaned,
                    "level": level,
                    "base_points": base_points,
                    "source_weight": source_info["weight"],
                    "points": weighted_points,
                    "source": source_info["source"],
                    "snippet": source_info["snippet"],
                })

    candidates.sort(
        key=lambda item: (
            item["points"],
            len(item["cleaned"])
        ),
        reverse=True
    )

    accepted = []

    for candidate in candidates:
        c = candidate["cleaned"]

        overlapping = False

        for previous in accepted:
            p = previous["cleaned"]

            if (
                c in p
                or p in c
            ):
                overlapping = True
                break

        if overlapping:
            continue

        accepted.append(candidate)

    score = round(
        sum(
            item["points"]
            for item in accepted
        ),
        2
    )

    strong_match = any(
        item["level"] in (
            "exact",
            "strong"
        )
        for item in accepted
    )

    details = []

    for item in accepted:
        details.append({
            "term": item["term"],
            "level": item["level"],
            "base_points": item["base_points"],
            "source_weight": item["source_weight"],
            "points": item["points"],
            "source": item["source"],
            "snippet": item["snippet"],
        })

    return {
        "score": score,
        "strong_match": strong_match,
        "global_strength": global_match_strength(
            details
        ),
        "details": details,
    }


# ============================================================
# MATCH + SCORE
# ============================================================


def title_relevance_bonus(
    trial,
    filters,
    expansions,
    age_intent
):
    """
    Usa o título apenas como sinal de ranking.
    Nunca elimina registros.
    """
    title_text = build_title_text(
        trial
    )

    bonus = 0.0
    details = []

    condition = filters.get(
        "condition"
    )

    if condition:
        matched = False

        for level in (
            "strong",
            "medium",
            "weak"
        ):
            for term in expansions[
                "condition"
            ].get(level, []):
                if clean_text(term) in title_text:
                    matched = True
                    break
            if matched:
                break

        if (
            not matched
            and clean_text(condition)
            in title_text
        ):
            matched = True

        if matched:
            bonus += TITLE_BONUS[
                "condition"
            ]

            details.append({
                "filter": "title_condition_match",
                "points": TITLE_BONUS[
                    "condition"
                ],
            })

    intervention = filters.get(
        "intervention"
    )

    if intervention:
        matched = False

        for level in (
            "strong",
            "medium",
            "weak"
        ):
            for term in expansions[
                "intervention"
            ].get(level, []):
                if clean_text(term) in title_text:
                    matched = True
                    break
            if matched:
                break

        if (
            not matched
            and clean_text(intervention)
            in title_text
        ):
            matched = True

        if matched:
            bonus += TITLE_BONUS[
                "intervention"
            ]

            details.append({
                "filter": "title_intervention_match",
                "points": TITLE_BONUS[
                    "intervention"
                ],
            })

    if (
        age_intent
        == "older_adult"
    ):
        older_terms = (
            "older adult",
            "older adults",
            "elderly",
            "aged",
            "older people",
        )

        if any(
            term in title_text
            for term in older_terms
        ):
            bonus += TITLE_BONUS[
                "older_adult"
            ]

            details.append({
                "filter": "title_older_adult_match",
                "points": TITLE_BONUS[
                    "older_adult"
                ],
            })

    return bonus, details


def evaluate_trial(
    trial,
    filters,
    expansions,
    age_intent=None
):
    score = 0

    explanation = {
        "condition": [],
        "intervention": [],
        "structured": [],
    }

    condition_requested = bool(
        filters.get("condition")
    )

    intervention_requested = bool(
        filters.get("intervention")
    )

    condition_eval = None
    intervention_eval = None

    # --------------------------------------------------------
    # CONDIÇÃO
    # --------------------------------------------------------
    if condition_requested:
        condition_text = build_condition_text(
            trial
        )

        condition_sources = source_text_map_condition(
            trial
        )

        condition_eval = evaluate_weighted_terms(
            condition_text,
            expansions["condition"],
            source_map=condition_sources,
            source_weights=SOURCE_WEIGHTS_CONDITION
        )

        if condition_eval["score"] <= 0:
            return False, 0, explanation

        raw_condition_dimension = round(
            condition_eval["score"] * 3,
            2
        )

        condition_dimension = soft_saturation(
            raw_condition_dimension,
            SATURATION_CONDITION
        )

        score += condition_dimension

        explanation["condition"] = (
            condition_eval["details"]
        )

        explanation["structured"].append({
            "filter": "condition_dimension",
            "raw_points": raw_condition_dimension,
            "points": condition_dimension,
            "saturation": SATURATION_CONDITION,
            "strength": condition_eval[
                "global_strength"
            ],
        })

    # --------------------------------------------------------
    # INTERVENÇÃO
    # --------------------------------------------------------
    if intervention_requested:
        intervention_text = build_intervention_text(
            trial
        )

        intervention_sources = source_text_map_intervention(
            trial
        )

        intervention_eval = evaluate_weighted_terms(
            intervention_text,
            expansions["intervention"],
            source_map=intervention_sources,
            source_weights=SOURCE_WEIGHTS_INTERVENTION
        )

        if intervention_eval["score"] <= 0:
            return False, 0, explanation

        raw_intervention_dimension = round(
            intervention_eval["score"] * 3,
            2
        )

        intervention_dimension = soft_saturation(
            raw_intervention_dimension,
            SATURATION_INTERVENTION
        )

        score += intervention_dimension

        explanation["intervention"] = (
            intervention_eval["details"]
        )

        explanation["structured"].append({
            "filter": "intervention_dimension",
            "raw_points": raw_intervention_dimension,
            "points": intervention_dimension,
            "saturation": SATURATION_INTERVENTION,
            "strength": intervention_eval[
                "global_strength"
            ],
        })

    # --------------------------------------------------------
    # REGRA DE QUALIDADE
    # --------------------------------------------------------
    # Se usuário pediu condição + intervenção,
    # exigimos pelo menos um match forte em condição.
    if (
        condition_requested
        and intervention_requested
    ):
        if not condition_eval["strong_match"]:
            return False, 0, explanation

    # --------------------------------------------------------
    # TÍTULO
    # --------------------------------------------------------
    wanted_title = filters.get("title")

    if wanted_title:
        title_text = build_title_text(
            trial
        )

        if clean_text(
            wanted_title
        ) not in title_text:
            return False, 0, explanation

        score += 10

        explanation["structured"].append({
            "filter": "title",
            "points": 10,
        })

    # --------------------------------------------------------
    # RECRUTAMENTO
    # --------------------------------------------------------
    wanted_status = filters.get(
        "recruitment_status"
    )

    if wanted_status:
        status = safe_dict(
            trial.get("recruitment_status")
        )

        label = clean_text(
            status.get("label")
        )

        aliases = {
            "recruiting": [
                "recruiting"
            ],
            "not-yet-recruiting": [
                "not yet recruiting",
                "not-yet-recruiting",
            ],
            "active-not-recruiting": [
                "active not recruiting",
                "active-not-recruiting",
            ],
            "completed": [
                "completed",
                "recruitment completed",
                "data analysis completed",
            ],
            "suspended": [
                "suspended"
            ],
            "withdrawn": [
                "withdrawn"
            ],
            "terminated": [
                "terminated"
            ],
        }

        allowed = [
            clean_text(x)
            for x in aliases.get(
                wanted_status,
                [wanted_status]
            )
        ]

        if label not in allowed:
            return False, 0, explanation

        score += 5

        explanation["structured"].append({
            "filter": "recruitment_status",
            "points": 5,
        })

    # --------------------------------------------------------
    # FASE
    # --------------------------------------------------------
    wanted_phase = filters.get("phase")

    if wanted_phase:
        phase = safe_dict(
            trial.get("phase")
        )

        phase_label = clean_text(
            phase.get("label")
        )

        if phase_label != clean_text(
            wanted_phase
        ):
            return False, 0, explanation

        score += 5

        explanation["structured"].append({
            "filter": "phase",
            "points": 5,
        })

    # --------------------------------------------------------
    # SEXO
    # --------------------------------------------------------
    wanted_gender = filters.get("gender")

    if wanted_gender:
        current = clean_text(
            trial.get("gender")
        )

        aliases = {
            "all": [
                "-",
                "both",
                "all"
            ],
            "male": [
                "m",
                "male"
            ],
            "female": [
                "f",
                "female"
            ],
        }

        allowed = [
            clean_text(x)
            for x in aliases.get(
                wanted_gender,
                [wanted_gender]
            )
        ]

        if current not in allowed:
            return False, 0, explanation

        score += 4

        explanation["structured"].append({
            "filter": "gender",
            "points": 4,
        })

    # --------------------------------------------------------
    # IDADE
    # --------------------------------------------------------
    trial_min = age_to_years(
        trial.get("agemin_value"),
        trial.get("agemin_unit")
    )

    trial_max = age_to_years(
        trial.get("agemax_value"),
        trial.get("agemax_unit")
    )

    requested_min = filters.get(
        "age_min_years"
    )

    requested_max = filters.get(
        "age_max_years"
    )

    if requested_min is not None:
        requested_min = float(
            requested_min
        )

        raw_min = numeric_value(
            trial.get("agemin_value")
        )

        raw_max = numeric_value(
            trial.get("agemax_value")
        )

        # 0-0 ou idade totalmente ausente não é evidência suficiente
        # para satisfazer um filtro etário explícito.
        if (
            (raw_min is None or raw_min <= 0)
            and (raw_max is None or raw_max <= 0)
        ):
            return False, 0, explanation

        # Se existe máximo real, deve alcançar a idade solicitada.
        if (
            raw_max is not None
            and raw_max > 0
            and trial_max is not None
            and trial_max < requested_min
        ):
            return False, 0, explanation

        # Quando máximo=0 é usado como "sem limite superior",
        # só aceitamos isso se houver mínimo válido.
        if (
            raw_max is not None
            and raw_max <= 0
            and (
                raw_min is None
                or raw_min <= 0
            )
        ):
            return False, 0, explanation

        score += 3

        explanation["structured"].append({
            "filter": "age_overlap_min",
            "points": 3,
        })

        # Para "older adults"/"elderly", diferenciamos
        # mero overlap de um ensaio realmente voltado à população idosa.
        if age_intent == "older_adult":
            if (
                trial_min is not None
                and raw_min is not None
                and raw_min > 0
                and trial_min >= requested_min
            ):
                score += 10

                explanation["structured"].append({
                    "filter": "older_adult_population_match",
                    "points": 10,
                })
            else:
                score -= 5

                explanation["structured"].append({
                    "filter": "older_adult_overlap_only",
                    "points": -5,
                })

        else:
            if (
                trial_min is not None
                and raw_min is not None
                and raw_min > 0
                and trial_min >= requested_min
            ):
                score += 8

                explanation["structured"].append({
                    "filter": "age_population_match",
                    "points": 8,
                })

    if requested_max is not None:
        requested_max = float(
            requested_max
        )

        if (
            trial_min is not None
            and trial_min > requested_max
        ):
            return False, 0, explanation

        score += 3

        explanation["structured"].append({
            "filter": "age_overlap_max",
            "points": 3,
        })

    title_bonus, title_details = (
        title_relevance_bonus(
            trial,
            filters,
            expansions,
            age_intent
        )
    )

    if title_bonus:
        score += title_bonus
        explanation[
            "structured"
        ].extend(
            title_details
        )

    score = round(
        score,
        2
    )

    explanation["global_strength"] = {
        "condition": (
            condition_eval["global_strength"]
            if condition_eval
            else "none"
        ),
        "intervention": (
            intervention_eval["global_strength"]
            if intervention_eval
            else "none"
        ),
    }

    return True, score, explanation


# ============================================================
# BUSCA
# ============================================================

def search_database(
    filters,
    expansions,
    age_intent=None
):
    conn = mysql.connector.connect(
        **MYSQL_CONFIG
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT serialized
        FROM fossil_fossil
        WHERE is_most_recent = 1
          AND content_type_id = 24
    """)

    results = []
    total_examined = 0
    invalid_json = 0

    for (serialized,) in cursor:
        total_examined += 1

        try:
            trial = json.loads(
                serialized
            )
        except Exception:
            invalid_json += 1
            continue

        if (
            trial.get("__model__")
            != "ClinicalTrial"
        ):
            continue

        matched, score, explanation = (
            evaluate_trial(
                trial,
                filters,
                expansions,
                age_intent=age_intent
            )
        )

        if not matched:
            continue

        status = safe_dict(
            trial.get("recruitment_status")
        )

        phase = safe_dict(
            trial.get("phase")
        )

        results.append({
            "score": score,
            "condition_strength": (
                explanation
                .get("global_strength", {})
                .get("condition", "none")
            ),
            "intervention_strength": (
                explanation
                .get("global_strength", {})
                .get("intervention", "none")
            ),
            "explanation": explanation,
            "trial_id": trial.get("trial_id"),
            "public_title": trial.get("public_title"),
            "health_condition": trial.get("hc_freetext"),
            "recruitment_status": status.get("label"),
            "phase": phase.get("label"),
            "gender": trial.get("gender"),
            "age_min_value": trial.get("agemin_value"),
            "age_min_unit": trial.get("agemin_unit"),
            "age_max_value": trial.get("agemax_value"),
            "age_max_unit": trial.get("agemax_unit"),
            "date_registration": trial.get("date_registration"),
        })

    cursor.close()
    conn.close()

    results.sort(
        key=lambda item: (
            item["score"],
            item.get("date_registration") or ""
        ),
        reverse=True
    )

    return (
        results,
        total_examined,
        invalid_json
    )


def split_by_relative_threshold(
    results,
    threshold_ratio,
    intervention_requested=False
):
    """
    Divide resultados em principais e relacionados.

    Resultado principal exige:
    1. score >= threshold relativo;
    2. se a consulta pediu intervenção, força global da intervenção
       precisa ser exact ou strong.

    Também contabiliza por que cada resultado foi enviado para
    "relacionados":
    - score abaixo do threshold;
    - força de intervenção insuficiente;
    - ambos.
    """
    stats = {
        "below_threshold_only": 0,
        "weak_intervention_only": 0,
        "both": 0,
    }

    if not results:
        return [], [], 0, stats

    best_score = results[0]["score"]

    threshold_score = round(
        best_score * threshold_ratio,
        2
    )

    primary = []
    related = []

    for item in results:
        passes_score = (
            item["score"]
            >= threshold_score
        )

        passes_intervention_strength = True

        if intervention_requested:
            passes_intervention_strength = (
                item.get(
                    "intervention_strength"
                )
                in (
                    "exact",
                    "strong"
                )
            )

        if (
            passes_score
            and passes_intervention_strength
        ):
            primary.append(item)
            continue

        reason_score = not passes_score
        reason_intervention = (
            intervention_requested
            and not passes_intervention_strength
        )

        if (
            reason_score
            and reason_intervention
        ):
            stats["both"] += 1

        elif reason_score:
            stats[
                "below_threshold_only"
            ] += 1

        elif reason_intervention:
            stats[
                "weak_intervention_only"
            ] += 1

        related.append(item)

    return (
        primary,
        related,
        threshold_score,
        stats
    )


# ============================================================
# SAÍDA
# ============================================================

def format_age(value, unit):
    if value is None:
        return "-"
    return f"{value}{unit or ''}"


def print_explanation(explanation):
    print("Motivos do score:")

    for item in explanation["condition"]:
        print(
            f"  condição: "
            f"{item['term']} "
            f"[{item['level']}] "
            f"+{item['points']} "
            f"(base={item['base_points']}, "
            f"origem={item.get('source') or 'desconhecida'}, "
            f"peso_origem={item['source_weight']})"
        )

        if item.get("snippet"):
            print(
                f"    trecho: "
                f"{item['snippet']}"
            )

    for item in explanation["intervention"]:
        print(
            f"  intervenção: "
            f"{item['term']} "
            f"[{item['level']}] "
            f"+{item['points']} "
            f"(base={item['base_points']}, "
            f"origem={item.get('source') or 'desconhecida'}, "
            f"peso_origem={item['source_weight']})"
        )

        if item.get("snippet"):
            print(
                f"    trecho: "
                f"{item['snippet']}"
            )

    for item in explanation["structured"]:
        if item["filter"] in (
            "condition_dimension",
            "intervention_dimension"
        ):
            print(
                f"  dimensão: "
                f"{item['filter']} "
                f"raw={item.get('raw_points', item['points'])} "
                f"saturado=+{item['points']} "
                f"(S={item.get('saturation')}, "
                f"força={item.get('strength', 'none')})"
            )

        else:
            points = item["points"]

            sign = (
                "+"
                if points >= 0
                else ""
            )

            print(
                f"  filtro: "
                f"{item['filter']} "
                f"{sign}{points}"
            )


def print_trial(
    i,
    trial,
    explain
):
    print("=" * 70)

    print(
        f"{i}. "
        f"{trial['trial_id'] or ''}"
        f"  [score={trial['score']}]"
    )

    print(
        trial["public_title"]
        or ""
    )

    print(
        "Condição: "
        f"{trial['health_condition'] or ''}"
    )

    print(
        "Recrutamento: "
        f"{trial['recruitment_status'] or ''}"
    )

    print(
        "Fase: "
        f"{trial['phase'] or ''}"
    )

    print(
        "Sexo: "
        f"{trial['gender'] or ''}"
    )

    print(
        "Idade: "
        f"{format_age(trial['age_min_value'], trial['age_min_unit'])}"
        f" - "
        f"{format_age(trial['age_max_value'], trial['age_max_unit'])}"
    )

    print(
        "Registro: "
        f"{trial['date_registration'] or ''}"
    )

    print(
        "Força semântica: "
        f"condição={trial.get('condition_strength', 'none')} | "
        f"intervenção={trial.get('intervention_strength', 'none')}"
    )

    if explain:
        print_explanation(
            trial["explanation"]
        )


def print_results(
    results,
    total_examined,
    invalid_json,
    limit,
    explain,
    threshold_ratio,
    intervention_requested
):
    (
        primary,
        related,
        threshold_score,
        related_stats
    ) = split_by_relative_threshold(
        results,
        threshold_ratio,
        intervention_requested=(
            intervention_requested
        )
    )

    print()
    print(
        f"Registros examinados: "
        f"{total_examined}"
    )

    print(
        f"JSON inválidos: "
        f"{invalid_json}"
    )

    print(
        f"Resultados encontrados: "
        f"{len(results)}"
    )

    if results:
        print(
            f"Melhor score: "
            f"{results[0]['score']:.2f}"
        )

        print(
            f"Limiar principal "
            f"({threshold_ratio:.0%}): "
            f"{threshold_score:.2f}"
        )

    print(
        f"Resultados principais: "
        f"{len(primary)}"
    )

    print(
        f"Resultados relacionados: "
        f"{len(related)}"
    )

    if intervention_requested:
        print(
            "Regra de principal: "
            "intervenção exact/strong"
        )

    print(
        "Motivos para classificação "
        "como relacionado:"
    )

    print(
        "  somente score abaixo do limiar: "
        f"{related_stats['below_threshold_only']}"
    )

    print(
        "  somente força de intervenção insuficiente: "
        f"{related_stats['weak_intervention_only']}"
    )

    print(
        "  ambos: "
        f"{related_stats['both']}"
    )

    print()

    print(
        "### RESULTADOS PRINCIPAIS ###"
    )

    print()

    for i, trial in enumerate(
        primary[:limit],
        start=1
    ):
        print_trial(
            i,
            trial,
            explain
        )

    if related:
        print()
        print(
            "### OUTROS RESULTADOS RELACIONADOS ###"
        )

        print()

        related_limit = max(
            0,
            limit - min(
                len(primary),
                limit
            )
        )

        if related_limit > 0:
            for j, trial in enumerate(
                related[:related_limit],
                start=1
            ):
                print_trial(
                    j,
                    trial,
                    explain
                )
        else:
            print(
                f"{len(related)} resultados "
                f"relacionados adicionais não "
                f"exibidos. Use um --limit maior "
                f"para visualizá-los."
            )


# ============================================================
# ARGUMENTOS
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Busca inteligente experimental "
            "do ReBEC - v12"
        )
    )

    parser.add_argument(
        "query",
        nargs="+"
    )

    parser.add_argument(
        "--debug",
        action="store_true"
    )

    parser.add_argument(
        "--explain",
        action="store_true",
        help=(
            "mostra a composição do "
            "score de cada resultado"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=30
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help=(
            "fração do melhor score usada "
            "para separar resultados principais "
            "dos relacionados (padrão: 0.70)"
        )
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    query = " ".join(
        args.query
    ).strip()

    print()
    print("Consulta:")
    print(query)

    print()
    print("Interpretando com a IA...")

    try:
        llm_filters = ask_llm(
            query,
            debug=args.debug
        )

        explicit_filters = (
            explicit_filters_from_query(
                query
            )
        )

        filters = merge_filters(
            llm_filters,
            explicit_filters
        )

    except Exception as exc:
        logger.exception(
            "Erro ao interpretar consulta. "
            "query=%r",
            query
        )

        print()
        print("ERRO:")
        print(exc)
        sys.exit(2)

    if not has_any_filter(filters):
        print()
        print(
            "BUSCA INTERROMPIDA: "
            "nenhum filtro foi identificado."
        )
        sys.exit(6)

    age_intent = detect_age_intent(
        query
    )

    expansions = (
        build_semantic_expansions(
            filters
        )
    )

    print()
    print("Filtros finais:")

    print(
        json.dumps(
            filters,
            indent=2,
            ensure_ascii=False
        )
    )

    if args.debug:
        print()
        print(
            "Expansões semânticas ponderadas:"
        )

        print(
            json.dumps(
                expansions,
                indent=2,
                ensure_ascii=False
            )
        )

        print()
        print(
            "Intenção etária:"
        )
        print(
            age_intent
        )

        print()
        print(
            "Parâmetros de saturação:"
        )
        print(
            json.dumps(
                {
                    "condition_saturation":
                        SATURATION_CONDITION,
                    "intervention_saturation":
                        SATURATION_INTERVENTION,
                    "threshold_default":
                        args.threshold
                },
                indent=2,
                ensure_ascii=False
            )
        )

    print()
    print(
        "Consultando fossil_fossil..."
    )

    try:
        (
            results,
            total_examined,
            invalid_json
        ) = search_database(
            filters,
            expansions,
            age_intent=age_intent
        )

    except mysql.connector.Error as exc:
        logger.exception(
            "Erro MySQL."
        )

        print()
        print("ERRO MySQL:")
        print(exc)
        sys.exit(5)

    print_results(
        results,
        total_examined,
        invalid_json,
        limit=args.limit,
        explain=args.explain,
        threshold_ratio=args.threshold,
        intervention_requested=bool(
            filters.get("intervention")
        )
    )


if __name__ == "__main__":
    main()

