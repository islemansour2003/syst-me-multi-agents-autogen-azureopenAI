from protocol.loop_detection import CLARIFICATION_MARKER, LoopDetectionHook, LoopDetector


class FakeAgent:
    def __init__(self, name: str):
        self.name = name


# --- LoopDetector (logique pure) ---

def test_no_loop_on_progressing_conversation():
    detector = LoopDetector(max_rounds=10)
    status1 = detector.observe("reviseur", "Corrige la variable X.")
    status2 = detector.observe("reviseur", "Bien joué, il ne reste qu'un détail sur la gestion des erreurs.")
    assert status1.loop_detected is False
    assert status2.loop_detected is False


def test_detects_repetition_when_message_barely_changes():
    detector = LoopDetector(max_rounds=10, similarity_threshold=0.85)
    detector.observe("reviseur", "Il manque une gestion d'erreur pour b == 0.")
    status = detector.observe("reviseur", "Il manque une gestion d'erreur pour b==0.")
    assert status.loop_detected is True
    assert status.reason == "repetition"


def test_repetition_check_is_scoped_per_speaker():
    detector = LoopDetector(max_rounds=10)
    detector.observe("reviseur", "Corrige X.")
    status = detector.observe("codeur", "Corrige X.")  # locuteur différent : pas une répétition
    assert status.loop_detected is False


def test_detects_max_rounds_without_repetition():
    detector = LoopDetector(max_rounds=2)
    detector.observe("reviseur", "Premier avis, assez différent.")
    status = detector.observe("reviseur", "Un avis totalement différent cette fois-ci sur un autre point précis.")
    assert status.loop_detected is True
    assert status.reason == "max_rounds"


# --- LoopDetectionHook (intégration AutoGen) ---

def test_hook_leaves_message_untouched_before_loop_detected():
    hook = LoopDetectionHook(max_rounds=10, similarity_threshold=0.85)
    sender, recipient = FakeAgent("reviseur"), FakeAgent("codeur")

    message = hook(sender, {"content": "Il manque une gestion d'erreur pour b == 0."}, recipient, False)

    assert message["content"] == "Il manque une gestion d'erreur pour b == 0."
    assert hook.triggered is False


def test_hook_replaces_message_with_clarification_on_repetition():
    hook = LoopDetectionHook(max_rounds=10, similarity_threshold=0.85)
    sender, recipient = FakeAgent("reviseur"), FakeAgent("codeur")

    hook(sender, {"content": "Il manque une gestion d'erreur pour b == 0."}, recipient, False)
    message = hook(sender, {"content": "Il manque une gestion d'erreur pour b==0."}, recipient, False)

    assert CLARIFICATION_MARKER in message["content"]
    assert "TERMINATE" in message["content"]
    assert hook.triggered is True
    assert hook.reason == "repetition"


def test_hook_does_not_retrigger_after_first_detection():
    hook = LoopDetectionHook(max_rounds=10, similarity_threshold=0.85)
    sender, recipient = FakeAgent("reviseur"), FakeAgent("codeur")

    hook(sender, {"content": "A"}, recipient, False)
    hook(sender, {"content": "A"}, recipient, False)  # déclenche la détection
    assert hook.triggered is True

    message = hook(sender, {"content": "Un tout autre message"}, recipient, False)
    assert message["content"] == "Un tout autre message"  # plus de remplacement une fois déclenché


def test_hook_supports_plain_string_messages():
    hook = LoopDetectionHook(max_rounds=10, similarity_threshold=0.85)
    sender, recipient = FakeAgent("reviseur"), FakeAgent("codeur")

    hook(sender, "Corrige X.", recipient, False)
    message = hook(sender, "Corrige X.", recipient, False)

    assert isinstance(message, str)
    assert CLARIFICATION_MARKER in message
