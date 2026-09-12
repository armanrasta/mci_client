from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeState(str, Enum):
    EXISTS = "exists"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    
    
@dataclass(frozen=True)
class ClusterSnapshot:
    states: dict[str, NodeState]

    def is_converged(self, called_state: NodeState) -> bool:
        for state in self.states.values():
            if state == NodeState.UNKNOWN or state != called_state:
                return False
        return True
    
    def drifted_nodes(self, called_state: NodeState) -> list[str]:
        return [
            host
            for host, state in self.states.items()
            if state != NodeState.UNKNOWN and state != called_state
        ]
    
    def is_consistent(self):
        known_states = [s for s in self.states.values() if s != NodeState.UNKNOWN]
        length = len(set(known_states))
        
        match length:
            case 1: 
                return True
            case _:
                return False
        

@dataclass
class OperationContext:
    group_id: str
    target_state: NodeState
    last_snapshot: ClusterSnapshot | None = None
    round_number: int = 0

    def __str__(self):
        return f'{self.group_id} {self.target_state} {self.last_snapshot}'


@dataclass
class ReconciliationReport:
    group_id: str
    state: NodeState
    used_rounds: int
    converged: bool
    failures: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class ApplyResult:
    host: str
    success: bool
    status_code: int | None = None
    msg: str | None = None
