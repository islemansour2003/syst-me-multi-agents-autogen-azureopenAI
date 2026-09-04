from protocol.tracing import get_trace_id, new_trace_id, trace_context


def test_get_trace_id_is_none_outside_any_context():
    assert get_trace_id() is None


def test_trace_context_sets_and_resets_trace_id():
    assert get_trace_id() is None
    with trace_context() as trace_id:
        assert trace_id is not None
        assert get_trace_id() == trace_id
    assert get_trace_id() is None


def test_trace_context_accepts_explicit_id():
    with trace_context("mon-id-fixe") as trace_id:
        assert trace_id == "mon-id-fixe"
        assert get_trace_id() == "mon-id-fixe"


def test_new_trace_id_generates_distinct_ids():
    ids = {new_trace_id() for _ in range(100)}
    assert len(ids) == 100  # pas de collision sur 100 générations


def test_nested_trace_contexts_restore_outer_id():
    with trace_context("exterieur") as outer_id:
        with trace_context("interieur") as inner_id:
            assert get_trace_id() == inner_id
        assert get_trace_id() == outer_id
