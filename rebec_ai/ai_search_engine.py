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

from .settings import MYSQL_CONFIG, LLM_URL
from .trial_rules import recruitment_freshness


# ============================================================
# CONFIGURAÇÃO
# ============================================================

PROMPT_FILE = Path(__file__).with_name("rebec_system_prompt.txt")
LOG_FILE = Path(__file__).with_name("rebec_ai_search.log")
SEARCH_PROMPT_VERSION = "fastapi-search-v3-2026-09-08"

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
    "cancer": {
        "strong": [
            "cancer",
            "malignant neoplasm",
            "malignant neoplasms",
            "carcinoma",
            "carcinomas",
            "malignancy",
            "malignancies",
        ],
        "medium": [
            "neoplasm",
            "neoplasms",
            "tumor",
            "tumors",
            "tumour",
            "tumours",
        ],
        "weak": [
            "oncology",
            "oncologic",
            "oncological",
        ],
    },

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
            "functional exercises",
            "balance training",
            "balance exercises",
            "therapeutic exercise",
            "therapeutic exercises",
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


# ============================================================
# TRADUÇÃO DE APRESENTAÇÃO + CACHE MYSQL
# ============================================================

TRANSLATABLE_RESULT_FIELDS = (
    "public_title",
    "health_condition",
)

TRANSLATION_LANGUAGE_NAMES = {
    "pt": "Portuguese (Brazil)",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
}

TRANSLATION_BATCH_SIZE = 8


# Mude este valor sempre que alterar o prompt/modelo/regras de tradução.
# Ele entra no hash do cache e invalida traduções antigas sem precisar
# apagar a tabela.
TRANSLATION_VERSION = "pt-br-v2"


RECRUITMENT_STATUS_TRANSLATIONS = {
    "pt": {
        "recruiting": "Recrutando",
        "not yet recruiting": "Ainda não recrutando",
        "recruitment completed": "Recrutamento concluído",
        "data analysis completed": "Análise de dados concluída",
        "terminated": "Encerrado",
        "suspended": "Suspenso",
        "withdrawn": "Retirado",
        "other": "Outro",
    },
    "es": {
        "recruiting": "Reclutando",
        "not yet recruiting": "Aún no está reclutando",
        "recruitment completed": "Reclutamiento completado",
        "data analysis completed": "Análisis de datos completado",
        "terminated": "Terminado",
        "suspended": "Suspendido",
        "withdrawn": "Retirado",
        "other": "Otro",
    },
    "fr": {
        "recruiting": "Recrutement en cours",
        "not yet recruiting": "Pas encore en recrutement",
        "recruitment completed": "Recrutement terminé",
        "data analysis completed": "Analyse des données terminée",
        "terminated": "Arrêté",
        "suspended": "Suspendu",
        "withdrawn": "Retiré",
        "other": "Autre",
    },
}


def translate_recruitment_status_for_display(
    value,
    language
):
    if not value:
        return value

    mapping = RECRUITMENT_STATUS_TRANSLATIONS.get(
        language,
        {}
    )

    key = clean_text(value)

    return mapping.get(
        key,
        value
    )

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

    null_like = {
        "",
        "none",
        "null",
        "undefined",
        "n/a",
        "na",
        "-",
    }

    for field in normalized:
        value = filters.get(field)

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.lower() in null_like:
                value = None
            else:
                value = stripped

        normalized[field] = value

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



# ============================================================
# ICTRP v2 — contexto semântico da intervenção
# ============================================================

NEGATION_PATTERNS = [
    r"\bnot\b",
    r"\bno\b",
    r"\bwithout\b",
    r"\bnever\b",
    r"\bwill\s+not\b",
    r"\bdoes\s+not\b",
    r"\bdo\s+not\b",
    r"\bdid\s+not\b",
    r"\bcannot\b",
    r"\bcan't\b",
    r"\bwon't\b",
    r"\bn[aã]o\b",
    r"\bsem\b",
    r"\bnunca\b",
    r"\bsin\b",
    r"\bsans\b",
    r"\bne\b.{0,40}\bpas\b",
]

INCIDENTAL_PATTERNS = [
    # Contextos claramente de hábito / histórico / covariável
    r"\blife habits?\b",
    r"\blifestyle habits?\b",
    r"\bmedical history\b",
    r"\bhistory of previous diseases?\b",
    r"\bsmoking\b.{0,80}\balcohol\b",
    r"\balcohol\b.{0,80}\bfeeding\b",
    r"\bfeeding\b.{0,80}\bphysical exercise\b",

    # Questionários ou instrumentos de atividade física
    r"\bphysical activity questionnaire\b",
    r"\binternational physical activity questionnaire\b",
    r"\bipaq\b",
]

CONTEXT_MULTIPLIER = {
    "direct": 1.00,
    "contextual": 1.00,
    "incidental": 0.25,
    "negated": 0.00,
}


