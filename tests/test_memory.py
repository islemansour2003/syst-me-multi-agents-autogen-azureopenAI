import pytest
from autogen import AssistantAgent

from protocol.memory import LongTermMemory, ProgressiveSummaryTransform, attach_memory_management


def make_messages(n: int, prefix: str = "msg") -> list:
    return [{"role": "user", "content": f"{prefix} {i}", "name": "quelqu_un"} for i in range(n)]


# --- LongTermMemory ---

def test_long_term_memory_remember_and_recall(tmp_path):
    memory = LongTermMemory(path=str(tmp_path / "memory.json"))
    memory.remember("objectif", "Construire une API météo.")
    assert memory.recall("objectif") == "Construire une API météo."
    assert memory.recall("inexistant") is None


def test_long_term_memory_persists_across_instances(tmp_path):
    path = str(tmp_path / "memory.json")
    LongTermMemory(path=path).remember("cle", "valeur")
    # Une nouvelle instance pointant sur le même fichier doit retrouver la donnée.
    assert LongTermMemory(path=path).recall("cle") == "valeur"


def test_long_term_memory_forget_removes_key(tmp_path):
    memory = LongTermMemory(path=str(tmp_path / "memory.json"))
    memory.remember("cle", "valeur")
    memory.forget("cle")
    assert memory.recall("cle") is None


def test_long_term_memory_all_returns_everything(tmp_path):
    memory = LongTermMemory(path=str(tmp_path / "memory.json"))
    memory.remember("a", 1)
    memory.remember("b", 2)
    assert memory.all() == {"a": 1, "b": 2}


# --- ProgressiveSummaryTransform ---

def test_transform_leaves_short_history_untouched():
    transform = ProgressiveSummaryTransform(max_messages=10, keep_recent=6, summarizer_fn=lambda msgs, prev: "RESUME")
    messages = make_messages(5)
    assert transform.apply_transform(messages) == messages


def test_transform_summarizes_when_over_threshold():
    calls = []

    def fake_summarizer(msgs, prev):
        calls.append((msgs, prev))
        return "Résumé : objectif initial = construire une API météo."

    transform = ProgressiveSummaryTransform(max_messages=10, keep_recent=6, summarizer_fn=fake_summarizer)
    messages = make_messages(12)

    result = transform.apply_transform(messages)

    assert len(result) == 1 + 6  # 1 message de résumé + 6 récents
    assert result[0]["role"] == "system"
    assert "Résumé" in result[0]["content"]
    assert result[1:] == messages[-6:]

    # Le résumeur a bien reçu les messages les plus anciens (les 6 premiers sur 12).
    resumed_msgs, previous = calls[0]
    assert resumed_msgs == messages[:6]
    assert previous is None


def test_transform_is_progressive_across_calls():
    calls = []

    def fake_summarizer(msgs, prev):
        calls.append(prev)
        return f"résumé#{len(calls)}"

    transform = ProgressiveSummaryTransform(max_messages=10, keep_recent=6, summarizer_fn=fake_summarizer)

    transform.apply_transform(make_messages(12))
    transform.apply_transform(make_messages(14, prefix="msg2"))

    assert calls[0] is None
    assert calls[1] == "résumé#1"  # le 2e résumé part bien du précédent


def test_transform_rejects_invalid_keep_recent():
    with pytest.raises(ValueError):
        ProgressiveSummaryTransform(max_messages=5, keep_recent=5)


def test_transform_get_logs_reports_effect():
    transform = ProgressiveSummaryTransform(max_messages=10, keep_recent=6, summarizer_fn=lambda m, p: "R")
    pre = make_messages(12)
    post = transform.apply_transform(pre)

    log_msg, had_effect = transform.get_logs(pre, post)
    assert had_effect is True
    assert "Résumé progressif appliqué" in log_msg

    log_msg2, had_effect2 = transform.get_logs(pre[:3], pre[:3])
    assert had_effect2 is False


def test_transform_persists_summary_to_long_term_memory(tmp_path):
    memory = LongTermMemory(path=str(tmp_path / "memory.json"))
    transform = ProgressiveSummaryTransform(
        max_messages=10,
        keep_recent=6,
        summarizer_fn=lambda m, p: "résumé persistant",
        long_term_memory=memory,
        memory_key="conversation_test",
    )

    transform.apply_transform(make_messages(12))

    assert memory.recall("conversation_test") == "résumé persistant"


# --- Intégration avec un agent AutoGen ---

def test_attach_memory_management_registers_hook_and_triggers_summary():
    agent = AssistantAgent(name="codeur_test", llm_config=False)

    transform = attach_memory_management(
        agent,
        max_messages=10,
        keep_recent=6,
        summarizer_fn=lambda msgs, prev: "résumé injecté",
    )

    assert len(agent.hook_lists["process_all_messages_before_reply"]) == 1

    messages = make_messages(12)
    processed = agent.process_all_messages_before_reply(messages)

    assert len(processed) == 7  # 1 résumé + 6 récents
    assert "résumé injecté" in processed[0]["content"]
    assert transform.running_summary == "résumé injecté"


def test_attach_memory_management_default_key_is_agent_name(tmp_path):
    memory = LongTermMemory(path=str(tmp_path / "memory.json"))
    agent = AssistantAgent(name="reviseur_test", llm_config=False)

    attach_memory_management(
        agent,
        max_messages=10,
        keep_recent=6,
        summarizer_fn=lambda msgs, prev: "résumé",
        long_term_memory=memory,
    )
    agent.process_all_messages_before_reply(make_messages(12))

    assert memory.recall("reviseur_test") == "résumé"
