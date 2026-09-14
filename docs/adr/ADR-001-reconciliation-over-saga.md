# ADR-001: Reconciliation loop instead of saga or 2PC

## Status

Accepted.

## Context

The task is to make a client that has the methods to create or delete a group on every node in a cluster. The API is unreliable as mentioned but timeouts and 500s are normal. When a partial operation
happens (a create succeeds on one node but fails on another), the whole
ops has to be undone.

The obvious approaches were:

1. **Two-phase commit** — coordinate all nodes, commit or abort.
2. **Saga with compensating transactions** — do the work, and if it
   fails, run explicit undo steps.
3. **Kubernetes reconciliation methods(important)** — observe, diff, apply, repeat.

Each has tradeoffs.

## Decision

I use a reconciliation loop.

The client:
1. Observes every node with a parallel GET.
2. Diffs the observed state against the desired state.
3. Applies POST or DELETE to the drifted nodes only.
4. Repeats until the cluster converges, or max_rounds runs out.

Rollback is the same loop with a flipped target operated. If we wanted to do create and couldn't, we set the target to ABSENT and re-enter.

## Considered alternatives

**Two-phase commit.**
Reject | 2PC needs a transaction coordinator — a single process that
tracks every participant's state and decides when to commit or abort.
Our cluster has no such thing. It's just N independent REST servers
behind URLs. If we added a coordinator, it would be a single point of
failure: if it dies mid-commit, every node is stuck holding locks and
waiting.

**Saga with compensating transactions.**
Reject | A saga means writing a forward path and a rollback path for
every operation. Two code paths, two sets of tests, two places to have
bugs. Our rollback is the forward loop with the desired state set to what we started from one path either way.

**Distributed lock (etcd / Redis).**
Reject | It would let us coordinate across processes, but it adds a
new external dependency and a new failure mode. The cluster API has
no invalidation signal, so we'd be building coordination on top of a
system that's already flaky. Out of scope for this task.

## Consequences

**Good:**
- No external dependencies. No coordinator, no lock service.
- One code path for both directions.
- Self-healing. If a run fails but leaves partial state, the next run
  observes and fixes it. No transaction log needed.
- Tolerates network partitions gracefully — we just observe again.

**Bad:**
- Eventual consistency, not immediate actions. A single reconcile may need multiple rounds.
- `max_rounds` and `round_delay` need tuning. Too low and legitimate
  operations fail. If these parameters get set too high, a broken cluster hangs the client.
- We're trusting the nodes to eventually tell the truth when probed. If we want a real system for controlling these things, we would need a manager not a client service. 

## References

- Kubernetes controller pattern — https://kubernetes.io/docs/concepts/architecture/controller/
- RFC 7231 §4.2.2 (idempotent methods)