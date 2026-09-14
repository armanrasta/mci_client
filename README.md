# mci-client

[![CI](https://github.com/armanrasta/mci_client/actions/workflows/ci.yml/badge.svg)](https://github.com/armanrasta/mci_client/actions/workflows/ci.yml)

A small Python client that creates and deletes "groups" across a cluster
of nodes. The API is unreliable — timeouts and 500s are normal — so the
client retries, verifies, and rolls back when things go wrong.

Built for the API consumer challenge.

## Quick start

```bash
uv sync
uv run mci-client create my-group
uv run mci-client delete my-group
```

Or with Docker Compose (spins up a fake cluster + client):

```bash
docker compose up --build
```

## The API

Three endpoints, all on every node:

| Method | Path | Success | Notes |
|--------|------|---------|-------|
| POST | `/v1/group/` | 201 | 400 = "perhaps exists" |
| DELETE | `/v1/group/` | 200 | — |
| GET | `/v1/group/{id}/` | 200 | 404 = not found |

## How it works

### Three states per node

- `EXISTS` — GET returned 200
- `ABSENT` — GET returned 404
- `UNKNOWN` — timeout, 5xx, or anything unexpected

`UNKNOWN` is the key safety valve. When we can't tell what a node's
state is, we don't guess. We wait for the next round and try again.

### Reconciliation loop

Instead of "send a request, hope it works, rollback on failure," the
client runs a loop:

1. **Observe** — parallel GET to every node, build a snapshot
2. **Diff** — compare the snapshot to the desired state, find drifted nodes
3. **Apply** — parallel POST or DELETE on drifted nodes only
4. **Repeat** — until everyone agrees, or we run out of rounds

This is the same pattern Kubernetes uses for controllers.

### Rollback

If we can't converge, we flip the target state and re-enter the same
loop. So "create" failing turns into "reconcile to ABSENT." Same code,
no duplicated undo logic.

### Intra-client locking

A per-group `asyncio.Lock` serializes operations on the same group
within one process. Different groups still run in parallel.

## Assumptions I made

The API docs leave a few things open. Here's what I chose and why:

**POST 400 — verify, don't assume.**
The docs say a 400 might mean the group already exists. "Might" isn't
good enough, so after a 400 the client issues a GET. If the group is
now `EXISTS`, the create is treated as success (idempotent). If it's
still `ABSENT`, the 400 was a real failure.

**DELETE 404 — treated as success.**
The docs don't list a 404 for DELETE. I treat "already gone" as the
desired end state, which is what lets rollback converge cleanly instead
of retrying against an already-clean node.

**Two clients, same group — not coordinated.**
If two processes act on the same group simultaneously, they can race.
The API has no ETags and no idempotency keys, so there's nothing
server-side to coordinate on. Documented limitation.

**Static host list.**
The nodes come from `MCI_HOSTS`. No discovery. If the cluster changes,
you update the env var and restart.

**No external state.**
The client is stateless. Every run re-derives truth from the nodes.
No cache, no local database, no distributed lock service.

## Configuration

All through env vars, prefixed with `MCI_`:

| Var | Default | What |
|-----|---------|------|
| `MCI_HOSTS` | required | comma-separated node URLs |
| `MCI_ROUNDS` | 5 | max reconciliation rounds |
| `MCI_TIMEOUT` | 5.0 | HTTP timeout, seconds |
| `MCI_DELAY` | 0.5 | sleep between rounds |
| `MCI_ATTEMPTS` | 5 | max retries per HTTP call |
| `MCI_MAX_RETRY_TIME` | 15.0 | total retry budget per call |
| `MCI_LOG_LEVEL` | INFO | log level |

Copy `.env.example` to `.env` and edit.

## Tests

```bash
uv run pytest --cov=src/mci_client --cov-report=term-missing
```

The tests mock the HTTP layer with `respx`. No live cluster needed.
The rollback test uses a stateful fake cluster so it can verify that
rollback actually runs after a partial create failure.

## Deployment


Kubernetes manifests in `manifests/`:

- `configmap.yaml` — cluster URLs and tuning
- `job.yaml` — one-shot create/delete job
- `cronjob.yaml` — periodic reconciliation (optional)

```bash
kubectl apply -f manifests/
```

## What I didn't solve

- **Cross-process coordination.** Two clients on the same group can
  race. Full coordination would need an external lock service or
  server-side idempotency — out of scope for this task.
- **Stateful cluster.** The client is stateless; every run re-derives
  truth from the nodes. No cache, no local DB.

## Project layout

```
.
├── dev/
│   └── mock_node.py       fake cluster node for local testing
├── docs/                  architecture notes, ADRs
├── manifests/             kubernetes manifests
├── src/mci_client/
│   ├── __init__.py        public exports
│   ├── __main__.py        CLI entry point
│   ├── client.py          HTTP layer, retries, status mapping
│   ├── config.py          pydantic-settings: ClusterConfig
│   ├── logger.py          structlog setup
│   ├── models.py          dataclasses: NodeState, ClusterSnapshot
│   ├── reconciler.py      observe → diff → apply loop
│   ├── recorder.py        JSONL record writer
│   └── schemas.py         pydantic: GroupRequest
├── tests/                 pytest + respx
├── docker-compose.yaml
├── Dockerfile
├── pyproject.toml
├── README.md
└── uv.lock
```