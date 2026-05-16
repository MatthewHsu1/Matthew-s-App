# IBKR Gateway via Docker

This directory ships a `docker-compose.yml` that runs Interactive Brokers' Gateway
in a container so the alpha engine can talk to a paper (or live) IBKR account.

## Prerequisites

- IBKR account approved (KYC complete). Funding is NOT required for paper.
- Docker and `docker compose` installed.
- IBKR Gateway credentials placed in your env's `secrets.env`:

  ```
  IBKR_USERNAME=your_username
  IBKR_PASSWORD=your_password
  IBKR_ACCOUNT_ID=DU1234567   # DU prefix for paper accounts
  ```

  This file lives at `tools/alpha_engine/envs/<env_name>/secrets.env`. It is
  `.gitignore`'d. `chmod 600` is recommended.

## Start the paper Gateway

```bash
cd tools/alpha_engine/docker
docker compose --env-file ../envs/<env_name>/secrets.env up -d ib-gateway-paper
```

The container listens on `127.0.0.1:4002`. The alpha engine reaches it via
`host-gateway` on Linux or `host.docker.internal` on macOS — the engine's
`VenueConfig.gateway_host` field picks the right value.

## Stop the Gateway

```bash
docker compose -f tools/alpha_engine/docker/docker-compose.yml down
```

## Live Gateway (Phase 3 only)

The live container is behind a `profiles: [live]` gate so it does not start by
default. Once Phase 3 ships:

```bash
docker compose --env-file ../envs/<env_name>/secrets.env --profile live up -d ib-gateway-live
```

## Daily reconnect

IBKR forces a daily authentication refresh. The `restart: unless-stopped` policy
plus the upstream IBC handling inside `gnzsnz/ib-gateway` covers this. If the
engine emits `venue_reconnecting` events in `engine.jsonl`, this is the expected
behavior, not a bug.

## Troubleshooting

- **`connection refused` on port 4002** — Gateway is not running. Check
  `docker ps` and `docker logs alpha-engine-ibgw-paper`.
- **`auth failure`** — Check `secrets.env` values; ensure file is loaded via
  `--env-file` flag.
- **`port already in use`** — Another Gateway instance is running on 4002.
  Stop it before starting this one.
