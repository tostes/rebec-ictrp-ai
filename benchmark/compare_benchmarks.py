#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
from pathlib import Path


def load_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return {
            row["test_id"]: row
            for row in csv.DictReader(f)
        }


def as_float(v):
    try:
        return float(v)
    except Exception:
        return None


def as_bool(v):
    return str(v).lower() == "true"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv_a")
    p.add_argument("csv_b")
    p.add_argument("--output", default="benchmark_comparison.csv")
    args = p.parse_args()

    a = load_csv(args.csv_a)
    b = load_csv(args.csv_b)

    ids = sorted(set(a) | set(b))
    rows = []

    for test_id in ids:
        ra = a.get(test_id, {})
        rb = b.get(test_id, {})

        ta = as_float(ra.get("request_seconds"))
        tb = as_float(rb.get("request_seconds"))

        rows.append({
            "test_id": test_id,
            "query": ra.get("query") or rb.get("query"),
            "model_a": ra.get("model_label"),
            "model_b": rb.get("model_label"),
            "perfect_a": as_bool(ra.get("perfect")),
            "perfect_b": as_bool(rb.get("perfect")),
            "hallucinations_a": ra.get("hallucination_count"),
            "hallucinations_b": rb.get("hallucination_count"),
            "seconds_a": ta,
            "seconds_b": tb,
            "seconds_delta_b_minus_a": (
                round(tb - ta, 4)
                if ta is not None and tb is not None
                else None
            ),
            "winner_quality": (
                "B"
                if (not as_bool(ra.get("perfect")) and as_bool(rb.get("perfect")))
                else "A"
                if (as_bool(ra.get("perfect")) and not as_bool(rb.get("perfect")))
                else "tie"
            ),
            "final_filters_a": ra.get("final_filters_json"),
            "final_filters_b": rb.get("final_filters_json"),
        })

    out = Path(args.output)

    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(out)


if __name__ == "__main__":
    main()
