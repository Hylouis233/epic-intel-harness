"""Compile the candidate's declarative graph into a deterministic execution order."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    handler: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")


class CandidateGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    nodes: list[GraphNode] = Field(min_length=1, max_length=16)
    edges: list[tuple[str, str]] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_references(self) -> CandidateGraph:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("graph node ids must be unique")
        known = set(node_ids)
        for source, target in self.edges:
            if source not in known or target not in known:
                raise ValueError(f"edge references unknown node: {source} -> {target}")
            if source == target:
                raise ValueError(f"self-edge is not allowed: {source}")
        return self


@dataclass(frozen=True, slots=True)
class CompiledGraph:
    nodes: tuple[GraphNode, ...]


def load_and_compile_graph(path: Path) -> CompiledGraph:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    graph = CandidateGraph.model_validate(raw)
    by_id = {node.id: node for node in graph.nodes}
    incoming = {node.id: 0 for node in graph.nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for source, target in graph.edges:
        outgoing[source].append(target)
        incoming[target] += 1

    queue = deque(node.id for node in graph.nodes if incoming[node.id] == 0)
    ordered: list[GraphNode] = []
    while queue:
        node_id = queue.popleft()
        ordered.append(by_id[node_id])
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)

    if len(ordered) != len(graph.nodes):
        raise ValueError("candidate graph must be acyclic")
    return CompiledGraph(nodes=tuple(ordered))

