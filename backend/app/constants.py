DEFAULT_MODEL = "llama-3.1-8b-instant"
FREE_MODEL_IDS = {
    1: "llama-3.1-8b-instant",
    2: "llama-3.3-70b-versatile",
    3: "groq/compound",
    4: "groq/compound-mini",
    5: "openai/gpt-oss-20b", # reasoning model. Probably overkill for this
    6: "openai/gpt-oss-120b", # reasoning model
    7: "qwen/qwen3.6-27b", # reasoning model
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