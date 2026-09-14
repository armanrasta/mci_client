# ADR-002: Hybrid concurrency control (PCC + OCC)

## Status

Accepted.

## Context

ADR-001 picked reconciliation as the algorithm. This one is about
locking.

The problem: two callers can hit the same group at the same time.
Happens in two places. Same process — two coroutines call reconcile()
for the same group_id, they each grab their own snapshot, they each
decide what to do, and their requests interleave. Or across processes,
two pods doing the same thing. Either way, the cluster ends up in a
weird state.

We can't push this to the server. The API has no ETags, no idempotency
keys, no version field. Nothing to coordinate on. So the client has to
handle it.

## Decision

Two different strategies for the two different scales.

**Within one process:** a lock per group_id. `asyncio.Lock` in a dict.
Grab it before you reconcile, release when you're done. Different
groups don't touch each other's locks, so they run in parallel. Same
group waits.

**Across the cluster:** optimism. The reconciliation loop is already
optimistic — every round re-observes everything, so if a race slipped
through between rounds, the next round sees the drift and fixes it.
No distributed lock. No shared state. Just re-check.

**Across processes:** not solved. The reason is decribed on "Known limitation" below.

## What we rejected

**One big lock.** Serializes every group in the process. If group A
is stuck, group B waits. No reason for that. Per-group is the smallest
scope we can get without server help.

**No lock at all.** Tried to convince myself this was fine. It isn't.
Two coroutines reconcile the same group, both observe ABSENT, both
POST. Now we've sent two creates for the same group. The server may
handle it (400), or it may not. Either way we've done twice the work
and confused the retry logic. The lock is a few lines. Worth it.

**etcd / Redis lock.** Same rejection as ADR-001. Adds a dependency
and a new way to fail. Not worth it for a task like this.

**Fully optimistic, no lock.** Would work if the API were idempotent.
It isn't — a POST that fires twice isn't guaranteed to be safe. So we
keep the lock.

## Consequences

The good: same-group operations serialize cleanly. Different groups
run in parallel. No external deps. And because we never act on
`UNKNOWN` nodes, we don't take action on stale information — that's
the biggest race avoided for free.

The bad: cross-process is unsolved. Two pods racing on the same group
can produce inconsistent state. We make POST 400 and DELETE 404 count
as success, so the retry doesn't make it worse, and the next reconcile
observes and fixes drift. But there's still a window.

Also, the locks dict grows forever. One entry per group_id we've ever
seen. For a CLI that runs once and exits, fine. For a long-running
server, this would need eviction. Its not mentioned in challenge docs so we keep it out of our production scope.

## Known limitation

If this client ran as a service with multiple replicas, we'd need a
distributed lock — etcd, Redis, or a Kubernetes Lease. That's out of
scope for the current task. I'm asked to do The single-process case .

## References

- asyncio.Lock docs
- Kubernetes Lease API
