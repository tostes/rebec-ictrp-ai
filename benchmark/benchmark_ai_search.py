#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


FILTER_KEYS = [
    "condition",
    "intervention",
    "title",
    "recruitment_status",
    "phase",
    "gender",
    "age_min_years",
    "age_max_years",
    "country",
    "sponsor",
    "study_type",
    "registration_date_from",
    "registration_date_to",
]


def normalize_value(value):
    if isinstance(value, str):
        return value.strip()
    return value


def compare_filters(actual, expected):
    actual = actual or {}
    expected = expected or {}

    expected_ok = {}
    wrong_expected = {}
    hallucinated = {}

    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        ok = normalize_value(actual_value) == normalize_value(expected_value)
        expected_ok[key] = ok
        if not ok:
            wrong_expected[key] = {
                "expected": expected_value,
                "actual": actual_value,
            }

    # Any non-null filter not expected by the benchmark is counted as hallucinated.
    for key in FILTER_KEYS:
        if key in expected:
            continue
        value = actual.get(key)
        if value not in (None, "", [], {}):
            hallucinated[key] = value

    return {
        "expected_field_count": len(expected),
        "expected_correct_count": sum(1 for v in expected_ok.values() if v),
        "all_expected_correct": all(expected_ok.values()) if expected_ok else True,
        "wrong_expected": wrong_expected,
        "hallucinated": hallucinated,
        "hallucination_count": len(hallucinated),
        "perfect": (
            (all(expected_ok.values()) if expected_ok else True)
            and not hallucinated
        ),
    }


