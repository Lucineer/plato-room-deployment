# plato-room-deployment

> 5 ways to run a PLATO room — from Docker to bare metal.

## What It Is

Deployment guide and infrastructure for PLATO rooms. Includes Docker Compose setup, systemd service templates, and bare-metal configuration for running PLATO rooms on fleet hardware.

## Quick Start

```bash
# Docker (recommended)
docker-compose up -d

# Bare metal
./setup.sh
```

## Deployment Options

1. **Docker Compose** — easiest, isolated, reproducible
2. **systemd** — production, auto-restart, log management
3. **Bare metal** — maximum performance, minimal overhead
4. **Cloudflare Workers** — serverless, edge-deployed
5. **Kubernetes** — scalable, multi-room orchestration

## Fleet Context

Part of the PLATO ecosystem. See [PLATO-DEPLOYMENT-OPTIONS.md](./PLATO-DEPLOYMENT-OPTIONS.md) for detailed comparison.

## License

MIT / Apache-2.0
