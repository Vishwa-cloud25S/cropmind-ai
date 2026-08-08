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
    assert body["model_available"] is False  # baseline model lands in Phase 3
    assert all(
        not cond["supported_by_model"]
        for crop in body["crops"]
        for cond in crop["conditions"]
    )


def test_model_info_declares_not_trained(client):
    body = client.get("/model-info").json()
    assert body["model"]["status"] == "NOT_TRAINED"
    bands = body["confidence_bands"]
    assert 0 < bands["low"] < bands["medium"] < bands["high"] < 1
