# NautilusTrader Sidecar Bootstrap

This setup adds NautilusTrader as a local sidecar under `tools/nautilus-trader` without wiring it into the .NET backend or Next.js frontend.

## 1. Configure local settings

```bash
cp .env.nautilus.example .env.nautilus
```

Optional: edit `.env.nautilus` to change repo URL, pin tag, clone path, or Docker image.

## 2. Bootstrap NautilusTrader (pinned tag)

```bash
./scripts/bootstrap-nautilus.sh
```

What this does:
- Clones `nautechsystems/nautilus_trader` into `tools/nautilus-trader` (if missing)
- Fetches tags
- Checks out the pinned `NAUTILUS_TRADER_TAG`
- Prints the pinned commit SHA

The script is idempotent and can be rerun safely.

## 3. Run Docker smoke test

```bash
./scripts/nautilus-smoke.sh
```

This runs `docker compose -f docker/docker-compose.nautilus.yml run --rm nautilus` and prints the installed `nautilus_trader` package version from the container.

## 4. Helpful maintenance commands

Check the currently pinned checkout:

```bash
git -C tools/nautilus-trader describe --tags --always
```

Update to a newer release:
1. Change `NAUTILUS_TRADER_TAG` in `.env.nautilus`
2. Re-run `./scripts/bootstrap-nautilus.sh`
