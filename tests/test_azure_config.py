from config.azure_config import get_llm_config


REQUIRED_ENV = {
    "AZURE_OPENAI_API_KEY": "fake-key",
    "AZURE_OPENAI_ENDPOINT": "https://fake.openai.azure.com",
    "AZURE_OPENAI_API_VERSION": "2025-01-01-preview",
    "AZURE_OPENAI_DEPLOYMENT_ID": "gpt-4o",
}


def _set_required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_get_llm_config_sets_default_max_retries(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)

    config = get_llm_config()

    assert config["config_list"][0]["max_retries"] == 5


def test_get_llm_config_reads_max_retries_from_env(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LLM_MAX_RETRIES", "8")

    config = get_llm_config()

    assert config["config_list"][0]["max_retries"] == 8
