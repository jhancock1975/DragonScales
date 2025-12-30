# DragonScales

## Run locally
```bash
uv venv && uv pip install -e '.[dev]'
python -m dragonscales
```

## Run with Docker Compose
```bash
docker compose up --build
```

### Enable persistent model cache
The `Dragon` class can use a Redis-backed cache so model listings survive restarts. Docker Compose already provides a `cache` service:
```bash
docker compose up --build
```
Configure your app to construct the cache:
```python
from dragonscales.cache import redis_cache_from_url
from dragonscales.dragon import Dragon

cache = redis_cache_from_url("redis://cache:6379/0")
dragon = Dragon(client=openrouter_client, cache=cache)
```
Install the Redis extra if you're not using the dev extras:
```bash
uv pip install -e '.[cache]'
```

### Secrets via HashiCorp Vault
All credentials (OpenRouter API key, Redis username/password) are pulled from Vault when `VAULT_ADDR` is set. Provide access via `VAULT_TOKEN` or `VAULT_ROLE_ID`/`VAULT_SECRET_ID`, and store secrets in a KV v2 path (defaults: mount `secret`, path `dragonscales`). Environment variables override Vault for local overrides.

Redis URLs are built automatically when `REDIS_PASSWORD` (and optional `REDIS_USERNAME`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`) are present; otherwise set `CACHE_URL` explicitly. The bundled Redis container is started with password auth; supply `REDIS_PASSWORD` from Vault before `docker compose up`.

### Local Vault in Docker Compose
A Vault server is included in `docker-compose.yml` with file storage (`vault-data` volume) so secrets persist across restarts. Steps:
1. `export REDIS_PASSWORD=...` (and username if needed) and `docker compose up --build`.
2. Initialize Vault once (from another shell): `docker exec -it dragonscales-vault vault operator init -key-shares=1 -key-threshold=1`. Save the unseal key and root token securely.
3. Unseal: `docker exec -it dragonscales-vault vault operator unseal <UNSEAL_KEY>`.
4. Set your root token in the environment (`export VAULT_TOKEN=...`) and write secrets (example):
   ```bash
   vault kv put secret/dragonscales OPENROUTER_API_KEY=... REDIS_PASSWORD=$REDIS_PASSWORD REDIS_USERNAME=default
   ```
Vault UI is available at http://localhost:8200. The `vault-data` volume preserves data across `docker compose` restarts; remove it with `docker compose down -v` if you need a clean slate.

### Quick dev run
For a one-command run without exporting env vars, the compose file falls back to `REDIS_PASSWORD=dev-redis-password`. Use this only for local testing. To use real credentials from Vault, set `REDIS_PASSWORD`, `VAULT_TOKEN` or `VAULT_ROLE_ID`/`VAULT_SECRET_ID` in your environment or `.env` before `docker compose up`.

## UI
Run a simple HTTPS UI (self-signed) to browse free experts and see router selections:
```bash
export UI_API_KEY=dev-ui-key
export UI_TLS_CERT=/path/to/your/fullchain.pem   # e.g., from Let's Encrypt / certbot
export UI_TLS_KEY=/path/to/your/privkey.pem
python -m dragonscales.ui_app
# opens on https://localhost:8443
```
Calls are protected via `X-API-Key` or `Authorization: Bearer`. Set `ROUTER_CHECKPOINT_DIR` to persist router state, and use real certs in production by replacing the `ssl_context` argument. Compose still serves only the API; no Node.js middleware is used.

### Seed Vault with dev secrets (example script)
For local development, you can seed Vault (running in the `dragonscales-vault` container) with sample values and generate a self-signed cert. Save this as `scripts/dev_seed_vault.sh`, fill in your unseal key and root token, then run it from the repo root:
```bash
#!/usr/bin/env bash
set -euo pipefail

# --- configure with your dev values ---
VAULT_ADDR=http://localhost:8200
VAULT_CONTAINER=dragonscales-vault
UNSEAL_KEY="<paste-your-unseal-key-here>"
ROOT_TOKEN="<paste-your-root-token-here>"

# Dev secrets to store
OPENROUTER_API_KEY="sk-or-dev-123"
REDIS_PASSWORD="dev-redis-password"
UI_API_KEY="dev-ui-key"
UI_TLS_CERT_PATH="/app/certs/ui.crt"
UI_TLS_KEY_PATH="/app/certs/ui.key"

# --- generate self-signed cert (for dev only) ---
mkdir -p certs
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout certs/ui.key \
  -out certs/ui.crt \
  -days 365 \
  -subj "/CN=localhost"

# --- ensure Vault is unsealed ---
docker exec -it "$VAULT_CONTAINER" vault status >/dev/null || { echo "Vault container not running"; exit 1; }
docker exec -it "$VAULT_CONTAINER" vault operator unseal "$UNSEAL_KEY"

# --- write secrets into KV v2 at secret/dragonscales ---
docker exec -e VAULT_ADDR=http://localhost:8200 -e VAULT_TOKEN="$ROOT_TOKEN" "$VAULT_CONTAINER" \
  vault kv put secret/dragonscales \
    OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
    REDIS_PASSWORD="$REDIS_PASSWORD" \
    REDIS_USERNAME=default \
    UI_API_KEY="$UI_API_KEY" \
    UI_TLS_CERT="$UI_TLS_CERT_PATH" \
    UI_TLS_KEY="$UI_TLS_KEY_PATH"

echo "Done. Ensure ./certs is mounted into the app container:"
echo "  volumes:"
echo "    - ./certs:/app/certs:ro"
```
Run it with:
```bash
chmod +x scripts/dev_seed_vault.sh
./scripts/dev_seed_vault.sh
```
Then start the stack with `docker compose up -d` and visit `https://localhost:8443` (enter the UI API key in the page). For production, replace the self-signed cert with a trusted one and use proper tokens/roles.
