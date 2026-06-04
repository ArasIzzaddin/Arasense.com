"""Tests for the validation evidence-pack generator (pure parts, no network)."""

import pytest

from validation.evidence_pack import (
    EMILIA_ROMAGNA_2023,
    build_evidence_pack,
    categorical_scores,
    render_markdown,
)


def test_categorical_scores_known_matrix():
    # TP=30, FP=10, FN=20, TN=40
    s = categorical_scores(30, 10, 20, 40)
    assert s["precision"] == pytest.approx(0.75)        # 30/40
    assert s["pod_recall"] == pytest.approx(0.60)       # 30/50
    assert s["far"] == pytest.approx(0.25)              # 10/40
    assert s["csi_iou"] == pytest.approx(0.50)          # 30/60
    assert s["f1"] == pytest.approx(60 / 90)            # 2*30/(60+10+20)
    assert s["frequency_bias"] == pytest.approx(0.80)   # 40/50
    assert s["accuracy"] == pytest.approx(0.70)         # 70/100


def test_categorical_scores_undefined_are_none():
    # No predictions and no observations -> precision/POD undefined.
    s = categorical_scores(0, 0, 0, 100)
    assert s["precision"] is None
    assert s["pod_recall"] is None
    assert s["far"] is None
    assert s["csi_iou"] is None
    assert s["accuracy"] == pytest.approx(1.0)


def test_far_is_complement_of_precision():
    s = categorical_scores(7, 3, 5, 11)
    assert s["far"] + s["precision"] == pytest.approx(1.0)


def _fake_response():
    return {
        "counts": {"true_positive": 30, "false_positive": 10,
                   "false_negative": 20, "true_negative": 40},
        "best_model": "EC-Earth3",
        "trusted_models": ["EC-Earth3", "MPI-ESM1-2-HR"],
        "trust_weights": [0.6, 0.4],
        "precip_mean": 18.3, "precip_spread": 2.1,
        "trust_summary": {"n_kept": 2, "n_models": 5},
        "sentinel_image_count": 4, "grid_shape": [10, 10], "threshold": 0.5,
    }


def test_build_evidence_pack_structure():
    pack = build_evidence_pack(EMILIA_ROMAGNA_2023, _fake_response())
    assert pack["case"].startswith("Emilia-Romagna")
    assert pack["confusion"] == {"tp": 30, "fp": 10, "fn": 20, "tn": 40}
    assert pack["scores"]["csi_iou"] == pytest.approx(0.5)
    assert pack["climate"]["n_kept"] == 2
    assert pack["climate"]["trusted_models"] == ["EC-Earth3", "MPI-ESM1-2-HR"]


def test_render_markdown_contains_key_numbers():
    pack = build_evidence_pack(EMILIA_ROMAGNA_2023, _fake_response())
    md = render_markdown(pack)
    assert "Validation Evidence Pack" in md
    assert "Critical Success Index" in md
    assert "50.0%" in md          # CSI/IoU
    assert "EC-Earth3" in md      # best model surfaced
    assert "2/5" in md            # trusted models kept


def test_case_to_request_roundtrip():
    req = EMILIA_ROMAGNA_2023.to_request()
    assert set(req) >= {"lat", "lon", "radius_km", "start_date", "end_date",
                        "sentinel_start_date", "sentinel_end_date",
                        "scale", "threshold", "fast_mode"}
    assert req["lat"] == EMILIA_ROMAGNA_2023.lat
