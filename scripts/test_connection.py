"""
Valide la configuration Azure OpenAI + AutoGen (US 1.1 / 1.2).
Usage: python scripts/test_connection.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from config.azure_config import get_llm_config
from autogen import ConversableAgent


def test_raw_api_connection(llm_config: dict):
    from openai import AzureOpenAI

    cfg = llm_config["config_list"][0]
    client = AzureOpenAI(
        api_key=cfg["api_key"],
        azure_endpoint=cfg["base_url"],
        api_version=cfg["api_version"],
    )
    response = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": "Réponds uniquement par: OK"}],
        max_completion_tokens=10,
    )
    print(f"[Azure OpenAI] Connexion réussie -> {response.choices[0].message.content.strip()}")


def test_autogen_conversable_agent(llm_config: dict):
    assistant = ConversableAgent(
        name="assistant",
        llm_config=llm_config,
        system_message="Tu es un agent de test. Réponds brièvement.",
    )
    user_proxy = ConversableAgent(
        name="user_proxy",
        llm_config=False,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        is_termination_msg=lambda msg: "TERMINATE" in msg.get("content", ""),
        code_execution_config=False,
    )

    result = user_proxy.initiate_chat(
        assistant,
        message="Confirme que la configuration AutoGen + Azure OpenAI fonctionne, puis dis TERMINATE.",
        max_turns=1,
    )
    print("[AutoGen] Échange ConversableAgent réussi.")
    print(result.chat_history[-1]["content"])


if __name__ == "__main__":
    print("Chargement de la configuration Azure OpenAI...")
    config = get_llm_config()
    print(f"Modèle configuré : {config['config_list'][0]['model']}")
    print(f"Temperature : {config['temperature']} | Max tokens : {config['max_completion_tokens']}\n")

    test_raw_api_connection(config)
    test_autogen_conversable_agent(config)

    print("\nEnvironnement AutoGen + Azure OpenAI validé avec succès.")
