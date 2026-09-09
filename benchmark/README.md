# ReBEC AI Search — Benchmark via FastAPI

Este pacote roda 50 buscas diretamente contra o endpoint:

`POST /ai-search/api/search`

Objetivo:
- comparar modelos/configurações;
- registrar filtros finais;
- detectar filtros inventados;
- medir tempo;
- preservar a resposta completa e o DEBUG para análise posterior.

## Importante

O benchmark envia sempre:

```json
"language": "en"
```

para a camada de apresentação, mesmo quando a consulta está em português
ou espanhol.

Isso é proposital: evita gastar tempo traduzindo os resultados e mede
principalmente o interpretador da busca.

O idioma original da consulta continua registrado em cada teste.

## Arquivos

- `benchmark_ai_search.py`
- `benchmark_queries.json` — 50 consultas
- `compare_benchmarks.py`

## Executando contra o modelo atual

Com o FastAPI em:

`http://127.0.0.1:8010`

rode:

```bash
python benchmark_ai_search.py \
  --base-url http://127.0.0.1:8010 \
  --label qwen-0.8b
```

Os arquivos serão gravados em:

```text
benchmark_results/
qwen-0.8b_YYYYMMDD_HHMMSS.csv
qwen-0.8b_YYYYMMDD_HHMMSS.json
qwen-0.8b_YYYYMMDD_HHMMSS_summary.json
```

O JSON completo é o arquivo mais útil para enviar ao ChatGPT depois.

## Segundo modelo

A forma mais limpa é subir outra instância do llama.cpp em outra porta,
por exemplo 8081, e outra instância do FastAPI apontando para esse LLM.

Exemplo conceitual:

Terminal A:
```bash
llama serve ...0.8B... --port 8080
```

FastAPI A:
```bash
REBEC_AI_LLM_URL=http://127.0.0.1:8080/v1/chat/completions \
uvicorn app_ai_test:app --host 127.0.0.1 --port 8010
```

Terminal B:
```bash
llama serve ...1.5B... --port 8081
```

FastAPI B:
```bash
REBEC_AI_LLM_URL=http://127.0.0.1:8081/v1/chat/completions \
uvicorn app_ai_test:app --host 127.0.0.1 --port 8011
```

Depois:

```bash
python benchmark_ai_search.py \
  --base-url http://127.0.0.1:8010 \
  --label qwen-0.8b
```

e:

```bash
python benchmark_ai_search.py \
  --base-url http://127.0.0.1:8011 \
  --label qwen-1.5b
```

## Comparando

```bash
python compare_benchmarks.py \
  benchmark_results/qwen-0.8b_....csv \
  benchmark_results/qwen-1.5b_....csv \
  --output benchmark_comparison.csv
```

## Observação sobre DEBUG estruturado

O benchmark tenta usar filtros estruturados retornados pela API.
Se sua versão atual expuser apenas o texto do DEBUG e não
`debug.structured.final_filters`, o JSON completo ainda será coletado,
mas a avaliação automática de filtros poderá ficar incompleta.

Nesse caso, o próximo pequeno ajuste no FastAPI será expor também:

```json
"debug": {
  "structured": {
    "llm_filters": {},
    "final_filters": {}
  }
}
```

Isso não altera a busca; apenas facilita a medição automática.


## v2

Corrigida a avaliação: `response.filters` é a fonte autoritativa dos filtros finais.
