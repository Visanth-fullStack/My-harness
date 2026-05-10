"""KnowledgeGraphService — CRUD and RFC queries for CIKG."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Edge, Node
from .storage import SCHEMA, _connect


class KnowledgeGraphService:
    """SQLite-backed knowledge graph."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def add_node(self, node: Node) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes "
                "VALUES (?,?,?,?,?,?)",
                (
                    node.id, node.node_type, node.name,
                    node.description,
                    json.dumps(node.metadata),
                    node.created_at,
                ),
            )
            conn.commit()

    def get_node(self, node_id: str) -> Node | None:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM nodes WHERE id=?",
                (node_id,),
            ).fetchone()
        if not row:
            return None
        return Node(
            id=row["id"],
            node_type=row["node_type"],
            name=row["name"],
            description=row["description"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )

    def list_nodes(
        self, node_type: str | None = None,
    ) -> list[Node]:
        with _connect(self._db_path) as conn:
            if node_type:
                rows = conn.execute(
                    "SELECT * FROM nodes "
                    "WHERE node_type=?",
                    (node_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM nodes",
                ).fetchall()
        return [
            Node(
                id=r["id"],
                node_type=r["node_type"],
                name=r["name"],
                description=r["description"],
                metadata=json.loads(r["metadata"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def add_edge(self, edge: Edge) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO edges "
                "VALUES (?,?,?,?,?)",
                (
                    edge.source_id, edge.target_id,
                    edge.edge_type, edge.weight,
                    json.dumps(edge.metadata),
                ),
            )
            conn.commit()

    def get_edges(
        self, node_id: str, direction: str = "out",
    ) -> list[Edge]:
        """Get edges. direction: out|in|both."""
        with _connect(self._db_path) as conn:
            edges: list[Edge] = []
            if direction in ("out", "both"):
                for r in conn.execute(
                    "SELECT * FROM edges "
                    "WHERE source_id=?",
                    (node_id,),
                ).fetchall():
                    edges.append(self._row_to_edge(r))
            if direction in ("in", "both"):
                for r in conn.execute(
                    "SELECT * FROM edges "
                    "WHERE target_id=?",
                    (node_id,),
                ).fetchall():
                    edges.append(self._row_to_edge(r))
        return edges

    def neighbors(self, node_id: str) -> list[Node]:
        """Get all nodes connected to this node."""
        edges = self.get_edges(node_id, "both")
        ids = set()
        for e in edges:
            ids.add(e.source_id)
            ids.add(e.target_id)
        ids.discard(node_id)
        return [
            n for n in
            (self.get_node(i) for i in ids)
            if n
        ]

    def find_gaps(self, feature: str) -> list[dict[str, str]]:
        feature_ids = self._matching_ids("feature", feature)
        results = []
        for node in self.list_nodes("competitor"):
            status = "has" if self._has_targets(node.id, feature_ids) else "lacks"
            results.append({
                "entity_id": node.id,
                "entity": node.name,
                "feature": feature,
                "status": status,
            })
        return sorted(results, key=lambda item: item["entity"])

    def compare_entities(self, a: str, b: str) -> dict[str, list]:
        a_features = self._targets_for(a, "has_feature")
        b_features = self._targets_for(b, "has_feature")
        related = self.get_edges(a, "out") + self.get_edges(b, "out")
        relationships = [
            self._edge_payload(edge)
            for edge in related if {edge.source_id, edge.target_id} == {a, b}
        ]
        return {
            "shared": sorted(a_features & b_features),
            "only_a": sorted(a_features - b_features),
            "only_b": sorted(b_features - a_features),
            "relationships": relationships,
        }

    def get_landscape(self, segment: str) -> dict[str, object]:
        segment_node = self._matching_nodes("market_segment", segment)
        if not segment_node:
            return self._empty_landscape(segment)
        comp_ids = [
            edge.source_id for edge in self.get_edges(segment_node[0].id, "in")
            if edge.edge_type == "targets_market"
        ]
        names = [self.get_node(node_id).name for node_id in comp_ids if self.get_node(node_id)]
        features = set().union(*(self._targets_for(node_id, "has_feature") for node_id in comp_ids))
        techs = set().union(*(self._targets_for(node_id, "uses_technology") for node_id in comp_ids))
        threats = sum(
            1 for node_id in comp_ids for edge in self.get_edges(node_id, "out")
            if edge.edge_type == "threatens" and edge.target_id in comp_ids
        )
        return {
            "segment": segment_node[0].name,
            "competitors": len(comp_ids),
            "features_tracked": len(features),
            "technologies": len(techs),
            "threat_count": threats,
            "top_competitors": sorted(names)[:10],
        }

    def delete_node(self, node_id: str) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM nodes WHERE id=?",
                (node_id,),
            )
            conn.execute(
                "DELETE FROM edges "
                "WHERE source_id=? OR target_id=?",
                (node_id, node_id),
            )
            conn.commit()

    def _row_to_edge(
        self, r: sqlite3.Row,
    ) -> Edge:
        return Edge(
            source_id=r["source_id"],
            target_id=r["target_id"],
            edge_type=r["edge_type"],
            weight=r["weight"],
            metadata=json.loads(r["metadata"]),
        )

    def _empty_landscape(self, segment: str) -> dict[str, object]:
        return {
            "segment": segment,
            "competitors": 0,
            "features_tracked": 0,
            "technologies": 0,
            "threat_count": 0,
            "top_competitors": [],
        }

    def _edge_payload(self, edge: Edge) -> dict[str, str]:
        return {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "edge_type": edge.edge_type,
        }

    def _has_targets(self, node_id: str, targets: set[str]) -> bool:
        return bool(targets & self._targets_for(node_id, "has_feature"))

    def _matching_ids(self, node_type: str, query: str) -> set[str]:
        nodes = self._matching_nodes(node_type, query)
        return {node.id for node in nodes}

    def _matching_nodes(self, node_type: str, query: str) -> list[Node]:
        value = query.lower()
        return [
            node for node in self.list_nodes(node_type)
            if value in node.name.lower() or value == node.id.lower()
        ]

    def _targets_for(self, node_id: str, edge_type: str) -> set[str]:
        return {
            edge.target_id for edge in self.get_edges(node_id, "out")
            if edge.edge_type == edge_type
        }
