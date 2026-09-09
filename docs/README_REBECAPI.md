# ReBEC AI Search — adaptação para o `rebecAPI` atual

Este pacote foi montado para ser copiado diretamente para:

```text
~/rebec_em_numeros/rebecAPI/
```

Ele **não substitui** `app.py`. O servidor de teste `app_ai_test.py` importa o
`app` FastAPI e o dicionário `config` que já existem no seu `app.py`, e apenas
adiciona os endpoints `/ai-search`.

## Arquivos a copiar

```text
rebecAPI/
├── app.py                     # seu arquivo atual, não alterar no teste
├── app_ai_test.py             # novo
├── carga_ictrp_xml_ai.py      # novo wrapper do loader
├── requirements_ai_search.txt # dependências adicionais
├── run_ai_test.sh             # novo
├── rebec_ai/                  # novo pacote
│   ├── __init__.py
│   ├── settings.py
│   ├── router.py
│   ├── repository.py
│   ├── ai_search_engine.py
│   ├── ui.py
│   └── carga_ictrp_xml.py
└── ... seus demais arquivos atuais
```

## 1. Instalação

No diretório atual:

```bash
cd ~/rebec_em_numeros/rebecAPI
source env/bin/activate   # ajuste se o nome do venv for outro
pip install -r requirements_ai_search.txt
```

Se seu ambiente ainda não tiver FastAPI/Uvicorn, mantenha também as
versões já utilizadas pelo seu `requirements.txt` atual.

## 2. Qwen local

Em um terminal separado:

```bash
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF:Q4_0 \
  --host 127.0.0.1 \
  --port 8080 \
  -c 4096
```

## 3. Preencher a tabela XML sem refazer desnecessariamente a carga

O loader cria `ictrp_trial_xml`. Ele reconhece registros já existentes por
`trial_pk` + hash do XML e não duplica conteúdo.

Para a base que já está normalizada, use inicialmente:

```bash
python carga_ictrp_xml_ai.py \
  /caminho/RBR-ictrp-ALL.xml \
  --xml-only \
  --progress-every 500
```

Confira:

```sql
SELECT COUNT(*) FROM ictrp_trial;
SELECT COUNT(*) FROM ictrp_trial_xml;

SELECT COUNT(*) AS missing_xml
FROM ictrp_trial t
LEFT JOIN ictrp_trial_xml x ON x.trial_pk = t.id
WHERE x.trial_pk IS NULL;
```

O esperado, com sua carga atual, é `missing_xml = 0` ao final.

## 4. Ligar o FastAPI de teste sem alterar `app.py`

```bash
cd ~/rebec_em_numeros/rebecAPI
source env/bin/activate
./run_ai_test.sh
```

Equivale a:

```bash
uvicorn app_ai_test:app \
  --host 127.0.0.1 \
  --port 8010 \
  --reload
```

Abra:

```text
http://127.0.0.1:8010/ai-search/
```

Swagger:

```text
http://127.0.0.1:8010/docs
```

Os endpoints antigos do `app.py` também continuam disponíveis nesse servidor,
pois `app_ai_test.py` usa o mesmo objeto `app`.

## 5. Endpoints novos

```text
GET  /ai-search/
GET  /ai-search/api/options
POST /ai-search/api/search
GET  /ai-search/api/trials/{trial_id}
GET  /ai-search/api/trials/{trial_id}/xml
POST /ai-search/api/export
```

## 6. DEBUG / PROD

Arquivo:

```text
rebec_ai/settings.py
```

Para teste:

```python
APP_MODE = "DEBUG"
```

Para produção:

```python
APP_MODE = "PROD"
```

Em DEBUG a interface recebe o log necessário para análise da busca. Em PROD,
os dados internos de debug não são enviados ao navegador.

## 7. Produção depois

Depois de validar, você pode eliminar `app_ai_test.py` e incluir o router no
`app.py` real. Veja `PATCH_APP_PRODUCAO.txt`.

## Segurança

O pacote novo não copia chave OpenAI nem senhas MySQL para os arquivos
adicionados. Durante o teste, `app_ai_test.py` reutiliza em memória o `config`
ja existente em `app.py`.
