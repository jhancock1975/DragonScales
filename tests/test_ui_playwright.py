import os

import pytest


playwright = pytest.importorskip("playwright.sync_api", reason="playwright is required for UI e2e tests")
from playwright.sync_api import sync_playwright  # type: ignore


@pytest.mark.e2e
@pytest.mark.skipif(os.environ.get("E2E_UI") != "1", reason="Set E2E_UI=1 to run the UI Playwright test")
def test_chat_send_returns_text():
    """
    E2E check: hit /chat/send via Playwright's request client and confirm we get a reply.
    Expects the UI server running on UI_BASE_URL (default https://localhost:8443) with a valid UI_API_KEY.
    """
    api_key = os.environ.get("UI_API_KEY")
    if not api_key:
        pytest.skip("UI_API_KEY is required to run the E2E UI test")

    base_url = os.environ.get("UI_BASE_URL", "https://localhost:8443")
    prompt = "Hello from Playwright"

    with sync_playwright() as p:
        request = p.request.new_context(
            base_url=base_url,
            extra_http_headers={"X-API-Key": api_key},
            ignore_https_errors=True,
        )
        resp = request.post("/chat/send", data=None, json={"message": prompt}, timeout=130000)
        assert resp.ok, f"status {resp.status} body={resp.text()}"
        body = resp.json()
        assert body.get("selected_expert"), f"no expert id in body: {body}"
        assert body.get("response"), f"empty response from model: {body}"

