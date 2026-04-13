# Model Serving

This tool starts the repo's Docker Compose stack through a small wrapper that fails fast if Docker cannot see an NVIDIA runtime.

## Prerequisites

- A working NVIDIA host driver:

```bash
nvidia-smi
```

- Docker configured with the NVIDIA Container Toolkit:

```bash
docker info --format '{{range $name, $_ := .Runtimes}}{{$name}} {{end}}'
```

The runtime list should include `nvidia`.

## Start

From the repo root, run:

```bash
./tools/model-serving/scripts/up.sh
```

The wrapper checks for NVIDIA runtime support and then runs:

```bash
docker compose -f docker/docker-compose.yml up -d
```

## Troubleshooting

- If the wrapper exits with `Docker does not report an NVIDIA runtime`, install or repair the NVIDIA Container Toolkit, restart Docker, and re-run the host and Docker checks above.
- If `docker info` fails, confirm the Docker daemon is running before retrying.
- To inspect the stack after startup, use the same compose file with `docker compose -f docker/docker-compose.yml ps` and `docker compose -f docker/docker-compose.yml logs -f`.
