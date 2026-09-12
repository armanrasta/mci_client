import asyncio
from dataclasses import dataclass, field

import structlog

from .client import Client
from .models import (
    ApplyResult,
    ClusterSnapshot,
    NodeState,
    OperationContext,
    ReconciliationReport,
)

logger = structlog.get_logger(__name__)


class ReconciliationError(Exception):
    """Raised when reconciliation cannot bring the cluster to the desired state."""


class Reconciler:
    def __init__(self, hosts: list[str], client: Client, max_rounds: int = 5, round_delay: float = 0.5):
        
        self._hosts = hosts
        self._client = client
        self._max_rounds = max_rounds
        self._round_delay = round_delay
        # per-group locks — intra-client serialization
        self._locks: dict[str, asyncio.Lock] = {}
        
        logger.info(
            "reconciler_initialized",
            hosts=hosts,
            max_rounds=max_rounds,
            round_delay=round_delay,
        )
        
    def _get_lock(self, group_id: str) -> asyncio.Lock:
        if group_id not in self._locks:
            self._locks[group_id] = asyncio.Lock()
        return self._locks[group_id]
    
    async def close(self):
        await self._client.close()
        
    async def reconcile(self, group_id: str, target_state: NodeState) -> ReconciliationReport:
        lock = self._get_lock(group_id)
        async with lock:
            logger.info("reconciliation_started", group_id=group_id, target_state=target_state)
            context = OperationContext(group_id=group_id, target_state=target_state)
            report = await self._run_reconciliation(context)
            logger.info(
                "reconciliation_completed",
                group_id=group_id,
                target_state=target_state,
                report=report,
            )
            return report
    
    async def  _snapshot(self, group_id: str) -> ClusterSnapshot:
        states = {}
        for host in self._hosts:
            state = await self._client.get_state(host, group_id)
            states[host] = state
        return ClusterSnapshot(states=states)
    
    async def _apply_drift(self,
                           drifted_nodes: list[str],
                           group_id: str,
                           target_state: NodeState) -> list[ApplyResult]:
        
        if target_state == NodeState.EXISTS:
            tasks = [self._client.create(host, group_id) for host in drifted_nodes]
        elif target_state == NodeState.ABSENT:
            tasks = [self._client.delete(host, group_id) for host in drifted_nodes]
        
        results = await asyncio.gather(*tasks)
        
        for result in results:
            if result.success:
                logger.info("apply_success", host=result.host, group_id=group_id, target_state=target_state) 
            else:
                logger.warning("apply_failure", host=result.host, group_id=group_id, target_state=target_state, status_code=result.status_code, msg=result.msg)     
            
        return results     

    async def _run_reconciliation(self, context: OperationContext) -> ReconciliationReport:\
        
        for round_number in range(1, self._max_rounds + 1):
            context.round_number = round_number
            
            snapshot = await self._snapshot(context.group_id)
            context.last_snapshot = snapshot
            drifted_nodes = snapshot.drifted_nodes(context.target_state)
            
            logger.info("round_snapshot",
                        group_id=context.group_id,
                        round_number=round_number,
                        max_round_number=self._max_rounds,
                        target_state=context.target_state,
                        states=snapshot.states,
                        consistent=snapshot.is_consistent(),
                        converged=snapshot.is_converged(context.target_state),
                        drifted_nodes=drifted_nodes,
                        )       
            
            if snapshot.is_converged(context.target_state):
                return ReconciliationReport(
                    group_id=context.group_id,
                    state=context.target_state,
                    used_rounds=round_number,
                    converged=True,
                    failures=[],
                )
            
            if drifted_nodes:
                await self._apply_drift(drifted_nodes,
                                        context.group_id,
                                        context.target_state)
            else:
                logger.info(
                    "waiting_on_unknown_states",
                    group_id=context.group_id,
                    round_number=round_number,
                    max_round_number=self._max_rounds,
                )
            
            if round_number < self._max_rounds:
                await asyncio.sleep(self._round_delay)
        
        if context.last_snapshot:
            failures = [h for h,s in context.last_snapshot.states.items() if s != context.target_state]
        else:
            failures = []
            
        return ReconciliationReport(
            group_id=context.group_id,
            state=context.target_state,
            used_rounds=round_number,
            converged=False,
            failures=failures,
            )
            