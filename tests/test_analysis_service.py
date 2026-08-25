import pytest

from services.analysis_service import compute_statistics, detect_anomalies


def test_compute_statistics_basic():
    stats = compute_statistics([1, 2, 3, 4, 5])
    assert stats["count"] == 5
    assert stats["mean"] == 3
    assert stats["median"] == 3
    assert stats["min"] == 1
    assert stats["max"] == 5


def test_compute_statistics_raises_on_empty_list():
    with pytest.raises(ValueError):
        compute_statistics([])


def test_detect_anomalies_flags_outlier():
    data = [10, 11, 9, 10, 12, 100]  # 100 est clairement une anomalie
    anomalies = detect_anomalies(data, threshold=2.0)
    assert len(anomalies) == 1
    assert anomalies[0].index == 5
    assert anomalies[0].value == 100


def test_detect_anomalies_no_outliers_in_uniform_data():
    assert detect_anomalies([10, 10, 10, 10, 10]) == []


def test_detect_anomalies_returns_empty_for_short_data():
    assert detect_anomalies([5]) == []
    assert detect_anomalies([]) == []