def request_one(session, base_url, item, timeout):
    url = base_url.rstrip("/") + "/ai-search/api/search"

    # Force English display to avoid result translation latency.
    # This benchmark is about query interpretation/search, not translation.
    payload = {
        "query": item.get("query", ""),
        "language": "en",
        "filters": item.get("filters", {}),
        "page": 1,
        "page_size": 5,
        "threshold": 0.70,
    }

    t0 = time.perf_counter()

    response = session.post(
        url,
        json=payload,
        timeout=timeout,
    )

    elapsed = time.perf_counter() - t0

    try:
        data = response.json()
    except Exception:
        data = {
            "_raw_text": response.text,
        }

    return response.status_code, elapsed, payload, data


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark ReBEC AI Search via FastAPI"
    )

    parser.add_argument(
        "--base-url",
        required=True,
        help="Ex.: http://127.0.0.1:8010",
    )

    parser.add_argument(
        "--label",
        required=True,
        help="Nome do modelo/configuração. Ex.: qwen-0.8b",
    )

    parser.add_argument(
        "--queries",
        default="benchmark_queries.json",
    )

    parser.add_argument(
        "--output-dir",
        default="benchmark_results",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Pausa entre requests",
    )

    args = parser.parse_args()

    queries_path = Path(args.queries)
    tests = json.loads(
        queries_path.read_text(encoding="utf-8")
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{args.label}_{timestamp}"

    session = requests.Session()

    rows = []
    full_results = []

    print(f"Modelo/configuração: {args.label}")
    print(f"API: {args.base_url}")
    print(f"Testes: {len(tests)}")
    print()

    for idx, item in enumerate(tests, 1):
        test_id = item["id"]

        print(
            f"[{idx:02d}/{len(tests)}] "
            f"{test_id}: {item.get('query') or '[advanced only]'}"
        )

        try:
            status, elapsed, payload, data = request_one(
                session,
                args.base_url,
                item,
                args.timeout,
            )

            debug = data.get("debug", {})
            structured_debug = debug.get("structured", {}) if isinstance(debug, dict) else {}

            # Current API stores the useful structured debug both in
            # debug.structured and in debug.text. Prefer structured.
            # The FastAPI response already exposes the effective filters
            # at top level. This is the authoritative source for benchmark
            # scoring and works in both DEBUG and PROD.
            final_filters = data.get("filters")

            llm_filters = (
                structured_debug.get("llm_filters")
                if isinstance(structured_debug, dict)
                else None
            )

            if final_filters is None and isinstance(structured_debug, dict):
                final_filters = structured_debug.get("final_filters")

            if final_filters is None and isinstance(debug, dict):
                final_filters = debug.get("final_filters")

            if llm_filters is None and isinstance(debug, dict):
                llm_filters = debug.get("llm_filters")

            if final_filters is None:
                final_filters = {}

            comparison = compare_filters(
                final_filters,
                item.get("expected", {}),
            )

            db_stats = data.get("db_stats", {}) or {}

            row = {
                "test_id": test_id,
                "query_language": item.get("language"),
                "query": item.get("query", ""),
                "model_label": args.label,
                "http_status": status,
                "request_seconds": round(elapsed, 4),
                "search_seconds": db_stats.get("total_search_seconds"),
                "mysql_seconds": db_stats.get("mysql_seconds"),
                "ranking_seconds": db_stats.get("ranking_seconds"),
                "total_results": data.get("total_results"),
                "primary_count": data.get("primary_count"),
                "related_count": data.get("related_count"),
                "perfect": comparison["perfect"],
                "all_expected_correct": comparison["all_expected_correct"],
                "expected_correct_count": comparison["expected_correct_count"],
                "expected_field_count": comparison["expected_field_count"],
                "hallucination_count": comparison["hallucination_count"],
                "expected_json": json.dumps(item.get("expected", {}), ensure_ascii=False),
                "final_filters_json": json.dumps(final_filters, ensure_ascii=False),
                "llm_filters_json": json.dumps(llm_filters, ensure_ascii=False),
                "wrong_expected_json": json.dumps(comparison["wrong_expected"], ensure_ascii=False),
                "hallucinated_json": json.dumps(comparison["hallucinated"], ensure_ascii=False),
            }

            rows.append(row)

            full_results.append({
                "test": item,
                "model_label": args.label,
                "http_status": status,
                "elapsed_seconds": elapsed,
                "request_payload": payload,
                "response": data,
                "final_filters": final_filters,
                "llm_filters": llm_filters,
                "comparison": comparison,
            })

            print(
                f"    HTTP={status} "
                f"time={elapsed:.2f}s "
                f"results={data.get('total_results')} "
                f"perfect={comparison['perfect']} "
                f"hallucinations={comparison['hallucination_count']}"
            )

        except Exception as exc:
            print(f"    ERRO: {exc}")

            rows.append({
                "test_id": test_id,
                "query_language": item.get("language"),
                "query": item.get("query", ""),
                "model_label": args.label,
                "http_status": "ERROR",
                "request_seconds": None,
                "search_seconds": None,
                "mysql_seconds": None,
                "ranking_seconds": None,
                "total_results": None,
                "primary_count": None,
                "related_count": None,
                "perfect": False,
                "all_expected_correct": False,
                "expected_correct_count": 0,
                "expected_field_count": len(item.get("expected", {})),
                "hallucination_count": None,
                "expected_json": json.dumps(item.get("expected", {}), ensure_ascii=False),
                "final_filters_json": "",
                "llm_filters_json": "",
                "wrong_expected_json": json.dumps({"exception": str(exc)}, ensure_ascii=False),
                "hallucinated_json": "",
            })

            full_results.append({
                "test": item,
                "model_label": args.label,
                "exception": repr(exc),
            })

        time.sleep(args.sleep)

    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"
    summary_path = output_dir / f"{stem}_summary.json"

    fieldnames = list(rows[0].keys())

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(
        json.dumps(
            full_results,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    valid_times = [
        x["request_seconds"]
        for x in rows
        if isinstance(x.get("request_seconds"), (int, float))
    ]

    valid_rows = [
        x
        for x in rows
        if x.get("http_status") == 200
    ]

    summary = {
        "model_label": args.label,
        "base_url": args.base_url,
        "tests": len(rows),
        "http_200": len(valid_rows),
        "perfect_count": sum(1 for x in rows if x.get("perfect") is True),
        "perfect_percent": round(
            100.0 * sum(1 for x in rows if x.get("perfect") is True) / len(rows),
            2,
        ) if rows else 0,
        "total_hallucinations": sum(
            x.get("hallucination_count") or 0
            for x in rows
        ),
        "mean_request_seconds": round(statistics.mean(valid_times), 4)
        if valid_times else None,
        "median_request_seconds": round(statistics.median(valid_times), 4)
        if valid_times else None,
        "min_request_seconds": round(min(valid_times), 4)
        if valid_times else None,
        "max_request_seconds": round(max(valid_times), 4)
        if valid_times else None,
        "generated_at": datetime.now().isoformat(),
        "csv": str(csv_path),
        "json": str(json_path),
    }

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("========================================")
    print("BENCHMARK FINALIZADO")
    print("========================================")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print(f"CSV    : {csv_path}")
    print(f"JSON   : {json_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
