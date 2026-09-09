# Copy to a local config if you prefer Python configuration.
# Do not commit real credentials.

REBEC_API_MODE = "DEV"

REBEC_MYSQL_HOST = "127.0.0.1"
REBEC_MYSQL_PORT = 3306
REBEC_MYSQL_USER = "your_mysql_user"
REBEC_MYSQL_PASSWORD = "your_mysql_password"
REBEC_MYSQL_DATABASE = "your_mysql_database"

REBEC_AI_LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
REBEC_AI_LLM_MODEL = "ggml-org/Qwen3.5-0.8B-GGUF:Q4_0"

OPENAI_API_KEY = ""

# Only if the legacy emergency-password endpoint is used:
REBEC_EMERGENCY_PASSWORD = ""
REBEC_EMERGENCY_PASSWORD_HASH = ""