def classify_intervention_context(
    text,
    term,
    source_name
):
    """
    Classifica evidência de intervenção:
      direct      -> código/keyword estruturado
      contextual  -> intervenção narrativa normal
      incidental  -> hábito/histórico/questionário
      negated     -> ocorrência local negada

    Regras deliberadamente conservadoras:
    - negation precisa estar próxima e antes do termo;
    - incidental só é aplicado em contextos bastante explícitos;
    - palavras genéricas como "evaluation" ou "assessment" não bastam.
    """
    if source_name in (
        "i_code",
        "intervention_keyword"
    ):
        return "direct"

    ntext = clean_text(text)
    nterm = clean_text(term)

    if not ntext or not nterm:
        return "contextual"

    # Pode haver várias ocorrências do mesmo termo.
    # Avaliamos todas e damos preferência a uma ocorrência válida.
    positions = []
    start_at = 0

    while True:
        pos = ntext.find(
            nterm,
            start_at
        )

        if pos < 0:
            break

        positions.append(pos)
        start_at = pos + max(
            1,
            len(nterm)
        )

    if not positions:
        return "contextual"

    contexts = []

    for pos in positions:
        before = ntext[
            max(0, pos - 130):pos
        ]

        around_start = max(
            0,
            pos - 170
        )

        around = ntext[
            around_start:
            min(
                len(ntext),
                pos + len(nterm) + 170
            )
        ]

        local_before = before[-90:]

        is_negated = False

        for pattern in NEGATION_PATTERNS:
            for match in re.finditer(
                pattern,
                local_before
            ):
                distance = (
                    len(local_before)
                    - match.end()
                )

                if 0 <= distance <= 75:
                    is_negated = True
                    break

            if is_negated:
                break

        if is_negated:
            contexts.append(
                "negated"
            )
            continue

        is_incidental = any(
            re.search(
                pattern,
                around
            )
            for pattern in INCIDENTAL_PATTERNS
        )

        if is_incidental:
            contexts.append(
                "incidental"
            )
        else:
            contexts.append(
                "contextual"
            )

    # Se qualquer ocorrência for uma intervenção normal,
    # o termo é considerado válido.
    if "contextual" in contexts:
        return "contextual"

    if "incidental" in contexts:
        return "incidental"

    if "negated" in contexts:
        return "negated"

    return "contextual"


