from dragonscales.ui_app import create_app
from dragonscales import ui_app


def test_ui_auth_blocks_without_key():
    app = create_app(api_key="secret", checkpoint_dir=None)
    client = app.test_client()

    resp_root = client.get("/")
    assert resp_root.status_code == 200

    resp = client.get("/experts")
    assert resp.status_code == 401


def test_ui_allows_with_api_key(monkeypatch):
    app = create_app(api_key="secret", checkpoint_dir=None)
    client = app.test_client()

    class DummyModel:
        def __init__(self, model_id):
            self.id = model_id
            self.name = f"Model {model_id}"
            self.description = "desc"

    def fake_build_dragon():
        class D:
            def refresh_models(self, force=False):
                return [DummyModel("m1")]

        return D()

    monkeypatch.setattr("dragonscales.ui_app.build_dragon", fake_build_dragon)

    resp = client.get("/experts", headers={"X-API-Key": "secret"})
    assert resp.status_code == 200
    assert resp.get_json()[0]["id"] == "m1"

    resp_select = client.post("/select", headers={"X-API-Key": "secret"})
    assert resp_select.status_code == 200
    assert resp_select.get_json()["selected_expert"] == "m1"


def test_ui_serves_html(monkeypatch):
    app = create_app(api_key="secret", checkpoint_dir=None)
    client = app.test_client()

    monkeypatch.setattr("dragonscales.ui_app.build_dragon", lambda: None)

    resp = client.get("/", headers={"X-API-Key": "secret"})
    assert resp.status_code == 200
    assert b"Mixture of Experts" in resp.data


def test_self_signed_detection(monkeypatch):
    def fake_decode(path):
        return {"subject": "X", "issuer": "X"}

    monkeypatch.setattr(ui_app.ssl._ssl, "_test_decode_cert", fake_decode, raising=False)  # type: ignore[attr-defined]

    assert ui_app._is_self_signed("dummy") is True
