#!/usr/bin/env python3
import json, argparse, requests

FIELDS = [
 "condition","intervention","title","recruitment_status","phase","gender",
 "age_min_years","age_max_years","country","sponsor","study_type",
 "registration_date_from","registration_date_to"
]

def parse_model(url, system_prompt, query):
    r = requests.post(url, json={
        "messages":[
            {"role":"system","content":system_prompt},
            {"role":"user","content":query}
        ],
        "temperature":0,
        "max_tokens":300,
        "chat_template_kwargs":{"enable_thinking":False}
    }, timeout=60)
    r.raise_for_status()
    c = r.json()["choices"][0]["message"].get("content") or ""
    c = c.strip().replace("```json","").replace("```","").strip()
    return json.loads(c)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    prompt = open(args.prompt, encoding="utf-8").read()
    total = exact = valid = hallucinated = missed = 0
    field_ok = {f:0 for f in FIELDS}

    with open(args.dataset, encoding="utf-8") as f:
        for line in f:
            if total >= args.limit: break
            row = json.loads(line)
            query = row["messages"][0]["content"]
            expected = json.loads(row["messages"][1]["content"])
            total += 1
            try:
                got = parse_model(args.url, prompt, query)
                valid += 1
            except Exception as e:
                print("ERRO", query, e)
                continue

            if got == expected:
                exact += 1

            for field in FIELDS:
                e = expected.get(field)
                g = got.get(field)
                if e == g:
                    field_ok[field] += 1
                if e is None and g is not None:
                    hallucinated += 1
                if e is not None and g is None:
                    missed += 1

    print(f"Total: {total}")
    print(f"JSON válido: {valid/total*100:.1f}%")
    print(f"Exact match: {exact/total*100:.1f}%")
    print(f"Filtros inventados: {hallucinated}")
    print(f"Filtros esquecidos: {missed}")
    print("\nPor campo:")
    for f in FIELDS:
        print(f"{f:24s} {field_ok[f]/total*100:6.1f}%")

if __name__ == "__main__":
    main()
