"""Predictions read surface: list ordering, get-by-id, 404s, and the standing
client notice on every response.
"""

from __future__ import annotations

from app.workers.analysis_worker import tick
from tests.test_analysis_flow import StubPredictor, _contract, _handle, _jpeg_bytes


def _make_prediction(client, tmp_path) -> dict:
    up = client.post("/images", files={"file": ("leaf.jpg", _jpeg_bytes(), "image/jpeg")})
    image_id = up.json()["image"]["id"]
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    assert tick("w", handle=_handle(StubPredictor(_contract()), tmp_path)) == 1
    return client.get(f"/analyses/{analysis_id}/prediction").json()


def test_list_predictions_empty(client) -> None:
    resp = client.get("/predictions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0 and body["predictions"] == []
    assert "human verification" in body["client_notice"]


def test_list_and_get_prediction(client, tmp_path) -> None:
    pred = _make_prediction(client, tmp_path)
    listed = client.get("/predictions").json()
    assert listed["count"] == 1
    assert listed["predictions"][0]["prediction_id"] == pred["prediction_id"]
    assert listed["predictions"][0]["phrasing"].startswith("Suspected ")

    got = client.get(f"/predictions/{pred['prediction_id']}")
    assert got.status_code == 200
    assert got.json()["crop"] == "corn"
    assert got.json()["condition"]["disease_id"] == "corn_northern_leaf_blight"


def test_get_prediction_404(client) -> None:
    assert client.get("/predictions/nope").status_code == 404


def test_list_respects_limit(client, tmp_path) -> None:
    _make_prediction(client, tmp_path)
    _make_prediction(client, tmp_path)  # same image bytes → dedupe is fine; two analyses
    body = client.get("/predictions", params={"limit": 1}).json()
    assert body["count"] == 1
    assert len(body["predictions"]) == 1
