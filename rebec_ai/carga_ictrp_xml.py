#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ICTRP XML -> MySQL canonical loader
===================================

Objetivo
--------
Importar XMLs no formato ICTRP para uma estrutura relacional normalizada,
adequada para busca e reutilizável entre registros de ensaios clínicos.

Características
---------------
- Usa MYSQL_CONFIG do mesmo config.py usado pelo projeto.
- Cria as tabelas apenas se elas ainda não existirem.
- Faz INSERT de ensaios novos.
- Faz UPDATE apenas quando o conteúdo do ensaio mudou.
- Ignora registros cujo conteúdo não mudou.
- Usa SHA-256 por ensaio para detectar alterações.
- Mantém os valores "raw" recebidos do registro.
- Mantém também alguns valores normalizados para busca.
- Importa estruturas 1:N em tabelas filhas.
- Mantém uma tabela desnormalizada ictrp_trial_search para busca rápida.
- Registra cada execução em ictrp_import_run.
- Processa XML grande via iterparse, sem carregar o arquivo inteiro em memória.

Uso
---
    python carga_ictrp_xml.py RBR-ictrp-ALL.xml

ou:

    python carga_ictrp_xml.py RBR-ictrp-ALL.xml --verbose

Dependências
------------
    pip install mysql-connector-python

config.py
---------
    MYSQL_CONFIG = {
        "host": "127.0.0.1",
        "user": "...",
        "password": "...",
        "database": "...",
    }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import mysql.connector
from mysql.connector import Error

from .settings import MYSQL_CONFIG


# ============================================================
# Helpers gerais
# ============================================================

def clean_text(value: Optional[str]) -> str:
    """Limpa espaços, mas preserva maiúsculas/minúsculas e acentos."""
    if value is None:
        return ""
    return " ".join(str(value).replace("\x00", " ").split())


def normalize_search_text(value: Optional[str]) -> str:
    """
    Normalização leve para busca lexical:
    - lowercase
    - remove acentos
    - normaliza whitespace
    """
    value = clean_text(value).lower()

    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        c for c in normalized
        if not unicodedata.combining(c)
    )
    return " ".join(normalized.split())


def element_text(parent: Optional[ET.Element], tag: str) -> str:
    if parent is None:
        return ""
    elem = parent.find(tag)
    if elem is None:
        return ""
    return clean_text(elem.text)


