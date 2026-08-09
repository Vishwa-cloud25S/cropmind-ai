EXPECTED_CROPS = {"tomato", "potato", "corn", "apple"}
EXPECTED_CONDITION_COUNT = 21  # PlantVillage class count for the 4-crop subset


def test_supported_crops_matches_taxonomy_config(client):
    response = client.get("/supported-crops")
    assert response.status_code == 200
    body = response.json()
    assert {c["crop_id"] for c in body["crops"]} == EXPECTED_CROPS
    total_conditions = sum(len(c["conditions"]) for c in body["crops"])
    assert total_conditions == EXPECTED_CONDITION_COUNT


def test_supported_crops_reports_model_unavailable_honestly(client):
    body = client.get("/supported-crops").json()
    # Stays False until the serving stack loads the checkpoint (Phase 5) — even though a
    # trained, evaluated run exists operator-locally. "Available" means wired LIVE.
    assert body["model_available"] is False


def test_supported_flags_true_after_published_evaluation(client):
    """Reviewed support-rule flip 2026-08-09: reports/model_evaluation/summary.json shows
    every class held-out F1 >= 0.90 with support >= 20 (run 20260808-180238-0.1.0)."""
    body = client.get("/supported-crops").json()
    assert all(
        cond["supported_by_model"]
        for crop in body["crops"]
        for cond in crop["conditions"]
    )
    assert body["taxonomy_version"] == "0.2"


def test_model_info_reports_evaluated_baseline(client):
    body = client.get("/model-info").json()
    # EVALUATED, not PROMOTED: gates measured (docs/06 §4.2); serving stack loads it in Phase 5.
    assert body["model"]["status"] == "EVALUATED"
    assert body["model"]["version"] == "0.1.0"
    bands = body["confidence_bands"]
    assert 0 < bands["low"] < bands["medium"] < bands["high"] < 1
