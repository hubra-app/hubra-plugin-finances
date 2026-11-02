"""The example plugin: its API, permissions and the module switch.

Runs with Hubra's fixtures (client, auth_headers, db, seeded_db) once the
plugin is cloned into plugins/<id> of a Hubra checkout; see README.md.
"""

from __future__ import annotations

from tests.helpers import set_modules


def test_notes_round_trip(client, auth_headers):
    set_modules(True, "example")
    resp = client.post("/api/v1/example/notes", json={"text": "Hello club"})
    assert resp.status_code == 201
    note = resp.get_json()
    assert note["text"] == "Hello club"

    listed = client.get("/api/v1/example/notes").get_json()
    assert [n["text"] for n in listed] == ["Hello club"]

    assert client.delete(f"/api/v1/example/notes/{note['id']}").status_code == 204
    assert client.get("/api/v1/example/notes").get_json() == []


def test_empty_note_is_refused(client, auth_headers):
    set_modules(True, "example")
    resp = client.post("/api/v1/example/notes", json={"text": "  "})
    assert resp.status_code == 400


def test_module_off_hides_the_api(client, auth_headers):
    set_modules(False, "example")
    resp = client.get("/api/v1/example/notes")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "MODULE_DISABLED"
