import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT_ID",
]


def _check_env():
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        raise EnvironmentError(
            f"Variables d'environnement manquantes dans .env : {', '.join(missing)}"
        )


def get_llm_config() -> dict:
    """Construit la configuration AutoGen (llm_config) pour Azure OpenAI."""
    _check_env()

    config_list = [
        {
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_ID"),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
            "base_url": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_type": "azure",
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
            # Timeout par appel LLM (openai.APITimeoutError au-delà) : évite qu'un
            # appel bloqué ne fasse planter/geler un orchestrateur multi-agents.
            "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", 60)),
            # Dépassement du budget de tokens (erreurs 429) : "max_retries" est un
            # paramètre du client openai.AzureOpenAI lui-même (pas une invention
            # d'AutoGen) — le SDK réessaie alors automatiquement avec un backoff
            # exponentiel (en respectant l'en-tête Retry-After renvoyé par Azure)
            # au lieu de laisser planter l'appel dès la première erreur 429.
            "max_retries": int(os.getenv("LLM_MAX_RETRIES", 5)),
        }
    ]

    return {
        "config_list": config_list,
        "temperature": float(os.getenv("LLM_TEMPERATURE", 0.7)),
        # gpt-5.4 rejette "max_tokens" et exige "max_completion_tokens"
        "max_completion_tokens": int(os.getenv("LLM_MAX_TOKENS", 2000)),
    }
