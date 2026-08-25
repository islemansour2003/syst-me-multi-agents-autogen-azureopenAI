"""
Benchmarks de performance (US 11) sur les parties déterministes du système —
routage, détection de boucle, résumé progressif, journalisation. Ce sont les
seules parties dont la latence dépend de *notre* code : le reste (temps de
réponse d'un agent) est dominé par la latence du modèle Azure OpenAI, qui n'a
pas de sens à "benchmarker" côté client (cf. scripts/benchmark_real_llm.py
pour une mesure de latence réelle, en opt-in, hors suite automatisée).

Lancer avec le détail des résultats : py -m pytest tests/test_performance.py -v
"""
from protocol.logger import CommunicationLogger
from protocol.loop_detection import LoopDetector
from protocol.memory import ProgressiveSummaryTransform
from protocol.pre_step import detect_needs
from protocol.router import route_request


# --- Latence / throughput : routage et détection de besoins ---

def test_benchmark_detect_needs(benchmark):
    result = benchmark(detect_needs, "Recherche des infos sur HTTP et analyse ces valeurs : 10, 20, 30.")
    assert result.besoin_recherche is True


def test_benchmark_route_request(benchmark):
    result = benchmark(route_request, "Écris une fonction Python qui trie une liste.")
    assert result.route == "developpement"


# --- Latence / throughput : détection de boucle ---

def test_benchmark_loop_detector_observe(benchmark):
    detector = LoopDetector(max_rounds=10_000)  # évite de déclencher pendant le benchmark

    def run():
        return detector.observe("reviseur", "Un avis de longueur réaliste sur un extrait de code Python.")

    benchmark(run)


# --- Latence / throughput : résumé progressif (hors appel LLM réel) ---

def test_benchmark_progressive_summary_transform(benchmark):
    messages = [{"role": "user", "content": f"Message numéro {i} de la conversation."} for i in range(20)]
    transform = ProgressiveSummaryTransform(
        max_messages=10,
        keep_recent=6,
        summarizer_fn=lambda msgs, prev: "Résumé simulé (le vrai résumeur appelle Azure OpenAI).",
    )

    result = benchmark(transform.apply_transform, messages)
    assert len(result) == 7


# --- Latence / throughput : journalisation (écriture disque réelle) ---

def test_benchmark_communication_logger_write(benchmark, tmp_path):
    logger = CommunicationLogger(log_path=str(tmp_path / "bench.jsonl"))

    class FakeAgent:
        def __init__(self, name):
            self.name = name

    sender, recipient = FakeAgent("codeur"), FakeAgent("reviseur")
    message = {"content": "```python\ndef exemple():\n    return 42\n```"}

    def run():
        return logger._log_hook(sender, message, recipient, False)

    benchmark(run)
