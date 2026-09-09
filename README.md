# ReBEC ICTRP AI

Experimental AI platform for intelligent search, retrieval, and analysis of
clinical trial registry data, focused on ICTRP interoperability, structured
data, and local language models.

## Architecture

```text
llama.cpp Web UI / client
        ↓
Qwen local LLM
        ↓
tool / function calling
        ↓
FastAPI
        ↓
MySQL ICTRP
        ↓
structured trial results
        ↓
LLM response
```

## Repository layout

```text
api/                  FastAPI entry points and legacy API integration
rebec_ai/             Current ICTRP AI search engine
benchmark/            Model/search benchmark suite
scripts/              ICTRP loaders and operational scripts
legacy_experiments/   Earlier useful experiments, kept without versioned copies
schemas/              Search schemas
docs/                 Technical documentation
```

## Local configuration

Real credentials are intentionally excluded from the repository.

Use `config_example.py` and `config_example.json` only as templates.
The current runtime reads credentials from environment variables:

- `REBEC_MYSQL_HOST`
- `REBEC_MYSQL_PORT`
- `REBEC_MYSQL_USER`
- `REBEC_MYSQL_PASSWORD`
- `REBEC_MYSQL_DATABASE`
- `REBEC_AI_LLM_URL`
- `OPENAI_API_KEY` (only for legacy OpenAI-dependent endpoints)

## Running the AI test API

```bash
./run_ai_test.sh
```

Default test URL:

```text
http://127.0.0.1:8010/ai-search/
```

## Data policy

Large ICTRP XML files, database dumps, credentials, virtual environments,
logs, generated benchmark results, and old release ZIPs are not versioned.
