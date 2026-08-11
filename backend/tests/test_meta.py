EXPECTED_CROPS = {"tomato", "potato", "corn", "apple"}
EXPECTED_CONDITION_COUNT = 21  # PlantVillage class count for the 4-crop subset


def test_supported_crops_matches_taxonomy_config(client):
    response = client.get("/supported-crops")
    assert response.status_code == 200
    body = response.json()
    assert {c["crop_id"] for c in body["crops"]} == EXPECTED_CROPS
    total_conditions = sum(len(c["conditions"]) for c in body["crops"])
    assert total_conditions == EXPECTED_CONDITION_COUNT


def test_supported_crops_reports_model_available_honestly(client):
    body = client.get("/supported-crops").json()
    # Flipped False->True 2026-08-11 (own commit) on LIVE real-checkpoint serving evidence:
    # worker job 39bec3e6 loaded runs/20260808-180238-0.1.0/checkpoint.pt via MODEL_CHECKPOINT
    # (no DEMO warning), analysis 6144ff30-5ecb-425a-a816-34a1d9eefb41 yielded prediction
    # demo=false, SUSPECTED, 0.4311 (LOW band); model_versions registers v0.1.0 demo=false
    # plantvillage@v1. "Available" requires live evidence in the repo — that is what this pins.
    assert body["model_available"] is True


def test_supported_flags_true_after_published_evaluation(client):
    """Reviewed support-rule flip 2026-08-09: reports/model_evaluation/summary.json shows
    every class held-out F1 >= 0.90 with support >= 20 (run 20260808-180238-0.1.0)."""
    body = client.get("/supported-crops").json()
    assert all(
        cond["supported_by_model"]
        for crop in body["crops"]
        for cond in crop["conditions"]
    )
    assert body["taxonomy_version"] == "0.3"  # 0.2 = supported_by_model flip; 0.3 = live-serving flip 2026-08-11


def test_model_info_reports_promoted_baseline(client):
    body = client.get("/model-info").json()
    # EVALUATED -> PROMOTED 2026-08-11 (own commit): the config's own rule is "PROMOTED
    # when the serving stack loads it" — worker job 39bec3e6 served analysis 6144ff30
    # with prediction demo=false. Band set ("0.1") unchanged: gates were not adjusted.
    assert body["model"]["status"] == "PROMOTED"
    assert body["model"]["version"] == "0.1.0"
    bands = body["confidence_bands"]
    assert 0 < bands["low"] < bands["medium"] < bands["high"] < 1
