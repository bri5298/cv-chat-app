DEFAULT_MODEL = "openai/gpt-oss-20b"
FREE_MODEL_IDS = {
    1: "openai/gpt-oss-20b", # reasoning model, but reasoning not used
    2: "qwen/qwen3.8-27b", # reasoning model, overkill for most CV questions
    3: "openai/gpt-oss-120b", # reasoning model, heaviest fallback, overkill
}


FALLBACK_MODEL_IDS = list(FREE_MODEL_IDS.values())
FALLBACK_ERROR_TERMS = (
    "context",
    "token",
    "too large",
    "maximum",
    "limit",
)

TEMPERATURE = 0.1
ANSWER_MAX_TOKENS = 400
MAX_HISTORY_USER_MESSAGES = 4