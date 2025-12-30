"""HTTPS-enabled UI server for the mixture-of-experts router."""

from __future__ import annotations

import os
import ssl
import warnings
import threading
import random
import time
from typing import Any, Generator

from flask import Flask, Response, jsonify, request

from dragonscales.__main__ import build_dragon
from dragonscales.config import load_settings
from dragonscales.router import Expert, LocalFileStorage, UCBRouter


def require_api_key(app: Flask, key: str) -> None:
    @app.before_request
    def _check_api_key() -> Response | None:
        if request.path in ("/", "/favicon.ico"):
            return None
        provided = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace(
            "Bearer ", ""
        )
        if not key or provided != key:
            return Response("Unauthorized", status=401)
        return None


def create_app(api_key: str, checkpoint_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    require_api_key(app, api_key)

    training_state = {
        "running": False,
        "step": 0,
        "loss_history": [],
    }
    training_lock = threading.Lock()

    def _sample_text_iter() -> Generator[str, None, None]:
        sample = (
            "In the ancient archives of the DragonScales project, engineers etched notes about routing models. "
            "Each free LLM expert contributed insights, and the router learned to balance them.\n"
        ) * 50
        for paragraph in sample.split("\n"):
            yield paragraph

    def _chunk_generator(chunk_size: int = 512, overlap: int = 32) -> Generator[str, None, None]:
        buf = ""
        for piece in _sample_text_iter():
            if not isinstance(piece, str):
                continue
            piece = " ".join(piece.split())
            buf += piece + "\n"
            while len(buf) >= chunk_size:
                yield buf[:chunk_size]
                buf = buf[chunk_size - overlap :] if overlap else buf[chunk_size :]
        if buf:
            yield buf

    chunk_iter = _chunk_generator()

    def _next_chunk() -> str:
        nonlocal chunk_iter
        try:
            return next(chunk_iter)
        except StopIteration:
            chunk_iter = _chunk_generator()
            return next(chunk_iter)

    def _simulate_training():
        nonlocal training_state
        with training_lock:
            training_state["running"] = True
            training_state["step"] = 0
            training_state["loss_history"] = []
        for step in range(1, 51):
            chunk = _next_chunk()
            _ = len(chunk)  # placeholder for real training input
            loss = max(0.01, 2.0 * (0.95 ** step) + random.uniform(-0.05, 0.05))
            with training_lock:
                training_state["step"] = step
                training_state["loss_history"].append({"step": step, "loss": round(loss, 4)})
            time.sleep(0.05)
        with training_lock:
            training_state["running"] = False

    @app.get("/")
    def index() -> Response:
        html = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8"/>
            <title>DragonScales MoE Router</title>
            <style>
                body { font-family: sans-serif; margin: 2rem; background: #0b0f16; color: #e5e7eb; }
                h1 { margin-bottom: 0.5rem; }
                button { padding: 0.5rem 1rem; background: #2563eb; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background: #1d4ed8; }
                pre { background: #111827; padding: 1rem; border-radius: 6px; overflow-x: auto; }
                .status { margin-top: 1rem; }
                input { padding: 0.4rem; border-radius: 4px; border: 1px solid #1f2937; margin-right: 0.5rem; background: #111827; color: #e5e7eb; }
            </style>
        </head>
        <body>
            <h1>DragonScales Mixture of Experts</h1>
            <p>This UI lists free experts and selects a recommended one via the router.</p>
            <div>
                <input id="apiKeyInput" type="password" placeholder="API key" />
                <button onclick="saveKey()">Save API Key</button>
            </div>
            <button onclick="loadExperts()">Load Free Experts</button>
            <button onclick="selectExpert()">Select Expert</button>
            <div class="status">
                <h3>Experts</h3>
                <pre id="experts"></pre>
                <h3>Selection</h3>
                <pre id="selection"></pre>
                <h3>Router Training</h3>
                <button onclick="startTraining()">Start Training</button>
                <div id="train-status"></div>
                <canvas id="lossChart" width="600" height="240"></canvas>
            </div>
            <script>
                function currentHeaders() {
                    const key = localStorage.getItem("dragon_api_key") || "";
                    return {"X-API-Key": key};
                }
                function saveKey() {
                    const val = document.getElementById("apiKeyInput").value;
                    if (val) {
                        localStorage.setItem("dragon_api_key", val);
                        alert("Saved API key");
                    }
                }
                function loadExperts() {
                    fetch("/experts", {headers: currentHeaders()}).then(r => r.json()).then(data => {
                        document.getElementById("experts").textContent = JSON.stringify(data, null, 2);
                    }).catch(err => alert(err));
                }
                function selectExpert() {
                    fetch("/select", {method:"POST", headers: currentHeaders()}).then(r => r.json()).then(data => {
                        document.getElementById("selection").textContent = JSON.stringify(data, null, 2);
                    }).catch(err => alert(err));
                }
                document.getElementById("apiKeyInput").value = localStorage.getItem("dragon_api_key") || "";

                function startTraining() {
                    fetch("/train/start", {method:"POST", headers: currentHeaders()})
                      .then(r => r.json())
                      .then(data => {
                        document.getElementById("train-status").textContent = JSON.stringify(data, null, 2);
                      });
                }

                function pollStatus() {
                    fetch("/train/status", {headers: currentHeaders()})
                      .then(r => r.json())
                      .then(data => {
                        document.getElementById("train-status").textContent = JSON.stringify(data, null, 2);
                        drawLoss(data.loss_history || []);
                      })
                      .catch(() => {});
                }
                setInterval(pollStatus, 1500);

                function drawLoss(history) {
                    const canvas = document.getElementById("lossChart");
                    const ctx = canvas.getContext("2d");
                    ctx.clearRect(0,0,canvas.width,canvas.height);
                    if (!history.length) return;
                    const maxStep = Math.max(...history.map(h => h.step));
                    const maxLoss = Math.max(...history.map(h => h.loss));
                    ctx.strokeStyle = "#4ade80";
                    ctx.beginPath();
                    history.forEach((h, idx) => {
                        const x = (h.step / maxStep) * canvas.width;
                        const y = canvas.height - (h.loss / maxLoss) * canvas.height;
                        if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    });
                    ctx.stroke();
                }
            </script>
        </body>
        </html>
        """
        return Response(html, mimetype="text/html")

    def _router(models: list[Any]) -> UCBRouter:
        experts = [Expert(getattr(m, "id", None) or getattr(m, "canonical_slug", str(m))) for m in models]
        storage = LocalFileStorage(checkpoint_dir) if checkpoint_dir else None
        return UCBRouter(experts, storage=storage)

    @app.get("/experts")
    def experts() -> Response:
        dragon = build_dragon()
        models = dragon.refresh_models(force=True)
        data = [
            {
                "id": getattr(m, "id", None) or getattr(m, "canonical_slug", None),
                "name": getattr(m, "name", None),
                "description": getattr(m, "description", None),
            }
            for m in models
        ]
        return jsonify(data)

    @app.post("/select")
    def select() -> Response:
        dragon = build_dragon()
        models = dragon.refresh_models(force=True)
        router = _router(models)
        expert = router.select()
        return jsonify({"selected_expert": expert.id})

    @app.post("/train/start")
    def train_start() -> Response:
        with training_lock:
            if training_state["running"]:
                return jsonify({"status": "already_running"})
            threading.Thread(target=_simulate_training, daemon=True).start()
            return jsonify({"status": "started"})

    @app.get("/train/status")
    def train_status() -> Response:
        with training_lock:
            return jsonify(
                {
                    "running": training_state["running"],
                    "step": training_state["step"],
                    "loss_history": training_state["loss_history"],
                }
            )

    @app.get("/train/next-chunk")
    def train_next_chunk() -> Response:
        chunk = _next_chunk()
        return jsonify({"chunk": chunk})

    return app


def _is_self_signed(cert_path: str) -> bool:
    try:
        info = ssl._ssl._test_decode_cert(cert_path)  # type: ignore[attr-defined]
    except Exception:
        return False
    return info.get("subject") == info.get("issuer")


def main() -> None:  # pragma: no cover - entrypoint wiring
    settings = load_settings(env=os.environ)
    api_key = settings.ui_api_key
    if not api_key:
        raise RuntimeError("UI_API_KEY or API_KEY is required to start the UI server")

    checkpoint_dir = os.environ.get("ROUTER_CHECKPOINT_DIR", ".router-state")
    app = create_app(api_key, checkpoint_dir=checkpoint_dir)
    cert = settings.ui_tls_cert
    key = settings.ui_tls_key
    if not cert or not key:
        raise RuntimeError("Provide UI_TLS_CERT and UI_TLS_KEY for HTTPS; self-signed certs are not allowed here.")
    if _is_self_signed(cert):
        warnings.warn("UI is starting with a self-signed certificate; replace with a trusted CA-issued cert.")
    ssl_context = (cert, key)
    app.run(host="0.0.0.0", port=int(os.environ.get("UI_PORT", "8443")), ssl_context=ssl_context)


if __name__ == "__main__":
    main()  # pragma: no cover