def context_adjusted_level(
    level,
    context
):
    if context == "negated":
        return "none"

    if (
        context == "incidental"
        and level == "exact"
    ):
        return "medium"

    return level


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
                "source_text": text,
                "snippet": extract_snippet(
                    text,
                    term
                )
            })

    if not matches:
        return {
            "source": None,
            "weight": DEFAULT_SOURCE_WEIGHT,
            "source_text": "",
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
    source_weights=None,
    context_aware=False
):
    source_map = source_map or {}
    source_weights = source_weights or {}

    concept = clean_text(
        expansion.get("concept")
    )

    candidates = []

    def add_candidate(
        term,
        original_level,
        cleaned
    ):
        source_info = best_source_and_snippet(
            term,
            source_map,
            source_weights
        )

        context = "contextual"

        if context_aware:
            context = classify_intervention_context(
                source_info.get(
                    "source_text",
                    ""
                ),
                term,
                source_info.get(
                    "source"
                )
            )

        effective_level = (
            context_adjusted_level(
                original_level,
                context
            )
            if context_aware
            else original_level
        )

        base_points = WEIGHTS.get(
            effective_level,
            0
        )

        context_multiplier = (
            CONTEXT_MULTIPLIER.get(
                context,
                1.0
            )
            if context_aware
            else 1.0
        )

        weighted_points = round(
            base_points
            * source_info["weight"]
            * context_multiplier,
            2
        )

        candidates.append({
            "term": term,
            "cleaned": cleaned,
            "level": effective_level,
            "original_level":
                original_level,
            "context": context,
            "context_multiplier":
                context_multiplier,
            "base_points": base_points,
            "source_weight":
                source_info["weight"],
            "points": weighted_points,
            "source":
                source_info["source"],
            "snippet":
                source_info["snippet"],
        })

    if concept and concept in haystack:
        add_candidate(
            expansion["concept"],
            "exact",
            concept
        )

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
                add_candidate(
                    term,
                    level,
                    cleaned
                )

    scoring_candidates = [
        item
        for item in candidates
        if item["points"] > 0
        and item["level"] != "none"
    ]

    scoring_candidates.sort(
        key=lambda item: (
            item["points"],
            len(item["cleaned"])
        ),
        reverse=True
    )

    accepted = []

    for candidate in scoring_candidates:
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

    details = [
        {
            "term": item["term"],
            "level": item["level"],
            "original_level":
                item["original_level"],
            "context": item["context"],
            "context_multiplier":
                item["context_multiplier"],
            "base_points":
                item["base_points"],
            "source_weight":
                item["source_weight"],
            "points":
                item["points"],
            "source":
                item["source"],
            "snippet":
                item["snippet"],
        }
        for item in accepted
    ]

    context_evidence = []

    if context_aware:
        for item in candidates:
            if item["context"] in (
                "negated",
                "incidental"
            ):
                context_evidence.append({
                    "term":
                        item["term"],
                    "level":
                        item["original_level"],
                    "effective_level":
                        item["level"],
                    "context":
                        item["context"],
                    "points":
                        item["points"],
                    "source":
                        item["source"],
                    "snippet":
                        item["snippet"],
                })

    return {
        "score": score,
        "strong_match":
            strong_match,
        "global_strength":
            global_match_strength(
                details
            ),
        "details": details,
        "context_evidence":
            context_evidence,
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
            source_weights=SOURCE_WEIGHTS_INTERVENTION,
            context_aware=True
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

        explanation["intervention_context"] = (
            intervention_eval.get(
                "context_evidence",
                []
            )
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



def ensure_translation_cache_schema(conn):
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ictrp_translation_cache (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                trial_pk BIGINT UNSIGNED NOT NULL,
                language VARCHAR(16) NOT NULL,
                field_name VARCHAR(64) NOT NULL,
                source_hash CHAR(64) NOT NULL,
                translated_text LONGTEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_ictrp_translation_cache (
                    trial_pk,
                    language,
                    field_name,
                    source_hash
                ),
                KEY idx_ictrp_translation_lookup (
                    trial_pk,
                    language,
                    field_name
                )
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
            """
        )
        conn.commit()
    finally:
        cursor.close()


def _sha256_text(value):
    import hashlib

    value = "" if value is None else str(value)

    payload = (
        f"{TRANSLATION_VERSION}\n"
        f"{value}"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _translation_prompt(
    language,
    trial_id,
    public_title,
    health_condition
):
    language_name = (
        TRANSLATION_LANGUAGE_NAMES.get(
            language,
            language
        )
    )

    pt_br_rules = ""

    if language == "pt":
        pt_br_rules = """
Brazilian Portuguese terminology:
- postural balance -> equilíbrio postural
- balance disorder -> distúrbio do equilíbrio
- balance training -> treinamento de equilíbrio
- balance exercises -> exercícios de equilíbrio
- falls / accidental falls -> quedas / quedas acidentais
- fall risk / risk of falling -> risco de quedas
- fallers -> pessoas idosas com histórico de quedas
- elderly / older adults / aged -> idosos / idosas according to context
- exercise -> exercício
- physical exercise -> exercício físico
- exercise program -> programa de exercícios
- therapeutic exercise -> exercício terapêutico
- strength training -> treinamento de força
- resistance training -> treinamento resistido
- functional training -> treinamento funcional
- muscle strength -> força muscular
- mood -> humor
- nursing home -> instituição de longa permanência para idosos
- aging -> envelhecimento
- recruitment completed -> recrutamento concluído
- not yet recruiting -> ainda não recrutando
- recruiting -> recrutando

Never use Spanish or European-Portuguese forms such as:
- Fallas
- quedagens
- quedadas
- "adultos idosos"
""".strip()

    return f"""
Translate these two clinical-trial fields into {language_name}.

Rules:
- Use natural, fluent language suitable for a clinical-trial search interface.
- Preserve meaning faithfully.
- Do not summarize.
- Do not add explanations.
- Use standard medical terminology.
- Avoid literal word-for-word translation.
- Do not mix languages.
- Return ONLY one valid JSON object.
- Include BOTH keys even when one field is empty.

{pt_br_rules}

Required output:
{{
  "public_title": "...",
  "health_condition": "..."
}}

Trial ID: {trial_id}

public_title:
{public_title or ""}

health_condition:
{health_condition or ""}
""".strip()



def _cleanup_translation_text(
    text,
    language
):
    if text is None:
        return None

    value = str(text).strip()

    if language != "pt":
        return value

    replacements = [
        (r"\bFallas\b", "Quedas"),
        (r"\bfallas\b", "quedas"),
        (r"\bquedagens\b", "quedas"),
        (r"\bquedadas\b", "quedas"),
        (r"\bQuedagens\b", "Quedas"),
        (r"\bQuedadas\b", "Quedas"),
        (r"\badultos idosos\b", "idosos"),
        (r"\bAdultos idosos\b", "Idosos"),
        (r"\bda exercício\b", "do exercício"),
        (r"\bAção da idade\b", "Envelhecimento"),
        (r"\bação da idade\b", "envelhecimento"),
        (r"\bEvaluando\b", "Avaliação"),
        (r"\bevaluando\b", "avaliação"),
    ]

    for pattern, replacement in replacements:
        value = re.sub(
            pattern,
            replacement,
            value,
            flags=re.IGNORECASE
            if pattern.lower() == pattern
            else 0
        )

    return value


def _call_translation_llm(
    language,
    trial_id,
    public_title,
    health_condition,
    debug=False
):
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise multilingual "
                    "clinical-trial translator. "
                    "Return only valid JSON."
                )
            },
            {
                "role": "user",
                "content": _translation_prompt(
                    language,
                    trial_id,
                    public_title,
                    health_condition
                )
            }
        ],
        "temperature": 0,
        "max_tokens": 500,
        "chat_template_kwargs": {
            "enable_thinking": False
        }
    }

    response = requests.post(
        LLM_URL,
        json=payload,
        timeout=120
    )

    response.raise_for_status()

    content = (
        response.json()["choices"][0]
        ["message"]["content"]
    ).strip()

    if debug:
        print()
        print(
            "===== RESPOSTA BRUTA DA TRADUÇÃO ====="
        )
        print(content)
        print(
            "======================================="
        )
        print()

    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content
        )
        content = re.sub(
            r"\s*```$",
            "",
            content
        )

    parsed = json.loads(content)

    if not isinstance(parsed, dict):
        return {}

    return {
        "public_title":
            _cleanup_translation_text(
                parsed.get(
                    "public_title"
                ),
                language
            ),
        "health_condition":
            _cleanup_translation_text(
                parsed.get(
                    "health_condition"
                ),
                language
            ),
    }


def _get_cached_translation(
    conn,
    trial_pk,
    language,
    field_name,
    source_hash
):
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT translated_text
            FROM ictrp_translation_cache
            WHERE trial_pk = %s
              AND language = %s
              AND field_name = %s
              AND source_hash = %s
            LIMIT 1
            """,
            (
                trial_pk,
                language,
                field_name,
                source_hash,
            )
        )

        row = cursor.fetchone()

        return row[0] if row else None

    finally:
        cursor.close()


def _save_translation(
    conn,
    trial_pk,
    language,
    field_name,
    source_hash,
    translated_text
):
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO ictrp_translation_cache (
                trial_pk,
                language,
                field_name,
                source_hash,
                translated_text
            )
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                translated_text = VALUES(
                    translated_text
                ),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                trial_pk,
                language,
                field_name,
                source_hash,
                translated_text,
            )
        )
        conn.commit()
    finally:
        cursor.close()