def child_texts(parent: Optional[ET.Element], tag: str) -> List[str]:
    if parent is None:
        return []
    values = []
    for elem in parent.findall(tag):
        text = clean_text(elem.text)
        if text:
            values.append(text)
    return values


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(data: Dict[str, Any]) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_date(value: str) -> Optional[str]:
    """
    Tenta normalizar datas do ICTRP para YYYY-MM-DD.
    Mantemos também o valor raw em coluna própria.
    """
    value = clean_text(value)
    if not value:
        return None

    formats = (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass

    return None


def parse_age_years(value: str) -> Optional[float]:
    """
    Converte idades ICTRP para anos.

    Exemplos:
      18   -> 18
      18Y  -> 18
      6M   -> 0.5
      4W   -> ~0.077
      30D  -> ~0.082

    0 e 0Y são mantidos como 0.0.
    """
    value = clean_text(value).upper()

    if not value:
        return None

    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([YMWD]?)\s*$", value)

    if not m:
        return None

    number = float(m.group(1))
    unit = m.group(2) or "Y"

    if unit == "Y":
        return number
    if unit == "M":
        return number / 12.0
    if unit == "W":
        return number / 52.1429
    if unit == "D":
        return number / 365.25

    return None


def normalize_gender(value: str) -> Optional[str]:
    v = normalize_search_text(value)

    if not v:
        return None

    female = {"f", "female", "feminino", "feminine"}
    male = {"m", "male", "masculino", "masculine"}
    both = {
        "-", "both", "all", "both sexes", "todos",
        "ambos", "male and female", "female and male"
    }

    if v in female:
        return "female"
    if v in male:
        return "male"
    if v in both:
        return "both"

    return "other"


def normalize_study_type(value: str) -> Optional[str]:
    v = normalize_search_text(value)

    if not v:
        return None

    if "intervention" in v or "interventional" in v:
        return "interventional"

    if "observational" in v or "observacional" in v:
        return "observational"

    return "other"


def normalize_phase(value: str) -> Optional[str]:
    """
    Mantém valores reconhecidos em formato canônico.
    Valores estranhos ficam em 'other', enquanto phase_raw
    preserva exatamente o que veio do registro.
    """
    v = normalize_search_text(value).replace("phase", "").replace("fase", "").strip()

    if not v:
        return None

    replacements = {
        "i": "1",
        "ii": "2",
        "iii": "3",
        "iv": "4",
        "n/a": "n/a",
        "na": "n/a",
        "not applicable": "n/a",
    }

    v = replacements.get(v, v)

    allowed = {
        "0", "1", "2", "3", "4",
        "1-2", "2-3", "3-4",
        "n/a",
    }

    if v in allowed:
        return v

    return "other"


def normalize_recruitment_status(value: str) -> Optional[str]:
    v = normalize_search_text(value)

    if not v:
        return None

    mapping = {
        "not yet recruiting": "not_yet_recruiting",
        "pending": "not_yet_recruiting",
        "recruiting": "recruiting",
        "recruitment completed": "completed",
        "completed": "completed",
        "data analysis completed": "data_analysis_completed",
        "suspended": "suspended",
        "terminated": "terminated",
        "withdrawn": "withdrawn",
        "active not recruiting": "active_not_recruiting",
        "active, not recruiting": "active_not_recruiting",
        "other": "other",
        "array": "other",
    }

    return mapping.get(v, "other")


def join_search(values: Iterable[str]) -> str:
    return " ".join(
        normalize_search_text(v)
        for v in values
        if clean_text(v)
    ).strip()


# ============================================================
# Extração do XML
# ============================================================

def parse_trial_element(trial: ET.Element) -> Dict[str, Any]:
    main = trial.find("main")
    criteria = trial.find("criteria")

    data: Dict[str, Any] = {
        "main": {
            "trial_id": element_text(main, "trial_id"),
            "utrn": element_text(main, "utrn"),
            "reg_name": element_text(main, "reg_name"),
            "reg_country": element_text(main, "reg_country"),

            "date_registration": element_text(main, "date_registration"),
            "primary_sponsor": element_text(main, "primary_sponsor"),

            "public_title": element_text(main, "public_title"),
            "acronym": element_text(main, "acronym"),
            "scientific_title": element_text(main, "scientific_title"),
            "scientific_acronym": element_text(main, "scientific_acronym"),

            "date_enrolment": element_text(main, "date_enrolment"),
            "type_enrolment": element_text(main, "type_enrolment"),
            "target_size": element_text(main, "target_size"),

            "recruitment_status": element_text(main, "recruitment_status"),
            "url": element_text(main, "url"),

            "study_type": element_text(main, "study_type"),
            "study_design": element_text(main, "study_design"),
            "phase": element_text(main, "phase"),

            "hc_freetext": element_text(main, "hc_freetext"),
            "i_freetext": element_text(main, "i_freetext"),

            "results_actual_enrolment": element_text(main, "results_actual_enrolment"),
            "results_date_completed": element_text(main, "results_date_completed"),
            "results_url_link": element_text(main, "results_url_link"),
            "results_summary": element_text(main, "results_summary"),
            "results_date_posted": element_text(main, "results_date_posted"),
            "results_date_first_publication": element_text(main, "results_date_first_publication"),
            "results_baseline_char": element_text(main, "results_baseline_char"),
            "results_participant_flow": element_text(main, "results_participant_flow"),
            "results_adverse_events": element_text(main, "results_adverse_events"),
            "results_outcome_measures": element_text(main, "results_outcome_measures"),
            "results_url_protocol": element_text(main, "results_url_protocol"),
            "results_IPD_plan": element_text(main, "results_IPD_plan"),
            "results_IPD_description": element_text(main, "results_IPD_description"),
        },

        "criteria": {
            "inclusion_criteria": element_text(criteria, "inclusion_criteria"),
            "agemin": element_text(criteria, "agemin"),
            "agemax": element_text(criteria, "agemax"),
            "gender": element_text(criteria, "gender"),
            "exclusion_criteria": element_text(criteria, "exclusion_criteria"),
        },

        "contacts": [],
        "countries": [],
        "condition_codes": [],
        "condition_keywords": [],
        "intervention_codes": [],
        "intervention_keywords": [],
        "primary_outcomes": [],
        "secondary_outcomes": [],
        "secondary_sponsors": [],
        "secondary_ids": [],
        "source_support": [],
        "ethics_reviews": [],
    }

    # contatos
    contacts = trial.find("contacts")
    if contacts is not None:
        for contact in contacts.findall("contact"):
            data["contacts"].append({
                "type": element_text(contact, "type"),
                "firstname": element_text(contact, "firstname"),
                "middlename": element_text(contact, "middlename"),
                "lastname": element_text(contact, "lastname"),
                "address": element_text(contact, "address"),
                "city": element_text(contact, "city"),
                "country": element_text(contact, "country1"),
                "zip": element_text(contact, "zip"),
                "telephone": element_text(contact, "telephone"),
                "email": element_text(contact, "email"),
                "affiliation": element_text(contact, "affiliation"),
            })

    countries = trial.find("countries")
    if countries is not None:
        data["countries"] = child_texts(countries, "country2")

    hc_codes = trial.find("health_condition_code")
    if hc_codes is not None:
        data["condition_codes"] = child_texts(hc_codes, "hc_code")

    hc_keywords = trial.find("health_condition_keyword")
    if hc_keywords is not None:
        data["condition_keywords"] = child_texts(hc_keywords, "hc_keyword")

    i_codes = trial.find("intervention_code")
    if i_codes is not None:
        data["intervention_codes"] = child_texts(i_codes, "i_code")

    i_keywords = trial.find("intervention_keyword")
    if i_keywords is not None:
        data["intervention_keywords"] = child_texts(i_keywords, "i_keyword")

    primary = trial.find("primary_outcome")
    if primary is not None:
        data["primary_outcomes"] = child_texts(primary, "prim_outcome")

    secondary = trial.find("secondary_outcome")
    if secondary is not None:
        data["secondary_outcomes"] = child_texts(secondary, "sec_outcome")

    sponsors = trial.find("secondary_sponsor")
    if sponsors is not None:
        data["secondary_sponsors"] = child_texts(sponsors, "sponsor_name")

    sec_ids = trial.find("secondary_ids")
    if sec_ids is not None:
        for sec_id in sec_ids.findall("secondary_id"):
            data["secondary_ids"].append({
                "sec_id": element_text(sec_id, "sec_id"),
                "issuing_authority": element_text(sec_id, "issuing_authority"),
            })

    support = trial.find("source_support")
    if support is not None:
        data["source_support"] = child_texts(support, "source_name")

    ethics = trial.find("ethics_reviews")
    if ethics is not None:
        for review in ethics.findall("ethics_review"):
            data["ethics_reviews"].append({
                "status": element_text(review, "status"),
                "approval_date": element_text(review, "approval_date"),
                "contact_name": element_text(review, "contact_name"),
                "contact_address": element_text(review, "contact_address"),
                "contact_phone": element_text(review, "contact_phone"),
                "contact_email": element_text(review, "contact_email"),
            })

    return data


# ============================================================
# Schema MySQL
# ============================================================

DDL_STATEMENTS = [

"""
CREATE TABLE IF NOT EXISTS ictrp_import_run (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_file VARCHAR(512) NOT NULL,
    source_file_sha256 CHAR(64) NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',

    total_xml INT UNSIGNED NOT NULL DEFAULT 0,
    inserted_count INT UNSIGNED NOT NULL DEFAULT 0,
    updated_count INT UNSIGNED NOT NULL DEFAULT 0,
    unchanged_count INT UNSIGNED NOT NULL DEFAULT 0,
    error_count INT UNSIGNED NOT NULL DEFAULT 0,

    message TEXT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_import_started (started_at),
    KEY idx_ictrp_import_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_registry (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    registry_code VARCHAR(64) NOT NULL,
    registry_name VARCHAR(255) NOT NULL,
    registry_country VARCHAR(8) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_ictrp_registry_code (registry_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    registry_id BIGINT UNSIGNED NOT NULL,

    trial_id VARCHAR(128) NOT NULL,
    utrn VARCHAR(128) NULL,

    date_registration_raw VARCHAR(64) NULL,
    date_registration DATE NULL,

    primary_sponsor TEXT NULL,

    public_title LONGTEXT NULL,
    acronym TEXT NULL,
    scientific_title LONGTEXT NULL,
    scientific_acronym TEXT NULL,

    date_enrolment_raw VARCHAR(64) NULL,
    date_enrolment DATE NULL,
    type_enrolment VARCHAR(64) NULL,

    target_size_raw VARCHAR(64) NULL,
    target_size INT NULL,

    recruitment_status_raw VARCHAR(255) NULL,
    recruitment_status VARCHAR(64) NULL,

    url TEXT NULL,

    study_type_raw VARCHAR(255) NULL,
    study_type VARCHAR(64) NULL,

    study_design LONGTEXT NULL,

    phase_raw VARCHAR(255) NULL,
    phase VARCHAR(32) NULL,

    hc_freetext LONGTEXT NULL,
    i_freetext LONGTEXT NULL,

    inclusion_criteria LONGTEXT NULL,
    exclusion_criteria LONGTEXT NULL,

    age_min_raw VARCHAR(64) NULL,
    age_max_raw VARCHAR(64) NULL,
    age_min_years DECIMAL(10,4) NULL,
    age_max_years DECIMAL(10,4) NULL,

    gender_raw VARCHAR(255) NULL,
    gender VARCHAR(32) NULL,

    results_actual_enrolment LONGTEXT NULL,
    results_date_completed LONGTEXT NULL,
    results_url_link LONGTEXT NULL,
    results_summary LONGTEXT NULL,
    results_date_posted LONGTEXT NULL,
    results_date_first_publication LONGTEXT NULL,
    results_baseline_char LONGTEXT NULL,
    results_participant_flow LONGTEXT NULL,
    results_adverse_events LONGTEXT NULL,
    results_outcome_measures LONGTEXT NULL,
    results_url_protocol LONGTEXT NULL,
    results_ipd_plan LONGTEXT NULL,
    results_ipd_description LONGTEXT NULL,

    source_hash CHAR(64) NOT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uq_ictrp_trial_registry_trial (
        registry_id,
        trial_id
    ),

    KEY idx_ictrp_trial_trial_id (trial_id),
    KEY idx_ictrp_trial_utrn (utrn),
    KEY idx_ictrp_trial_registration (date_registration),
    KEY idx_ictrp_trial_phase (phase),
    KEY idx_ictrp_trial_recruitment (recruitment_status),
    KEY idx_ictrp_trial_study_type (study_type),
    KEY idx_ictrp_trial_gender (gender),
    KEY idx_ictrp_trial_age_min (age_min_years),
    KEY idx_ictrp_trial_age_max (age_max_years),

    CONSTRAINT fk_ictrp_trial_registry
      FOREIGN KEY (registry_id)
      REFERENCES ictrp_registry(id)
      ON DELETE RESTRICT
      ON UPDATE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",


"""
CREATE TABLE IF NOT EXISTS ictrp_trial_xml (
    trial_pk BIGINT UNSIGNED NOT NULL,
    source_hash CHAR(64) NOT NULL,
    trial_xml LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (trial_pk),
    KEY idx_ictrp_trial_xml_hash (source_hash),

    CONSTRAINT fk_ictrp_trial_xml_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE
      ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_contact (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,

    contact_type VARCHAR(64) NULL,
    firstname VARCHAR(255) NULL,
    middlename VARCHAR(255) NULL,
    lastname VARCHAR(255) NULL,
    address TEXT NULL,
    city VARCHAR(255) NULL,
    country_code VARCHAR(16) NULL,
    zip VARCHAR(64) NULL,
    telephone VARCHAR(128) NULL,
    email VARCHAR(320) NULL,
    affiliation TEXT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_contact_trial (trial_pk),
    KEY idx_ictrp_contact_type (contact_type),

    CONSTRAINT fk_ictrp_contact_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_country (
    trial_pk BIGINT UNSIGNED NOT NULL,
    country_code VARCHAR(16) NOT NULL,

    PRIMARY KEY (trial_pk, country_code),
    KEY idx_ictrp_country_code (country_code),

    CONSTRAINT fk_ictrp_country_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_condition_code (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    condition_code VARCHAR(255) NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_ictrp_condition_code (
        trial_pk,
        condition_code
    ),
    KEY idx_ictrp_condition_code_value (condition_code),

    CONSTRAINT fk_ictrp_condition_code_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_condition_keyword (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    keyword TEXT NOT NULL,
    keyword_normalized TEXT NOT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_condition_keyword_trial (trial_pk),

    CONSTRAINT fk_ictrp_condition_keyword_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_intervention_code (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    intervention_code VARCHAR(255) NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_ictrp_intervention_code (
        trial_pk,
        intervention_code
    ),
    KEY idx_ictrp_intervention_code_value (intervention_code),

    CONSTRAINT fk_ictrp_intervention_code_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_intervention_keyword (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    keyword TEXT NOT NULL,
    keyword_normalized TEXT NOT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_intervention_keyword_trial (trial_pk),

    CONSTRAINT fk_ictrp_intervention_keyword_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_primary_outcome (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    ordinal_no INT UNSIGNED NOT NULL,
    outcome_text LONGTEXT NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_ictrp_primary_outcome (
        trial_pk,
        ordinal_no
    ),

    CONSTRAINT fk_ictrp_primary_outcome_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_secondary_outcome (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    ordinal_no INT UNSIGNED NOT NULL,
    outcome_text LONGTEXT NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_ictrp_secondary_outcome (
        trial_pk,
        ordinal_no
    ),

    CONSTRAINT fk_ictrp_secondary_outcome_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_secondary_sponsor (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    sponsor_name TEXT NOT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_secondary_sponsor_trial (trial_pk),

    CONSTRAINT fk_ictrp_secondary_sponsor_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_secondary_id (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    secondary_id VARCHAR(255) NULL,
    issuing_authority TEXT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_secondary_id_trial (trial_pk),
    KEY idx_ictrp_secondary_id_value (secondary_id),

    CONSTRAINT fk_ictrp_secondary_id_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_source_support (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,
    source_name TEXT NOT NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_source_support_trial (trial_pk),

    CONSTRAINT fk_ictrp_source_support_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_ethics_review (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trial_pk BIGINT UNSIGNED NOT NULL,

    status VARCHAR(255) NULL,
    approval_date_raw VARCHAR(64) NULL,
    approval_date DATE NULL,

    contact_name TEXT NULL,
    contact_address TEXT NULL,
    contact_phone VARCHAR(128) NULL,
    contact_email VARCHAR(320) NULL,

    PRIMARY KEY (id),
    KEY idx_ictrp_ethics_trial (trial_pk),
    KEY idx_ictrp_ethics_status (status),

    CONSTRAINT fk_ictrp_ethics_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",

"""
CREATE TABLE IF NOT EXISTS ictrp_trial_search (
    trial_pk BIGINT UNSIGNED NOT NULL,
    registry_id BIGINT UNSIGNED NOT NULL,

    trial_id VARCHAR(128) NOT NULL,
    utrn VARCHAR(128) NULL,

    public_title LONGTEXT NULL,
    scientific_title LONGTEXT NULL,

    title_text LONGTEXT NULL,
    condition_text LONGTEXT NULL,
    intervention_text LONGTEXT NULL,
    eligibility_text LONGTEXT NULL,
    outcome_text LONGTEXT NULL,
    sponsor_text LONGTEXT NULL,
    country_text TEXT NULL,

    recruitment_status VARCHAR(64) NULL,
    study_type VARCHAR(64) NULL,
    phase VARCHAR(32) NULL,
    gender VARCHAR(32) NULL,
    age_min_years DECIMAL(10,4) NULL,
    age_max_years DECIMAL(10,4) NULL,
    date_registration DATE NULL,

    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
      ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (trial_pk),

    KEY idx_ictrp_search_registry (registry_id),
    KEY idx_ictrp_search_trial_id (trial_id),
    KEY idx_ictrp_search_utrn (utrn),
    KEY idx_ictrp_search_status (recruitment_status),
    KEY idx_ictrp_search_type (study_type),
    KEY idx_ictrp_search_phase (phase),
    KEY idx_ictrp_search_gender (gender),
    KEY idx_ictrp_search_age_min (age_min_years),
    KEY idx_ictrp_search_age_max (age_max_years),
    KEY idx_ictrp_search_registration (date_registration),

    FULLTEXT KEY ft_ictrp_search_title (
        title_text
    ),

    FULLTEXT KEY ft_ictrp_search_condition (
        condition_text
    ),

    FULLTEXT KEY ft_ictrp_search_intervention (
        intervention_text
    ),

    FULLTEXT KEY ft_ictrp_search_outcome (
        outcome_text
    ),

    CONSTRAINT fk_ictrp_search_trial
      FOREIGN KEY (trial_pk)
      REFERENCES ictrp_trial(id)
      ON DELETE CASCADE,

    CONSTRAINT fk_ictrp_search_registry
      FOREIGN KEY (registry_id)
      REFERENCES ictrp_registry(id)
      ON DELETE RESTRICT

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""",
]


CHILD_TABLES = [
    "ictrp_trial_contact",
    "ictrp_trial_country",
    "ictrp_trial_condition_code",
    "ictrp_trial_condition_keyword",
    "ictrp_trial_intervention_code",
    "ictrp_trial_intervention_keyword",
    "ictrp_trial_primary_outcome",
    "ictrp_trial_secondary_outcome",
    "ictrp_trial_secondary_sponsor",
    "ictrp_trial_secondary_id",
    "ictrp_trial_source_support",
    "ictrp_trial_ethics_review",
]


def create_schema(conn) -> None:
    cur = conn.cursor()
    try:
        for sql in DDL_STATEMENTS:
            cur.execute(sql)
        conn.commit()
    finally:
        cur.close()


def apply_schema_migrations(conn) -> None:
    """
    Aplica ajustes compatíveis também quando as tabelas já existem.

    CREATE TABLE IF NOT EXISTS não altera colunas existentes, portanto
    pequenas migrações necessárias ao importador ficam centralizadas aqui.
    """
    migrations = [
        """
        ALTER TABLE ictrp_trial
        MODIFY COLUMN acronym TEXT NULL
        """,
        """
        ALTER TABLE ictrp_trial
        MODIFY COLUMN scientific_acronym TEXT NULL
        """,
    ]

    cur = conn.cursor()
    try:
        for sql in migrations:
            cur.execute(sql)
        conn.commit()
    finally:
        cur.close()


# ============================================================
# Registry
# ============================================================

def registry_code(reg_name: str) -> str:
    code = normalize_search_text(reg_name)
    code = re.sub(r"[^a-z0-9]+", "_", code).strip("_")
    return (code or "unknown")[:64]


def get_or_create_registry(
    conn,
    reg_name: str,
    reg_country: str,
) -> int:
    reg_name = clean_text(reg_name) or "UNKNOWN"
    code = registry_code(reg_name)

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM ictrp_registry
            WHERE registry_code = %s
            """,
            (code,),
        )
        row = cur.fetchone()

        if row:
            registry_id = int(row[0])

            cur.execute(
                """
                UPDATE ictrp_registry
                SET
                    registry_name = %s,
                    registry_country = COALESCE(NULLIF(%s, ''), registry_country)
                WHERE id = %s
                """,
                (
                    reg_name,
                    clean_text(reg_country),
                    registry_id,
                ),
            )
            return registry_id

        cur.execute(
            """
            INSERT INTO ictrp_registry (
                registry_code,
                registry_name,
                registry_country
            )
            VALUES (%s, %s, NULLIF(%s, ''))
            """,
            (
                code,
                reg_name,
                clean_text(reg_country),
            ),
        )
        return int(cur.lastrowid)

    finally:
        cur.close()


# ============================================================
# Parent trial
# ============================================================

def int_or_none(value: str) -> Optional[int]:
    value = clean_text(value)
    if not value:
        return None

    m = re.search(r"\d+", value.replace(",", ""))
    if not m:
        return None

    try:
        return int(m.group(0))
    except ValueError:
        return None


def find_existing_trial(
    conn,
    registry_id: int,
    trial_id: str,
) -> Optional[Tuple[int, str]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, source_hash
            FROM ictrp_trial
            WHERE registry_id = %s
              AND trial_id = %s
            LIMIT 1
            """,
            (
                registry_id,
                trial_id,
            ),
        )
        row = cur.fetchone()

        if not row:
            return None

        return int(row[0]), row[1]
    finally:
        cur.close()


TRIAL_COLUMNS = [
    "registry_id",
    "trial_id",
    "utrn",

    "date_registration_raw",
    "date_registration",

    "primary_sponsor",

    "public_title",
    "acronym",
    "scientific_title",
    "scientific_acronym",

    "date_enrolment_raw",
    "date_enrolment",
    "type_enrolment",

    "target_size_raw",
    "target_size",

    "recruitment_status_raw",
    "recruitment_status",

    "url",

    "study_type_raw",
    "study_type",

    "study_design",

    "phase_raw",
    "phase",

    "hc_freetext",
    "i_freetext",

    "inclusion_criteria",
    "exclusion_criteria",

    "age_min_raw",
    "age_max_raw",
    "age_min_years",
    "age_max_years",

    "gender_raw",
    "gender",

    "results_actual_enrolment",
    "results_date_completed",
    "results_url_link",
    "results_summary",
    "results_date_posted",
    "results_date_first_publication",
    "results_baseline_char",
    "results_participant_flow",
    "results_adverse_events",
    "results_outcome_measures",
    "results_url_protocol",
    "results_ipd_plan",
    "results_ipd_description",

    "source_hash",
]


def trial_row(
    data: Dict[str, Any],
    registry_id: int,
    source_hash: str,
) -> Dict[str, Any]:
    m = data["main"]
    c = data["criteria"]

    return {
        "registry_id": registry_id,
        "trial_id": m["trial_id"],
        "utrn": m["utrn"] or None,

        "date_registration_raw": m["date_registration"] or None,
        "date_registration": parse_date(m["date_registration"]),

        "primary_sponsor": m["primary_sponsor"] or None,

        "public_title": m["public_title"] or None,
        "acronym": m["acronym"] or None,
        "scientific_title": m["scientific_title"] or None,
        "scientific_acronym": m["scientific_acronym"] or None,

        "date_enrolment_raw": m["date_enrolment"] or None,
        "date_enrolment": parse_date(m["date_enrolment"]),
        "type_enrolment": m["type_enrolment"] or None,

        "target_size_raw": m["target_size"] or None,
        "target_size": int_or_none(m["target_size"]),

        "recruitment_status_raw": m["recruitment_status"] or None,
        "recruitment_status": normalize_recruitment_status(
            m["recruitment_status"]
        ),

        "url": m["url"] or None,

        "study_type_raw": m["study_type"] or None,
        "study_type": normalize_study_type(m["study_type"]),

        "study_design": m["study_design"] or None,

        "phase_raw": m["phase"] or None,
        "phase": normalize_phase(m["phase"]),

        "hc_freetext": m["hc_freetext"] or None,
        "i_freetext": m["i_freetext"] or None,

        "inclusion_criteria": c["inclusion_criteria"] or None,
        "exclusion_criteria": c["exclusion_criteria"] or None,

        "age_min_raw": c["agemin"] or None,
        "age_max_raw": c["agemax"] or None,
        "age_min_years": parse_age_years(c["agemin"]),
        "age_max_years": parse_age_years(c["agemax"]),

        "gender_raw": c["gender"] or None,
        "gender": normalize_gender(c["gender"]),

        "results_actual_enrolment": m["results_actual_enrolment"] or None,
        "results_date_completed": m["results_date_completed"] or None,
        "results_url_link": m["results_url_link"] or None,
        "results_summary": m["results_summary"] or None,
        "results_date_posted": m["results_date_posted"] or None,
        "results_date_first_publication": m["results_date_first_publication"] or None,
        "results_baseline_char": m["results_baseline_char"] or None,
        "results_participant_flow": m["results_participant_flow"] or None,
        "results_adverse_events": m["results_adverse_events"] or None,
        "results_outcome_measures": m["results_outcome_measures"] or None,
        "results_url_protocol": m["results_url_protocol"] or None,
        "results_ipd_plan": m["results_IPD_plan"] or None,
        "results_ipd_description": m["results_IPD_description"] or None,

        "source_hash": source_hash,
    }


def insert_trial(
    conn,
    row: Dict[str, Any],
) -> int:
    cols = TRIAL_COLUMNS
    placeholders = ", ".join(["%s"] * len(cols))

    sql = f"""
        INSERT INTO ictrp_trial (
            {", ".join(cols)}
        )
        VALUES (
            {placeholders}
        )
    """

    values = [row[col] for col in cols]

    cur = conn.cursor()
    try:
        cur.execute(sql, values)
        return int(cur.lastrowid)
    finally:
        cur.close()


def update_trial(
    conn,
    trial_pk: int,
    row: Dict[str, Any],
) -> None:
    cols = [
        c
        for c in TRIAL_COLUMNS
        if c not in (
            "registry_id",
            "trial_id",
        )
    ]

    assignments = ", ".join(
        f"{col} = %s"
        for col in cols
    )

    values = [
        row[col]
        for col in cols
    ]

    values.append(trial_pk)

    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            UPDATE ictrp_trial
            SET {assignments}
            WHERE id = %s
            """,
            values,
        )
    finally:
        cur.close()


# ============================================================
# Tabelas filhas
# ============================================================

def delete_children(conn, trial_pk: int) -> None:
    cur = conn.cursor()
    try:
        for table in CHILD_TABLES:
            cur.execute(
                f"""
                DELETE FROM {table}
                WHERE trial_pk = %s
                """,
                (trial_pk,),
            )
    finally:
        cur.close()


def unique_ci(values: Iterable[str]) -> List[str]:
    """
    Remove duplicidades de forma compatível com collations MySQL
    case-insensitive, preservando o primeiro valor original.

    Ex.: "DeCs" e "DECS" são considerados o mesmo código.
    """
    seen = set()
    result = []

    for value in values:
        value = clean_text(value)
        if not value:
            continue

        key = normalize_search_text(value)

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def insert_children(
    conn,
    trial_pk: int,
    data: Dict[str, Any],
) -> None:
    cur = conn.cursor()

    try:
        # Contacts
        contact_rows = [
            (
                trial_pk,
                x["type"] or None,
                x["firstname"] or None,
                x["middlename"] or None,
                x["lastname"] or None,
                x["address"] or None,
                x["city"] or None,
                x["country"] or None,
                x["zip"] or None,
                x["telephone"] or None,
                x["email"] or None,
                x["affiliation"] or None,
            )
            for x in data["contacts"]
        ]

        if contact_rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_contact (
                    trial_pk,
                    contact_type,
                    firstname,
                    middlename,
                    lastname,
                    address,
                    city,
                    country_code,
                    zip,
                    telephone,
                    email,
                    affiliation
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                contact_rows,
            )

        # Countries
        country_rows = [
            (
                trial_pk,
                country,
            )
            for country in unique_ci(
                data["countries"]
            )
        ]

        if country_rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_country (
                    trial_pk,
                    country_code
                )
                VALUES (%s, %s)
                """,
                country_rows,
            )

        # Condition codes
        rows = [
            (trial_pk, value)
            for value in unique_ci(
                data["condition_codes"]
            )
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_condition_code (
                    trial_pk,
                    condition_code
                )
                VALUES (%s, %s)
                """,
                rows,
            )

        # Condition keywords
        rows = [
            (
                trial_pk,
                value,
                normalize_search_text(value),
            )
            for value in data["condition_keywords"]
            if value
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_condition_keyword (
                    trial_pk,
                    keyword,
                    keyword_normalized
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

        # Intervention codes
        rows = [
            (trial_pk, value)
            for value in unique_ci(
                data["intervention_codes"]
            )
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_intervention_code (
                    trial_pk,
                    intervention_code
                )
                VALUES (%s, %s)
                """,
                rows,
            )

        # Intervention keywords
        rows = [
            (
                trial_pk,
                value,
                normalize_search_text(value),
            )
            for value in data["intervention_keywords"]
            if value
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_intervention_keyword (
                    trial_pk,
                    keyword,
                    keyword_normalized
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

        # Primary outcomes
        rows = [
            (
                trial_pk,
                idx,
                value,
            )
            for idx, value in enumerate(
                data["primary_outcomes"],
                start=1,
            )
            if value
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_primary_outcome (
                    trial_pk,
                    ordinal_no,
                    outcome_text
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

        # Secondary outcomes
        rows = [
            (
                trial_pk,
                idx,
                value,
            )
            for idx, value in enumerate(
                data["secondary_outcomes"],
                start=1,
            )
            if value
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_secondary_outcome (
                    trial_pk,
                    ordinal_no,
                    outcome_text
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

        # Secondary sponsors
        rows = [
            (trial_pk, value)
            for value in data["secondary_sponsors"]
            if value
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_secondary_sponsor (
                    trial_pk,
                    sponsor_name
                )
                VALUES (%s, %s)
                """,
                rows,
            )

        # Secondary IDs
        rows = [
            (
                trial_pk,
                x["sec_id"] or None,
                x["issuing_authority"] or None,
            )
            for x in data["secondary_ids"]
            if (
                x["sec_id"]
                or x["issuing_authority"]
            )
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_secondary_id (
                    trial_pk,
                    secondary_id,
                    issuing_authority
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

        # Source/support
        rows = [
            (trial_pk, value)
            for value in data["source_support"]
            if value
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_source_support (
                    trial_pk,
                    source_name
                )
                VALUES (%s, %s)
                """,
                rows,
            )

        # Ethics reviews
        rows = [
            (
                trial_pk,
                x["status"] or None,
                x["approval_date"] or None,
                parse_date(x["approval_date"]),
                x["contact_name"] or None,
                x["contact_address"] or None,
                x["contact_phone"] or None,
                x["contact_email"] or None,
            )
            for x in data["ethics_reviews"]
        ]

        if rows:
            cur.executemany(
                """
                INSERT INTO ictrp_trial_ethics_review (
                    trial_pk,
                    status,
                    approval_date_raw,
                    approval_date,
                    contact_name,
                    contact_address,
                    contact_phone,
                    contact_email
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                """,
                rows,
            )

    finally:
        cur.close()


# ============================================================
# Índice de busca desnormalizado
# ============================================================

def upsert_search_row(
    conn,
    trial_pk: int,
    registry_id: int,
    data: Dict[str, Any],
) -> None:
    m = data["main"]
    c = data["criteria"]

    title_text = join_search([
        m["public_title"],
        m["scientific_title"],
        m["acronym"],
        m["scientific_acronym"],
    ])

    condition_text = join_search(
        [m["hc_freetext"]]
        + data["condition_codes"]
        + data["condition_keywords"]
    )

    intervention_text = join_search(
        [m["i_freetext"]]
        + data["intervention_codes"]
        + data["intervention_keywords"]
    )

    eligibility_text = join_search([
        c["inclusion_criteria"],
        c["exclusion_criteria"],
    ])

    outcome_text = join_search(
        data["primary_outcomes"]
        + data["secondary_outcomes"]
    )

    sponsor_text = join_search(
        [m["primary_sponsor"]]
        + data["secondary_sponsors"]
        + data["source_support"]
    )

    country_text = join_search(
        data["countries"]
    )

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ictrp_trial_search (
                trial_pk,
                registry_id,
                trial_id,
                utrn,

                public_title,
                scientific_title,

                title_text,
                condition_text,
                intervention_text,
                eligibility_text,
                outcome_text,
                sponsor_text,
                country_text,

                recruitment_status,
                study_type,
                phase,
                gender,
                age_min_years,
                age_max_years,
                date_registration
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                registry_id = VALUES(registry_id),
                trial_id = VALUES(trial_id),
                utrn = VALUES(utrn),

                public_title = VALUES(public_title),
                scientific_title = VALUES(scientific_title),

                title_text = VALUES(title_text),
                condition_text = VALUES(condition_text),
                intervention_text = VALUES(intervention_text),
                eligibility_text = VALUES(eligibility_text),
                outcome_text = VALUES(outcome_text),
                sponsor_text = VALUES(sponsor_text),
                country_text = VALUES(country_text),

                recruitment_status = VALUES(recruitment_status),
                study_type = VALUES(study_type),
                phase = VALUES(phase),
                gender = VALUES(gender),
                age_min_years = VALUES(age_min_years),
                age_max_years = VALUES(age_max_years),
                date_registration = VALUES(date_registration)
            """,
            (
                trial_pk,
                registry_id,
                m["trial_id"],
                m["utrn"] or None,

                m["public_title"] or None,
                m["scientific_title"] or None,

                title_text or None,
                condition_text or None,
                intervention_text or None,
                eligibility_text or None,
                outcome_text or None,
                sponsor_text or None,
                country_text or None,

                normalize_recruitment_status(
                    m["recruitment_status"]
                ),
                normalize_study_type(
                    m["study_type"]
                ),
                normalize_phase(
                    m["phase"]
                ),
                normalize_gender(
                    c["gender"]
                ),
                parse_age_years(
                    c["agemin"]
                ),
                parse_age_years(
                    c["agemax"]
                ),
                parse_date(
                    m["date_registration"]
                ),
            ),
        )
    finally:
        cur.close()


# ============================================================
# Import run
# ============================================================

def create_import_run(
    conn,
    xml_path: Path,
    file_sha256: str,
) -> int:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ictrp_import_run (
                source_file,
                source_file_sha256,
                started_at,
                status
            )
            VALUES (
                %s,
                %s,
                NOW(),
                'running'
            )
            """,
            (
                str(xml_path),
                file_sha256,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        cur.close()


def finish_import_run(
    conn,
    run_id: int,
    stats: Dict[str, int],
    status: str,
    message: str = "",
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE ictrp_import_run
            SET
                finished_at = NOW(),
                status = %s,

                total_xml = %s,
                inserted_count = %s,
                updated_count = %s,
                unchanged_count = %s,
                error_count = %s,

                message = %s
            WHERE id = %s
            """,
            (
                status,
                stats["total"],
                stats["inserted"],
                stats["updated"],
                stats["unchanged"],
                stats["errors"],
                message or None,
                run_id,
            ),
        )
        conn.commit()
    finally:
        cur.close()


# ============================================================
# XML original por trial
# ============================================================

def get_trial_xml_state(conn, trial_pk: int):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT source_hash
            FROM ictrp_trial_xml
            WHERE trial_pk = %s
            """,
            (trial_pk,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()


def upsert_trial_xml(
    conn,
    trial_pk: int,
    source_hash: str,
    trial_xml: str,
) -> str:
    """
    Retorna: inserted | updated | unchanged
    """
    current_hash = get_trial_xml_state(
        conn,
        trial_pk,
    )

    if current_hash == source_hash:
        return "unchanged"

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ictrp_trial_xml (
                trial_pk,
                source_hash,
                trial_xml
            )
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                source_hash = VALUES(source_hash),
                trial_xml = VALUES(trial_xml),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                trial_pk,
                source_hash,
                trial_xml,
            ),
        )
    finally:
        cur.close()

    if current_hash is None:
        return "inserted"

    return "updated"


def get_trial_xml_population(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM ictrp_trial"
        )
        trials = int(cur.fetchone()[0])

        cur.execute(
            "SELECT COUNT(*) FROM ictrp_trial_xml"
        )
        xml_rows = int(cur.fetchone()[0])

        return {
            "trials": trials,
            "xml_rows": xml_rows,
            "missing": max(0, trials - xml_rows),
            "complete": (
                trials > 0
                and xml_rows >= trials
            ),
        }
    finally:
        cur.close()


# ============================================================
# Carga incremental
# ============================================================

def import_xml(
    conn,
    xml_path: Path,
    verbose: bool = False,
    progress_every: int = 100,
    xml_only: bool = False,
) -> Dict[str, int]:
    stats = {
        "total": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": 0,
        "xml_inserted": 0,
        "xml_updated": 0,
        "xml_unchanged": 0,
    }

    registry_cache: Dict[Tuple[str, str], int] = {}

    started = time.time()

    context = ET.iterparse(
        str(xml_path),
        events=("end",),
    )

    for _event, elem in context:
        if elem.tag != "trial":
            continue

        stats["total"] += 1

        trial_id_for_log = "UNKNOWN"

        try:
            data = parse_trial_element(elem)
            trial_xml_text = ET.tostring(
                elem,
                encoding="unicode",
            )
            trial_xml_hash = hashlib.sha256(
                trial_xml_text.encode("utf-8")
            ).hexdigest()
            m = data["main"]

            trial_id = clean_text(
                m["trial_id"]
            )

            trial_id_for_log = (
                trial_id
                or "UNKNOWN"
            )

            if not trial_id:
                raise ValueError(
                    "trial sem trial_id"
                )

            reg_name = (
                clean_text(m["reg_name"])
                or "UNKNOWN"
            )

            reg_country = clean_text(
                m["reg_country"]
            )

            reg_key = (
                reg_name,
                reg_country,
            )

            if reg_key not in registry_cache:
                registry_cache[reg_key] = (
                    get_or_create_registry(
                        conn,
                        reg_name,
                        reg_country,
                    )
                )

            registry_id = (
                registry_cache[reg_key]
            )

            source_hash = canonical_hash(
                data
            )

            existing = find_existing_trial(
                conn,
                registry_id,
                trial_id,
            )

            if xml_only:
                if not existing:
                    raise ValueError(
                        "trial não existe na base normalizada "
                        "para carga --xml-only"
                    )

                trial_pk = existing[0]
                xml_action = upsert_trial_xml(
                    conn,
                    trial_pk,
                    trial_xml_hash,
                    trial_xml_text,
                )
                stats[
                    f"xml_{xml_action}"
                ] += 1
                stats["unchanged"] += 1
                conn.commit()

                if verbose:
                    print(
                        f"[XML-{xml_action.upper()}] "
                        f"{reg_name} / {trial_id}"
                    )

                elem.clear()
                continue

            if (
                existing
                and existing[1] == source_hash
            ):
                trial_pk = existing[0]

                xml_action = upsert_trial_xml(
                    conn,
                    trial_pk,
                    trial_xml_hash,
                    trial_xml_text,
                )
                stats[
                    f"xml_{xml_action}"
                ] += 1
                conn.commit()

                stats["unchanged"] += 1

                if verbose:
                    print(
                        f"[UNCHANGED] "
                        f"{reg_name} / {trial_id} "
                        f"xml={xml_action}"
                    )

                elem.clear()
                continue

            row = trial_row(
                data,
                registry_id,
                source_hash,
            )

            try:
                if existing:
                    trial_pk = existing[0]

                    update_trial(
                        conn,
                        trial_pk,
                        row,
                    )

                    delete_children(
                        conn,
                        trial_pk,
                    )

                    action = "UPDATED"

                else:
                    trial_pk = insert_trial(
                        conn,
                        row,
                    )

                    action = "INSERTED"

                insert_children(
                    conn,
                    trial_pk,
                    data,
                )

                upsert_search_row(
                    conn,
                    trial_pk,
                    registry_id,
                    data,
                )

                xml_action = upsert_trial_xml(
                    conn,
                    trial_pk,
                    trial_xml_hash,
                    trial_xml_text,
                )
                stats[
                    f"xml_{xml_action}"
                ] += 1

                conn.commit()

                if existing:
                    stats["updated"] += 1
                else:
                    stats["inserted"] += 1

                if verbose:
                    print(
                        f"[{action}] "
                        f"{reg_name} / {trial_id}"
                    )

            except Exception:
                conn.rollback()
                raise

        except Exception as exc:
            stats["errors"] += 1

            print(
                f"[ERRO] "
                f"{trial_id_for_log}: "
                f"{exc}",
                file=sys.stderr,
            )

        finally:
            elem.clear()

        if (
            progress_every > 0
            and stats["total"] % progress_every == 0
        ):
            elapsed = time.time() - started

            print(
                f"[{stats['total']}] "
                f"inserted={stats['inserted']} "
                f"updated={stats['updated']} "
                f"unchanged={stats['unchanged']} "
                f"xml_inserted={stats['xml_inserted']} "
                f"xml_updated={stats['xml_updated']} "
                f"xml_unchanged={stats['xml_unchanged']} "
                f"errors={stats['errors']} "
                f"elapsed={elapsed:.1f}s"
            )

    return stats


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Importa XML ICTRP para uma "
            "base MySQL normalizada e incremental."
        )
    )

    parser.add_argument(
        "xml",
        nargs="?",
        default="RBR-ictrp-ALL.xml",
        help=(
            "arquivo XML ICTRP "
            "(padrão: RBR-ictrp-ALL.xml)"
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="mostra INSERT/UPDATE/UNCHANGED por ensaio",
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help=(
            "mostra progresso a cada N trials "
            "(padrão: 100)"
        ),
    )

    parser.add_argument(
        "--xml-only",
        action="store_true",
        help=(
            "preenche/atualiza apenas ictrp_trial_xml; "
            "não altera as demais tabelas normalizadas"
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    xml_path = Path(args.xml).expanduser().resolve()

    if not xml_path.exists():
        print(
            f"Arquivo não encontrado: "
            f"{xml_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    print(
        "ICTRP XML Loader"
    )
    print(
        f"XML: {xml_path}"
    )
    print(
        f"Tamanho: "
        f"{xml_path.stat().st_size / 1024 / 1024:.1f} MB"
    )

    print(
        "Calculando SHA-256 do arquivo..."
    )

    file_sha256 = sha256_file(
        xml_path
    )

    print(
        f"SHA-256: {file_sha256}"
    )

    conn = None
    run_id = None

    stats = {
        "total": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": 0,
        "xml_inserted": 0,
        "xml_updated": 0,
        "xml_unchanged": 0,
    }

    try:
        conn = mysql.connector.connect(
            **MYSQL_CONFIG
        )

        # Garante utf8mb4 na sessão.
        cur = conn.cursor()
        cur.execute(
            "SET NAMES utf8mb4"
        )
        cur.close()

        print(
            "Criando/verificando schema e migrações..."
        )

        create_schema(conn)
        apply_schema_migrations(conn)

        xml_population = get_trial_xml_population(
            conn
        )
        print(
            "Estado ictrp_trial_xml: "
            f"trials={xml_population['trials']} "
            f"xml_rows={xml_population['xml_rows']} "
            f"missing={xml_population['missing']} "
            f"complete={xml_population['complete']}"
        )

        if (
            args.xml_only
            and xml_population["complete"]
        ):
            print(
                "Tabela ictrp_trial_xml já está populada. "
                "A execução continuará apenas para validar hashes."
            )

        run_id = create_import_run(
            conn,
            xml_path,
            file_sha256,
        )

        print(
            f"Import run: {run_id}"
        )

        print(
            "Iniciando carga incremental..."
        )

        started = time.time()

        stats = import_xml(
            conn,
            xml_path,
            verbose=args.verbose,
            progress_every=args.progress_every,
            xml_only=args.xml_only,
        )

        elapsed = time.time() - started

        status = (
            "completed"
            if stats["errors"] == 0
            else "completed_with_errors"
        )

        finish_import_run(
            conn,
            run_id,
            stats,
            status=status,
            message=(
                f"Elapsed: {elapsed:.1f}s"
            ),
        )

        print()
        print(
            "========================================"
        )
        print(
            "CARGA FINALIZADA"
        )
        print(
            "========================================"
        )
        print(
            f"Trials no XML : {stats['total']}"
        )
        print(
            f"Inseridos      : {stats['inserted']}"
        )
        print(
            f"Atualizados    : {stats['updated']}"
        )
        print(
            f"Sem alteração  : {stats['unchanged']}"
        )
        print(
            f"Erros          : {stats['errors']}"
        )
        print(
            f"XML inseridos  : {stats['xml_inserted']}"
        )
        print(
            f"XML atualizados: {stats['xml_updated']}"
        )
        print(
            f"XML inalterados: {stats['xml_unchanged']}"
        )
        print(
            f"Tempo          : {elapsed:.1f}s"
        )
        print(
            "========================================"
        )

    except KeyboardInterrupt:
        print(
            "\nInterrompido pelo usuário.",
            file=sys.stderr,
        )

        if conn:
            conn.rollback()

        if conn and run_id:
            try:
                finish_import_run(
                    conn,
                    run_id,
                    stats,
                    status="interrupted",
                    message="Interrompido pelo usuário",
                )
            except Exception:
                pass

        sys.exit(130)

    except Exception as exc:
        print(
            f"ERRO FATAL: {exc}",
            file=sys.stderr,
        )

        if conn:
            conn.rollback()

        if conn and run_id:
            try:
                finish_import_run(
                    conn,
                    run_id,
                    stats,
                    status="failed",
                    message=str(exc),
                )
            except Exception:
                pass

        sys.exit(1)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
