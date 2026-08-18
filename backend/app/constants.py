DEFAULT_MODEL = "groq/compound-mini"
FREE_MODEL_IDS = {
    1: "groq/compound-mini",
    2: "groq/compound",
    3: "openai/gpt-oss-20b", # reasoning model, probably enough for this
    4: "qwen/qwen3.6-27b", # reasoning model, overkill for most CV questions
    5: "openai/gpt-oss-120b", # reasoning model, heaviest fallback, overkill
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