def translate_results_for_display(
    results,
    language,
    limit=None,
    debug=False
):
    """
    Traduz apenas a camada de apresentação.

    Estratégia:
    - recruitment_status: dicionário determinístico;
    - public_title + health_condition:
      1 chamada ao LLM por trial quando faltarem no cache;
    - cache por trial/campo/idioma/hash.
    """
    if (
        not results
        or language in (
            None,
            "",
            "en"
        )
    ):
        return {
            "language": language or "en",
            "cache_hits": 0,
            "translated_now": 0,
            "requested_items": 0,
            "failed_items": 0,
            "llm_calls": 0,
        }

    display_results = (
        results[:limit]
        if limit
        else results
    )

    conn = mysql.connector.connect(
        **MYSQL_CONFIG
    )

    ensure_translation_cache_schema(
        conn
    )

    cache_hits = 0
    translated_now = 0
    requested_items = 0
    failed_items = 0
    llm_calls = 0

    try:
        for item in display_results:
            trial_pk = item.get(
                "trial_pk"
            )

            if trial_pk is None:
                continue

            # ----------------------------------------------
            # Status: sem LLM
            # ----------------------------------------------
            original_status = item.get(
                "recruitment_status"
            )

            if original_status:
                item[
                    "recruitment_status_original"
                ] = original_status

                item[
                    "recruitment_status"
                ] = (
                    translate_recruitment_status_for_display(
                        original_status,
                        language
                    )
                )

            # ----------------------------------------------
            # Título e condição
            # ----------------------------------------------
            missing = {}

            for field_name in (
                TRANSLATABLE_RESULT_FIELDS
            ):
                original = item.get(
                    field_name
                )

                if not original:
                    continue

                item[
                    f"{field_name}_original"
                ] = original

                source_hash = _sha256_text(
                    original
                )

                requested_items += 1

                cached = (
                    _get_cached_translation(
                        conn,
                        trial_pk,
                        language,
                        field_name,
                        source_hash,
                    )
                )

                if cached is not None:
                    item[field_name] = cached
                    cache_hits += 1
                    continue

                missing[field_name] = {
                    "original": original,
                    "source_hash":
                        source_hash,
                }

            if not missing:
                continue

            llm_calls += 1

            translated_map = {}

            try:
                translated_map = (
                    _call_translation_llm(
                        language,
                        item.get(
                            "trial_id"
                        ),
                        (
                            missing.get(
                                "public_title",
                                {}
                            ).get(
                                "original",
                                item.get(
                                    "public_title"
                                )
                            )
                        ),
                        (
                            missing.get(
                                "health_condition",
                                {}
                            ).get(
                                "original",
                                item.get(
                                    "health_condition"
                                )
                            )
                        ),
                        debug=debug
                    )
                )
            except Exception:
                logger.exception(
                    "Falha ao traduzir trial %s",
                    item.get(
                        "trial_id"
                    )
                )

            for field_name, meta in (
                missing.items()
            ):
                translated_text = (
                    translated_map.get(
                        field_name
                    )
                )

                if not translated_text:
                    failed_items += 1
                    continue

                item[field_name] = (
                    translated_text
                )

                _save_translation(
                    conn,
                    trial_pk,
                    language,
                    field_name,
                    meta["source_hash"],
                    translated_text,
                )

                translated_now += 1

    finally:
        conn.close()

    return {
        "language": language,
        "translation_version":
            TRANSLATION_VERSION,
        "cache_hits": cache_hits,
        "translated_now":
            translated_now,
        "requested_items":
            requested_items,
        "failed_items":
            failed_items,
        "llm_calls":
            llm_calls,
    }


def detect_query_language(query):
    """
    Telemetria simples. Não altera o filtro canônico.
    O Qwen continua convertendo a consulta para conceitos em inglês.
    """
    q = clean_text(query)

    if any(
        marker in q
        for marker in (
            "estudos",
            "ensaios",
            "idosos",
            "idosas",
            "mulheres",
            "homens",
            "recrutando",
            "câncer",
            "cancer",
        )
    ):
        return "pt"

    if any(
        marker in q
        for marker in (
            "ensayos",
            "adultos mayores",
            "mujeres",
            "reclutando",
        )
    ):
        return "es"

    if any(
        marker in q
        for marker in (
            "essais",
            "personnes âgées",
            "personnes agees",
            "femmes",
        )
    ):
        return "fr"

    return "en"


def _db_status_value(value):
    mapping = {
        "recruiting": "recruiting",
        "not-yet-recruiting": "not_yet_recruiting",
        "active-not-recruiting": "active_not_recruiting",
        "completed": "completed",
        "suspended": "suspended",
        "withdrawn": "withdrawn",
        "terminated": "terminated",
    }
    return mapping.get(value, value)


def _db_gender_value(value):
    mapping = {
        "all": "both",
        "male": "male",
        "female": "female",
    }
    return mapping.get(value, value)


def _semantic_terms(expansion):
    """
    Retorna todos os termos úteis para geração de candidatos.
    O ranking final continua sendo feito por evaluate_trial().
    """
    terms = []

    if not expansion:
        return terms

    concept = expansion.get("concept")
    if concept:
        terms.append(concept)

    for level in ("strong", "medium", "weak"):
        for item in expansion.get(level, []):
            if isinstance(item, dict):
                term = item.get("term")
            else:
                term = item

            if term:
                terms.append(term)

    seen = set()
    result = []

    for term in terms:
        normalized = clean_text(term)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def _like_group(column, terms, params):
    """
    Gera:
      (column LIKE %s OR column LIKE %s ...)
    """
    if not terms:
        return None

    clauses = []

    for term in terms:
        clauses.append(
            f"{column} LIKE %s"
        )
        params.append(
            f"%{clean_text(term)}%"
        )

    return "(" + " OR ".join(clauses) + ")"


def _load_multivalue_map(
    conn,
    table,
    value_column,
    trial_ids,
):
    result = {}

    if not trial_ids:
        return result

    placeholders = ",".join(
        ["%s"] * len(trial_ids)
    )

    cursor = conn.cursor()

    try:
        cursor.execute(
            f"""
            SELECT trial_pk, {value_column}
            FROM {table}
            WHERE trial_pk IN ({placeholders})
            """,
            trial_ids,
        )

        for trial_pk, value in cursor:
            if value is None:
                continue

            result.setdefault(
                int(trial_pk),
                []
            ).append(
                str(value)
            )

    finally:
        cursor.close()

    return result


