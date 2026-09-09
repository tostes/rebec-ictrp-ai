# ReBEC AI Search — Kit inicial

## Objetivo

Criar um parser multilíngue especializado em transformar pesquisas em linguagem natural em filtros canônicos do ReBEC.

## Arquivos

- `rebec_search_schema.json`: contrato canônico e mapeamento dos filtros para `fossil_fossil.serialized`.
- `rebec_system_prompt.txt`: prompt de sistema para uso imediato com o Qwen local.
- `gerar_dataset_rebec.py`: gera exemplos sintéticos a partir dos registros atuais de `fossil_fossil`.
- `avaliar_modelo_rebec.py`: mede JSON válido, exact match, filtros inventados e filtros esquecidos.

## 1. Use primeiro SEM fine-tuning

No seu `teste_busca_ia.py`, carregue:

```python
SYSTEM_PROMPT = open("rebec_system_prompt.txt", encoding="utf-8").read()
```

Mantenha:
- `temperature=0`
- `enable_thinking=False`
- saída JSON
- nenhuma execução de SQL gerado pelo modelo

## 2. Gerar dataset

Exemplo:

```bash
python gerar_dataset_rebec.py   --user root   --password 'SENHA'   --database NOME_DO_BANCO   --limit 1000   --output rebec_dataset.jsonl
```

Para começar, use 500–1000 ensaios. Depois aumente.

## 3. Separar treino e teste

```bash
shuf rebec_dataset.jsonl > rebec_dataset_shuffled.jsonl
head -n 4000 rebec_dataset_shuffled.jsonl > train.jsonl
tail -n 1000 rebec_dataset_shuffled.jsonl > test.jsonl
```

Não use o mesmo conjunto para avaliar e treinar.

## 4. Avaliar o Qwen atual

```bash
python avaliar_modelo_rebec.py   --dataset test.jsonl   --prompt rebec_system_prompt.txt   --limit 200
```

A métrica mais importante é `Filtros inventados`.

## 5. Critérios para considerar o parser bom

Meta inicial:
- JSON válido >= 99%
- exact match >= 90%
- filtros inventados <= 1% das consultas
- recruitment_status >= 98%
- gender >= 98%
- phase >= 95%

## 6. Antes do fine-tuning

Adicione exemplos manuais com consultas reais:
- sinônimos;
- erros de digitação;
- português informal;
- inglês/espanhol/francês;
- condições e intervenções ambíguas;
- consultas com e sem filtros explícitos.

Exemplos negativos são especialmente importantes:
- `estudos sobre HIV` NÃO deve virar `recruiting`;
- `estudos para mulheres` NÃO deve inventar condição;
- `fase 3` NÃO deve inventar doença;
- `estudos concluídos` NÃO deve inventar intervenção.

## 7. Fine-tuning

Só faça LoRA/QLoRA quando o benchmark mostrar que prompt + schema não atingem a qualidade desejada.

O objetivo do fine-tuning é ensinar:
`consulta multilíngue -> JSON ReBEC`

Não é ensinar os ensaios clínicos ao modelo. Os ensaios continuam no MySQL.

## Observação

O gerador sintético é uma base inicial. Ele deve ser enriquecido com exemplos manuais e, idealmente, consultas reais anonimizadas de usuários quando existirem.
