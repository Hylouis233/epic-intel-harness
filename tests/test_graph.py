from __future__ import annotations

from pathlib import Path

import pytest

from epic_intel.runtime.graph import load_and_compile_graph


def test_candidate_graph_compiles_in_topological_order() -> None:
    root = Path(__file__).parents[1]
    graph = load_and_compile_graph(root / "candidate" / "graph.yaml")
    assert [node.id for node in graph.nodes] == [
        "readiness",
        "event_analysis",
        "evidence_retrieval",
        "report_writer",
    ]


def test_graph_rejects_cycles(tmp_path: Path) -> None:
    graph = tmp_path / "graph.yaml"
    graph.write_text(
        """version: 1
nodes:
  - {id: a, handler: a}
  - {id: b, handler: b}
edges:
  - [a, b]
  - [b, a]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="acyclic"):
        load_and_compile_graph(graph)


def test_graph_rejects_unknown_nodes(tmp_path: Path) -> None:
    graph = tmp_path / "graph.yaml"
    graph.write_text(
        """version: 1
nodes:
  - {id: a, handler: a}
edges:
  - [a, missing]
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown node"):
        load_and_compile_graph(graph)