def _build_candidate_sql(
    filters,
    expansions,
):
    """
    O MySQL faz a primeira redução do universo de busca.

    Filtros estruturados são aplicados diretamente por índices.
    Condição/intervenção/título/sponsor/country são usados como
    pré-seleção lexical. O score final continua em Python para
    manter comparabilidade com teste_busca_ia_v12.py.
    """
    where = []
    params = []

    condition_terms = _semantic_terms(
        expansions.get("condition")
    )

    intervention_terms = _semantic_terms(
        expansions.get("intervention")
    )

    condition_clause = _like_group(
        "s.condition_text",
        condition_terms,
        params,
    )

    if filters.get("condition") and condition_clause:
        where.append(condition_clause)

    intervention_clause = _like_group(
        "s.intervention_text",
        intervention_terms,
        params,
    )

    if filters.get("intervention") and intervention_clause:
        where.append(intervention_clause)

    if filters.get("title"):
        where.append(
            "s.title_text LIKE %s"
        )
        params.append(
            f"%{clean_text(filters['title'])}%"
        )

    if filters.get("recruitment_status"):
        where.append(
            "s.recruitment_status = %s"
        )
        params.append(
            _db_status_value(
                filters["recruitment_status"]
            )
        )

    if filters.get("phase"):
        where.append(
            "s.phase = %s"
        )
        params.append(
            str(filters["phase"])
        )

    if filters.get("gender"):
        where.append(
            "s.gender = %s"
        )
        params.append(
            _db_gender_value(
                filters["gender"]
            )
        )

    if filters.get("age_min_years") is not None:
        # O trial deve alcançar a idade mínima solicitada.
        where.append(
            """
            (
                s.age_max_years IS NULL
                OR s.age_max_years = 0
                OR s.age_max_years >= %s
            )
            """
        )
        params.append(
            float(filters["age_min_years"])
        )

    if filters.get("age_max_years") is not None:
        # O mínimo do trial não pode estar acima do máximo solicitado.
        where.append(
            """
            (
                s.age_min_years IS NULL
                OR s.age_min_years <= %s
            )
            """
        )
        params.append(
            float(filters["age_max_years"])
        )

    if filters.get("country"):
        country = filters["country"]

        if isinstance(country, list):
            group = []
            for item in country:
                group.append(
                    "s.country_text LIKE %s"
                )
                params.append(
                    f"%{clean_text(item)}%"
                )
            if group:
                where.append(
                    "(" + " OR ".join(group) + ")"
                )
        else:
            where.append(
                "s.country_text LIKE %s"
            )
            params.append(
                f"%{clean_text(country)}%"
            )

    if filters.get("sponsor"):
        where.append(
            "s.sponsor_text LIKE %s"
        )
        params.append(
            f"%{clean_text(filters['sponsor'])}%"
        )

    if filters.get("study_type"):
        wanted = clean_text(
            filters["study_type"]
        )

        aliases = {
            "interventional": "interventional",
            "intervention": "interventional",
            "observational": "observational",
        }

        where.append(
            "s.study_type = %s"
        )
        params.append(
            aliases.get(wanted, wanted)
        )

    if filters.get("registration_date_from"):
        where.append(
            "s.date_registration >= %s"
        )
        params.append(
            filters["registration_date_from"]
        )

    if filters.get("registration_date_to"):
        where.append(
            "s.date_registration <= %s"
        )
        params.append(
            filters["registration_date_to"]
        )

    sql = """
        SELECT
            t.id,
            t.trial_id,
            t.utrn,
            t.public_title,
            t.scientific_title,
            t.acronym,
            t.scientific_acronym,
            t.hc_freetext,
            t.i_freetext,

            t.recruitment_status_raw,
            t.recruitment_status,
            t.phase_raw,
            t.phase,
            t.gender_raw,
            t.gender,

            t.age_min_years,
            t.age_max_years,
            t.date_registration,
            t.date_enrolment,
            t.date_enrolment_raw,
            t.type_enrolment,

            t.primary_sponsor,
            t.study_type_raw,
            t.study_type,
            t.url,

            r.registry_name,
            r.registry_country

        FROM ictrp_trial_search s

        INNER JOIN ictrp_trial t
            ON t.id = s.trial_pk

        INNER JOIN ictrp_registry r
            ON r.id = t.registry_id
    """

    if where:
        sql += (
            "\nWHERE "
            + "\n  AND ".join(where)
        )

    return sql, params


