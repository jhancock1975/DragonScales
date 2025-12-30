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
