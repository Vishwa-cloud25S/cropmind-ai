"""Farms/fields CRUD (Phase 6 backend surface) + analysis list + Grad-CAM serving.

crop_id is validated against the published taxonomy (never a free-text crop);
deletes are honest 409 conflicts while children reference the row.
"""

from __future__ import annotations

from app.workers.analysis_worker import tick
from tests.test_analysis_flow import StubPredictor, _contract, _handle, _jpeg_bytes


def _make_farm(client, name="Dell Farm") -> dict:
    resp = client.post("/farms", json={"name": name, "location": "Shropshire"})
    assert resp.status_code == 201, resp.text
    return resp.json()["farm"]


def test_farm_crud_happy_path(client) -> None:
    farm = _make_farm(client)
    assert farm["field_count"] == 0 and farm["location"] == "Shropshire"

    listing = client.get("/farms").json()
    assert listing["count"] == 1 and listing["farms"][0]["id"] == farm["id"]

    patched = client.patch(f"/farms/{farm['id']}", json={"name": "Dell Farm North"})
    assert patched.status_code == 200 and patched.json()["farm"]["name"] == "Dell Farm North"

    gone = client.delete(f"/farms/{farm['id']}")
    assert gone.status_code == 204
    assert client.get(f"/farms/{farm['id']}").status_code == 404


def test_field_crud_and_taxonomy_validation(client) -> None:
    farm = _make_farm(client)
    bad = client.post(f"/farms/{farm['id']}/fields", json={"name": "West 1", "crop_id": "wheat"})
    assert bad.status_code == 400
    assert "allowed" in bad.json()["detail"]
    assert set(bad.json()["detail"]["allowed"]) == {"apple", "corn", "potato", "tomato"}

    created = client.post(
        f"/farms/{farm['id']}/fields", json={"name": "West 1", "crop_id": "corn", "area_ha": 4.2}
    )
    assert created.status_code == 201, created.text
    field = created.json()["field"]
    assert field["crop_id"] == "corn" and field["area_ha"] == 4.2

    detail = client.get(f"/farms/{farm['id']}").json()
    assert [f["id"] for f in detail["fields"]] == [field["id"]]
    assert detail["farm"]["field_count"] == 1

    patched = client.patch(f"/fields/{field['id']}", json={"crop_id": "potato", "area_ha": 3.5})
    assert patched.status_code == 200 and patched.json()["field"]["crop_id"] == "potato"

    blocked = client.delete(f"/farms/{farm['id']}")  # has a field → honest 409
    assert blocked.status_code == 409 and blocked.json()["detail"]["field_count"] == 1

    assert client.delete(f"/fields/{field['id']}").status_code == 204
    assert client.delete(f"/farms/{farm['id']}").status_code == 204  # now empty → allowed


def test_delete_field_blocked_by_referencing_image(client) -> None:
    farm = _make_farm(client)
    field = client.post(f"/farms/{farm['id']}/fields", json={"name": "West 1"}).json()["field"]
    up = client.post("/images", files={"file": ("leaf.jpg", _jpeg_bytes(), "image/jpeg")},
                     params={"field_id": field["id"]})
    assert up.status_code == 201
    blocked = client.delete(f"/fields/{field['id']}")
    assert blocked.status_code == 409 and blocked.json()["detail"]["image_count"] == 1


def test_unknown_parent_404s(client) -> None:
    assert client.post("/farms/nope/fields", json={"name": "x"}).status_code == 404
    assert client.get("/farms/nope").status_code == 404
    assert client.patch("/farms/nope", json={"name": "x"}).status_code == 404
    assert client.delete("/farms/nope").status_code == 404
    assert client.get("/fields/nope").status_code == 404


def _completed_analysis(client, tmp_path) -> str:
    up = client.post("/images", files={"file": ("leaf.jpg", _jpeg_bytes(), "image/jpeg")})
    image_id = up.json()["image"]["id"]
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    assert tick("w", handle=_handle(StubPredictor(_contract()), tmp_path)) == 1
    return analysis_id


def test_list_analyses_newest_first(client, tmp_path) -> None:
    empty = client.get("/analyses").json()
    assert empty["count"] == 0

    first = _completed_analysis(client, tmp_path)
    second = _completed_analysis(client, tmp_path)
    body = client.get("/analyses").json()
    assert body["count"] == 2
    ids = [a["analysis_id"] for a in body["analyses"]]
    assert ids == sorted(ids, key=lambda a: body["analyses"][ids.index(a)]["created_at"], reverse=True) or ids[0] == second
    assert all(a["status"] == "COMPLETED" for a in body["analyses"])
    assert body["analyses"][0]["job"]["attempts"] == 1

    filtered = client.get("/analyses", params={"status": "FAILED"}).json()
    assert filtered["count"] == 0
    assert client.get("/analyses", params={"status": "BOGUS"}).status_code == 400
    assert client.get("/analyses", params={"limit": 1}).json()["count"] == 1
    assert first in [a["analysis_id"] for a in client.get("/analyses").json()["analyses"]]


def test_gradcam_served_after_completion(client, tmp_path) -> None:
    analysis_id = _completed_analysis(client, tmp_path)
    resp = client.get(f"/analyses/{analysis_id}/gradcam")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content[:4] == b"\x89PNG"

    # QUEUED/unknown analyses must not serve one
    up = client.post("/images", files={"file": ("leaf2.jpg", _jpeg_bytes((32, 24)), "image/jpeg")})
    queued = client.post("/analyses", json={"image_id": up.json()["image"]["id"]}).json()["analysis_id"]
    assert client.get(f"/analyses/{queued}/gradcam").status_code == 409
    assert client.get("/analyses/nope/gradcam").status_code == 404