def search_database(
    filters,
    expansions,
    age_intent=None
):
    """
    Busca na nova base ICTRP.

    Estratégia híbrida:
    1. MySQL pré-seleciona candidatos;
    2. carregamos somente os campos estruturados necessários;
    3. evaluate_trial() reutiliza o mesmo ranking da v12.

    Assim podemos comparar o novo armazenamento com fossil_fossil
    sem trocar simultaneamente toda a lógica de relevância.
    """
    import time

    started = time.perf_counter()

    conn = mysql.connector.connect(
        **MYSQL_CONFIG
    )

    cursor = conn.cursor(
        dictionary=True
    )

    sql, params = _build_candidate_sql(
        filters,
        expansions,
    )

    query_started = time.perf_counter()

    cursor.execute(
        sql,
        params,
    )

    rows = cursor.fetchall()

    mysql_seconds = (
        time.perf_counter()
        - query_started
    )

    total_examined = len(rows)

    trial_pks = [
        int(row["id"])
        for row in rows
    ]

    # Carrega estruturas 1:N somente para os candidatos.
    hc_codes = _load_multivalue_map(
        conn,
        "ictrp_trial_condition_code",
        "condition_code",
        trial_pks,
    )

    hc_keywords = _load_multivalue_map(
        conn,
        "ictrp_trial_condition_keyword",
        "keyword",
        trial_pks,
    )

    i_codes = _load_multivalue_map(
        conn,
        "ictrp_trial_intervention_code",
        "intervention_code",
        trial_pks,
    )

    i_keywords = _load_multivalue_map(
        conn,
        "ictrp_trial_intervention_keyword",
        "keyword",
        trial_pks,
    )

    results = []

    ranking_started = time.perf_counter()

    for row in rows:
        trial_pk = int(
            row["id"]
        )

        # Adaptador ICTRP DB -> estrutura que evaluate_trial()
        # já conhece da versão fossil_fossil.
        trial = {
            "__model__": "ClinicalTrial",

            "trial_id": row["trial_id"],
            "utrn": row["utrn"],

            "public_title": row["public_title"],
            "scientific_title": row["scientific_title"],
            "acronym": row["acronym"],
            "scientific_acronym":
                row["scientific_acronym"],

            "hc_freetext": row["hc_freetext"],
            "i_freetext": row["i_freetext"],

            "hc_code": [
                {"text": x}
                for x in hc_codes.get(
                    trial_pk,
                    []
                )
            ],

            "hc_keyword": [
                {"text": x}
                for x in hc_keywords.get(
                    trial_pk,
                    []
                )
            ],

            "i_code": [
                {"text": x}
                for x in i_codes.get(
                    trial_pk,
                    []
                )
            ],

            "intervention_keyword": [
                {"text": x}
                for x in i_keywords.get(
                    trial_pk,
                    []
                )
            ],

            "translations": [],

            # Usamos raw para manter compatibilidade com aliases
            # já tratados por evaluate_trial().
            "recruitment_status": {
                "label": (
                    row["recruitment_status_raw"]
                    or row["recruitment_status"]
                    or ""
                )
            },

            "phase": {
                "label": (
                    row["phase_raw"]
                    or row["phase"]
                    or ""
                )
            },

            "gender": (
                row["gender_raw"]
                or row["gender"]
                or ""
            ),

            # A idade já foi normalizada em anos na carga.
            "agemin_value": row["age_min_years"],
            "agemin_unit": "Y",

            "agemax_value": row["age_max_years"],
            "agemax_unit": "Y",

            "date_registration": (
                row["date_registration"].isoformat()
                if row["date_registration"]
                else None
            ),

            "date_enrolment": (
                row["date_enrolment"].isoformat()
                if row["date_enrolment"]
                else None
            ),

            "date_enrolment_raw":
                row["date_enrolment_raw"],

            "type_enrolment":
                row["type_enrolment"],

            "primary_sponsor":
                row["primary_sponsor"],

            "url":
                row["url"],

            "study_type":
                row["study_type_raw"]
                or row["study_type"],

            "registry_name":
                row["registry_name"],

            "registry_country":
                row["registry_country"],
        }

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

        # Registra no explain quais filtros foram aplicados
        # previamente pelo banco.
        if filters.get("country"):
            explanation[
                "structured"
            ].append({
                "filter": "country_db_prefilter",
                "points": 0,
            })

        if filters.get("sponsor"):
            explanation[
                "structured"
            ].append({
                "filter": "sponsor_db_prefilter",
                "points": 0,
            })

        if filters.get("study_type"):
            explanation[
                "structured"
            ].append({
                "filter": "study_type_db_prefilter",
                "points": 0,
            })

        if (
            filters.get("registration_date_from")
            or filters.get("registration_date_to")
        ):
            explanation[
                "structured"
            ].append({
                "filter": "registration_date_db_prefilter",
                "points": 0,
            })

        results.append({
            "trial_pk": trial_pk,
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

            "trial_id":
                trial.get("trial_id"),

            "public_title":
                trial.get("public_title"),

            "health_condition":
                trial.get("hc_freetext"),

            "recruitment_status": (
                trial
                .get("recruitment_status", {})
                .get("label")
            ),

            "phase": (
                trial
                .get("phase", {})
                .get("label")
            ),

            "gender":
                trial.get("gender"),

            "age_min_value":
                trial.get("agemin_value"),

            "age_min_unit":
                trial.get("agemin_unit"),

            "age_max_value":
                trial.get("agemax_value"),

            "age_max_unit":
                trial.get("agemax_unit"),

            "date_registration":
                trial.get("date_registration"),

            "date_enrolment":
                trial.get("date_enrolment"),

            "date_enrolment_raw":
                trial.get("date_enrolment_raw"),

            "type_enrolment":
                trial.get("type_enrolment"),

            "registry_name":
                trial.get("registry_name"),

            "registration_url":
                trial.get("url"),

            "recruitment_freshness":
                recruitment_freshness(
                    trial.get("date_enrolment"),
                    trial.get("type_enrolment"),
                    (
                        row["recruitment_status"]
                        or row["recruitment_status_raw"]
                    ),
                ),
        })

    ranking_seconds = (
        time.perf_counter()
        - ranking_started
    )

    cursor.close()
    conn.close()

    results.sort(
        key=lambda item: (
            item["score"],
            item.get("date_registration") or ""
        ),
        reverse=True
    )

    total_seconds = (
        time.perf_counter()
        - started
    )

    db_stats = {
        "candidates": total_examined,
        "mysql_seconds": round(
            mysql_seconds,
            4
        ),
        "ranking_seconds": round(
            ranking_seconds,
            4
        ),
        "total_search_seconds": round(
            total_seconds,
            4
        ),
    }

    # Mantemos o terceiro retorno por compatibilidade com
    # print_results(). Nesta base não há JSON para desserializar.
    invalid_json = 0

    return (
        results,
        total_examined,
        invalid_json,
        db_stats
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

    for item in explanation.get(
        "intervention_context",
        []
    ):
        print(
            f"  intervenção contexto: "
            f"{item['term']} "
            f"[{item['level']}/"
            f"{item['context']}] "
            f"-> efetivo="
            f"{item['effective_level']}"
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
    if (
        trial.get("public_title_original")
        and trial.get("public_title_original")
        != trial.get("public_title")
    ):
        print(
            "Título original: "
            f"{trial.get('public_title_original')}"
        )

    print(
        "Condição: "
        f"{trial['health_condition'] or ''}"
    )
    if (
        trial.get("health_condition_original")
        and trial.get("health_condition_original")
        != trial.get("health_condition")
    ):
        print(
            "Condição original: "
            f"{trial.get('health_condition_original')}"
        )

    print(
        "Recrutamento: "
        f"{trial['recruitment_status'] or ''}"
    )
    if (
        trial.get("recruitment_status_original")
        and trial.get("recruitment_status_original")
        != trial.get("recruitment_status")
    ):
        print(
            "Recrutamento original: "
            f"{trial.get('recruitment_status_original')}"
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
        f"Registros inválidos na leitura: "
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
            "Busca inteligente experimental ICTRP "
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
        "--no-translate",
        action="store_true",
        help=(
            "não traduz os resultados para "
            "o idioma da consulta"
        )
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

    query_language = detect_query_language(
        query
    )

    print(
        "Idioma detectado: "
        f"{query_language}"
    )

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
        "Consultando base ICTRP normalizada..."
    )
    print(
        "Fonte: ictrp_trial_search + tabelas normalizadas | motor ICTRP + tradução PT-BR versionada + cache"
    )

    try:
        (
            results,
            total_examined,
            invalid_json,
            db_stats
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

    print()
    print("Estatísticas da base ICTRP:")
    print(
        json.dumps(
            db_stats,
            indent=2,
            ensure_ascii=False
        )
    )

    translation_stats = {
        "language": query_language,
        "translation_version":
            TRANSLATION_VERSION,
        "cache_hits": 0,
        "translated_now": 0,
        "requested_items": 0,
        "failed_items": 0,
        "llm_calls": 0,
    }

    if not args.no_translate:
        try:
            translation_stats = (
                translate_results_for_display(
                    results,
                    query_language,
                    limit=args.limit,
                    debug=args.debug,
                )
            )
        except Exception as exc:
            logger.exception(
                "Falha ao traduzir resultados."
            )
            print()
            print(
                "AVISO: tradução indisponível; "
                "resultados originais serão exibidos."
            )
            print(exc)

    print()
    print("Estatísticas de tradução:")
    print(
        json.dumps(
            translation_stats,
            indent=2,
            ensure_ascii=False
        )
    )

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

# ============================================================
# API SERVICE ADAPTER
# ============================================================

def _api_override_filters(base_filters, structured_filters):
    """Structured UI fields always win over LLM interpretation.

    Also sanitizes textual nulls occasionally emitted by small LLMs
    (for example ``"None"`` for an unused date field).
    """
    from datetime import date

    merged = dict(base_filters or empty_filter_dict())

    for key in empty_filter_dict().keys():
        if key not in structured_filters:
            continue

        value = structured_filters.get(key)

        if value in (None, "", [], {}):
            continue

        merged[key] = value

    # Small local models sometimes return strings instead of JSON null.
    textual_nulls = {
        "", "none", "null", "undefined", "nil", "n/a", "na"
    }
    for key, value in list(merged.items()):
        if isinstance(value, str) and value.strip().lower() in textual_nulls:
            merged[key] = None

    # Normalize numeric age values when they came from JSON/UI.
    for key in ("age_min_years", "age_max_years"):
        if merged.get(key) not in (None, ""):
            try:
                merged[key] = float(merged[key])
            except (TypeError, ValueError):
                merged[key] = None

    # Only valid ISO dates are allowed to reach MySQL DATE comparisons.
    # Invalid or textual-null model output is treated as an unused filter.
    for key in ("registration_date_from", "registration_date_to"):
        value = merged.get(key)
        if value in (None, ""):
            merged[key] = None
            continue
        try:
            normalized = str(value).strip()
            date.fromisoformat(normalized)
            merged[key] = normalized
        except (TypeError, ValueError):
            merged[key] = None

    return merged



def _model_query_with_structured_filters(
    query,
    structured_filters,
):
    """
    Build the best possible natural-language representation of the
    advanced-search selections and send that combined intent to the LLM.

    Structured fields still override the model afterward, so the user
    selection remains authoritative.
    """
    structured_filters = structured_filters or {}

    labels = [
        ("condition", "Condition / disease"),
        ("intervention", "Intervention"),
        ("title", "Title contains"),
        ("sponsor", "Sponsor"),
        ("study_type", "Study type"),
        ("recruitment_status", "Recruitment status"),
        ("phase", "Phase"),
        ("gender", "Sex / gender"),
        ("age_min_years", "Minimum age in years"),
        ("age_max_years", "Maximum age in years"),
        ("country", "Country"),
        ("registration_date_from", "Registration date from"),
        ("registration_date_to", "Registration date to"),
    ]

    selected = []

    for key, label in labels:
        value = structured_filters.get(key)

        if value in (None, "", [], {}):
            continue

        selected.append(
            f"- {label}: {value}"
        )

    free_text = (query or "").strip()

    if not selected:
        return free_text

    if not free_text:
        free_text = (
            "Find clinical trials matching the advanced filters "
            "selected by the user."
        )

    return (
        free_text
        + "\n\n"
        + "Advanced search filters explicitly selected by the user:\n"
        + "\n".join(selected)
        + "\n\n"
        + "Interpret the complete intent. "
        + "The advanced filter values are explicit user constraints. "
        + "Do NOT invent any additional disease, intervention, "
        + "recruitment status, phase, sex, age, country, sponsor, "
        + "study type, title, or date restriction that was not present "
        + "in the user's free-text query or in the selected advanced "
        + "filters. If only one advanced filter is selected, every "
        + "unrelated filter must be null."
    )

def run_search_api(
    query="",
    structured_filters=None,
    language=None,
    page=1,
    page_size=20,
    threshold_ratio=0.70,
    debug=False,
    translate=True,
):
    """
    FastAPI-friendly search entry point.

    No argparse and no dependency on terminal output. When debug=True,
    stdout generated by the experimental engine is captured and returned
    as a single copyable text block.
    """
    import contextlib
    import io
    import time

    structured_filters = structured_filters or {}
    query = (query or "").strip()

    model_query = _model_query_with_structured_filters(
        query,
        structured_filters,
    )

    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))

    detected_language = (
        detect_query_language(query)
        if query
        else "en"
    )
    display_language = language or detected_language

    debug_buffer = io.StringIO()
    started = time.perf_counter()

    capture = (
        contextlib.redirect_stdout(debug_buffer)
        if debug
        else contextlib.nullcontext()
    )

    with capture:
        if model_query:
            llm_filters = ask_llm(
                model_query,
                debug=debug,
            )
        else:
            llm_filters = empty_filter_dict()

        # Explicit parsing must inspect only what the user actually typed,
        # never the synthetic text created from advanced filters.
        explicit_filters = (
            explicit_filters_from_query(query)
            if query
            else empty_filter_dict()
        )

        if query:
            # Free-text search:
            # use the LLM interpretation + deterministic explicit parser,
            # then let advanced fields override them.
            filters = merge_filters(
                llm_filters,
                explicit_filters,
            )
            llm_filters_applied = True
        else:
            # Advanced-search-only:
            # the LLM still receives the composed query for interpretation,
            # logging and future features, but it is NOT allowed to create
            # extra search constraints.
            filters = empty_filter_dict()
            llm_filters_applied = False

        # Advanced fields are always authoritative.
        filters = _api_override_filters(
            filters,
            structured_filters,
        )

        if not has_any_filter(filters):
            raise ValueError(
                "Nenhum critério de busca foi informado. "
                "Use o campo livre ou ao menos um filtro avançado."
            )

        age_intent = (
            detect_age_intent(query)
            if query
            else None
        )
        expansions = build_semantic_expansions(filters)

        (
            results,
            total_examined,
            invalid_json,
            db_stats,
        ) = search_database(
            filters,
            expansions,
            age_intent=age_intent,
        )

        (
            primary,
            related,
            threshold_score,
            split_stats,
        ) = split_by_relative_threshold(
            results,
            threshold_ratio,
            intervention_requested=bool(
                filters.get("intervention")
            ),
        )

        ordered = []
        for item in primary:
            x = dict(item)
            x["result_class"] = "primary"
            ordered.append(x)

        for item in related:
            x = dict(item)
            x["result_class"] = "related"
            ordered.append(x)

        total = len(ordered)
        offset = (page - 1) * page_size
        page_results = ordered[offset:offset + page_size]

        translation_stats = {
            "language": display_language,
            "translation_version": TRANSLATION_VERSION,
            "cache_hits": 0,
            "translated_now": 0,
            "requested_items": 0,
            "failed_items": 0,
            "llm_calls": 0,
        }

        if translate and display_language != "en":
            translation_stats = translate_results_for_display(
                page_results,
                display_language,
                limit=None,
                debug=debug,
            )

    # The terminal engine stores Decimal/date-like values in a few places.
    # JSON-safe conversion is done by round-tripping through default=str.
    safe_results = json.loads(
        json.dumps(
            page_results,
            ensure_ascii=False,
            default=str,
        )
    )

    elapsed = round(time.perf_counter() - started, 4)

    debug_payload = {
        "enabled": bool(debug),
        "text": "",
    }

    if debug:
        structured_debug = {
            "query": query,
            "model_input_query": model_query,
            "detected_language": detected_language,
            "display_language": display_language,
            "llm_filters": llm_filters,
            "llm_filters_applied":
                llm_filters_applied,
            "explicit_filters": explicit_filters,
            "structured_filters": structured_filters,
            "final_filters": filters,
            "filter_provenance": {
                "free_text_present": bool(query),
                "advanced_filters_authoritative": True,
                "llm_used_for_search":
                    llm_filters_applied,
                "rule": (
                    "advanced-only searches use only structured filters; "
                    "free-text searches use LLM interpretation and then "
                    "advanced filters override matching fields"
                ),
            },
            "semantic_expansions": expansions,
            "age_intent": age_intent,
            "db_stats": db_stats,
            "total_examined": total_examined,
            "invalid_json": invalid_json,
            "best_score": results[0]["score"] if results else 0,
            "threshold_ratio": threshold_ratio,
            "threshold_score": threshold_score,
            "primary_count": len(primary),
            "related_count": len(related),
            "split_stats": split_stats,
            "translation_stats": translation_stats,
            "request_seconds": elapsed,
        }

        debug_payload["text"] = (
            "===== ReBEC AI SEARCH DEBUG =====\n"
            + json.dumps(
                structured_debug,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
            + "\n\n===== RAW MODEL / TRANSLATION OUTPUT =====\n"
            + debug_buffer.getvalue()
        )

    return {
        "query": query,
        "search_prompt_version": SEARCH_PROMPT_VERSION,
        "search_prompt_tokens_hint": "full rebec_system_prompt.txt",
        "detected_language": detected_language,
        "language": display_language,
        "filters": filters,
        "page": page,
        "page_size": page_size,
        "total_results": total,
        "primary_count": len(primary),
        "related_count": len(related),
        "threshold_score": threshold_score,
        "db_stats": db_stats,
        "translation_stats": translation_stats,
        "results": safe_results,

        "_all_results_internal": json.loads(
            json.dumps(
                ordered,
                ensure_ascii=False,
                default=str,
            )
        ),

        "all_trial_ids": [
            item.get("trial_id")
            for item in ordered
            if item.get("trial_id")
        ],
        "debug": debug_payload,
    }
