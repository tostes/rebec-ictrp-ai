#!/usr/bin/env python3
import json, random, argparse
import mysql.connector

TEMPLATES = {
    "pt": {
        "condition": ["estudos sobre {condition}", "ensaios clínicos sobre {condition}"],
        "condition_phase": ["estudos sobre {condition} fase {phase}", "ensaios de {condition} fase {phase}"],
        "condition_recruiting": ["estudos sobre {condition} recrutando", "ensaios de {condition} em recrutamento"],
        "intervention": ["estudos usando {intervention}", "ensaios com {intervention}"],
    },
    "en": {
        "condition": ["trials about {condition}", "clinical trials on {condition}"],
        "condition_phase": ["phase {phase} trials about {condition}", "phase {phase} {condition} trials"],
        "condition_recruiting": ["recruiting trials about {condition}", "{condition} trials recruiting"],
        "intervention": ["trials using {intervention}", "clinical trials with {intervention}"],
    },
    "es": {
        "condition": ["ensayos sobre {condition}", "ensayos clínicos sobre {condition}"],
        "condition_phase": ["ensayos sobre {condition} fase {phase}", "ensayos fase {phase} de {condition}"],
        "condition_recruiting": ["ensayos sobre {condition} reclutando", "ensayos de {condition} en reclutamiento"],
        "intervention": ["ensayos usando {intervention}", "ensayos con {intervention}"],
    },
    "fr": {
        "condition": ["essais sur {condition}", "essais cliniques sur {condition}"],
        "condition_phase": ["essais de phase {phase} sur {condition}", "essais {condition} phase {phase}"],
        "condition_recruiting": ["essais sur {condition} en recrutement", "essais {condition} recrutant"],
        "intervention": ["essais utilisant {intervention}", "essais avec {intervention}"],
    },
}

def normalize_phase(trial):
    p = trial.get("phase") or {}
    if isinstance(p, dict):
        return p.get("label")
    return p

def status_label(trial):
    x = trial.get("recruitment_status") or {}
    return (x.get("label") if isinstance(x, dict) else x) or None

def first_condition(trial):
    v = (trial.get("hc_freetext") or "").strip()
    if v:
        return v.split(";")[0].split("\n")[0].strip()
    for key in ("hc_keyword", "hc_code"):
        for item in trial.get(key, []) or []:
            if isinstance(item, dict) and item.get("text"):
                return item["text"].strip()
    return None

def first_intervention(trial):
    for item in trial.get("intervention_keyword", []) or []:
        if isinstance(item, dict) and item.get("text"):
            return item["text"].strip()
    v = (trial.get("i_freetext") or "").strip()
    if v:
        return v[:120].replace("\n"," ")
    return None

def canonical(**kwargs):
    obj = dict(
        condition=None, intervention=None, title=None, recruitment_status=None,
        phase=None, gender=None, age_min_years=None, age_max_years=None,
        country=None, sponsor=None, study_type=None,
        registration_date_from=None, registration_date_to=None
    )
    obj.update(kwargs)
    return obj

def add_example(out, lang, template_key, values, expected):
    for t in TEMPLATES[lang][template_key]:
        try:
            q = t.format(**values)
        except Exception:
            continue
        out.append({"messages":[
            {"role":"user","content":q},
            {"role":"assistant","content":json.dumps(expected, ensure_ascii=False)}
        ], "lang": lang})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--database", required=True)
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--output", default="rebec_dataset.jsonl")
    args = ap.parse_args()

    conn = mysql.connector.connect(host=args.host,user=args.user,password=args.password,database=args.database)
    cur = conn.cursor()
    cur.execute("""SELECT serialized FROM fossil_fossil
                   WHERE is_most_recent=1 AND content_type_id=24
                   LIMIT %s""", (args.limit,))
    out = []
    for (serialized,) in cur:
        try:
            trial = json.loads(serialized)
        except Exception:
            continue
        if trial.get("__model__") != "ClinicalTrial":
            continue

        cond = first_condition(trial)
        intervention = first_intervention(trial)
        phase = normalize_phase(trial)
        status = status_label(trial)

        if cond:
            for lang in TEMPLATES:
                add_example(out, lang, "condition", {"condition":cond}, canonical(condition=cond))
                if phase and str(phase).upper() != "N/A":
                    add_example(out, lang, "condition_phase",
                                {"condition":cond, "phase":phase},
                                canonical(condition=cond, phase=str(phase)))
                if status and str(status).lower() == "recruiting":
                    add_example(out, lang, "condition_recruiting",
                                {"condition":cond},
                                canonical(condition=cond, recruitment_status="recruiting"))
        if intervention:
            for lang in TEMPLATES:
                add_example(out, lang, "intervention",
                            {"intervention":intervention},
                            canonical(intervention=intervention))

    random.shuffle(out)
    with open(args.output, "w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Gerados {len(out)} exemplos em {args.output}")

if __name__ == "__main__":
    main()
