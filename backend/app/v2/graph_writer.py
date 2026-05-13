"""
Deterministic Neo4j writer.

Takes a typed Study from app.v2.loaders and merges it into Neo4j with one
Cypher transaction per node label / edge type. Idempotent: re-running with
the same Study yields the same graph. No LLM. No fuzzy matching.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from neo4j import GraphDatabase, Driver

from .loaders import Study, IdentityNode, DimensionEdge


logger = logging.getLogger("mirofish.v2.graph_writer")


@dataclass
class WriteStats:
    study_id: str
    graph_id: str
    identity_nodes: int
    target_nodes: int
    edges: int
    edge_types: dict[str, int]
    target_labels: dict[str, int]


class GraphWriter:
    """Thin Neo4j wrapper used by the v2 path. One driver per process."""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    @contextmanager
    def _session(self) -> Iterator[Any]:
        with self._driver.session() as session:
            yield session

    # --- public ---

    def write_study(self, study: Study, *, graph_id: str | None = None,
                    wipe: bool = True) -> WriteStats:
        """
        Push the whole study into Neo4j under a single ``graph_id`` namespace.

        ``graph_id`` is stamped onto every node/edge as ``graph_id`` so a single
        Neo4j instance can host multiple studies side by side. ``wipe=True``
        deletes any existing nodes/edges with the same graph_id before writing.

        Beyond the schema-declared dimensions, this also derives behavioural
        nodes from panelist properties (region, household, voice register,
        clarity sensitivity, gender, age band) so the graph reads as a
        connected behavioural model rather than a flat star-schema.
        """
        gid = graph_id or f"v2_{study.study_id}"
        if wipe:
            self._wipe(gid)

        extra_targets, extra_edges = _derive_implicit_dimensions(study)
        all_target_nodes = {**study.target_nodes, **extra_targets}
        all_edges = list(study.edges) + extra_edges

        self._write_identity_nodes(study.nodes, gid)
        self._write_target_nodes(all_target_nodes, gid)
        edge_types = self._write_edges(all_edges, gid)
        self._stamp_brief(study, gid)
        return WriteStats(
            study_id=study.study_id,
            graph_id=gid,
            identity_nodes=len(study.nodes),
            target_nodes=len(all_target_nodes),
            edges=len(all_edges),
            edge_types=edge_types,
            target_labels=_count_labels(all_target_nodes),
        )

    def count_for(self, graph_id: str) -> dict[str, int]:
        """Return per-label node counts for a graph_id — useful for tests."""
        with self._session() as session:
            rec = session.run(
                "MATCH (n {graph_id: $gid}) RETURN labels(n)[0] AS label, count(*) AS c",
                gid=graph_id,
            )
            return {r["label"]: r["c"] for r in rec}

    # --- internals ---

    def _wipe(self, graph_id: str) -> None:
        with self._session() as session:
            session.run(
                "MATCH (n {graph_id: $gid}) DETACH DELETE n",
                gid=graph_id,
            )
        logger.info("wiped graph_id=%s", graph_id)

    def _write_identity_nodes(self, nodes: list[IdentityNode], graph_id: str) -> None:
        if not nodes:
            return
        # Group by label so we can run one MERGE per label.
        by_label: dict[str, list[IdentityNode]] = defaultdict(list)
        for n in nodes:
            by_label[n.label].append(n)
        for label, group in by_label.items():
            payload = [{
                "key_field": n.key_field,
                "key_value": n.key_value,
                "props":     {**n.properties, **n.attributes,
                              "graph_id": graph_id},
            } for n in group]
            cypher = (
                f"UNWIND $rows AS row "
                f"MERGE (n:{_safe_label(label)} {{ graph_id: $gid, "
                f"  `_key`: row.key_value }}) "
                f"SET n += row.props, n._key_field = row.key_field"
            )
            with self._session() as session:
                session.run(cypher, rows=payload, gid=graph_id)
            logger.info("wrote %d %s nodes (graph_id=%s)", len(group), label, graph_id)

    def _write_target_nodes(self, target_nodes: dict[tuple[str, str], dict[str, Any]],
                             graph_id: str) -> None:
        if not target_nodes:
            return
        by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (label, key_value), props in target_nodes.items():
            by_label[label].append({"key_value": key_value,
                                     "props": {**props, "graph_id": graph_id}})
        for label, group in by_label.items():
            cypher = (
                f"UNWIND $rows AS row "
                f"MERGE (n:{_safe_label(label)} {{ graph_id: $gid, "
                f"  `_key`: row.key_value }}) "
                f"SET n += row.props"
            )
            with self._session() as session:
                session.run(cypher, rows=group, gid=graph_id)
            logger.info("wrote %d %s targets (graph_id=%s)", len(group), label, graph_id)

    def _write_edges(self, edges: list[DimensionEdge], graph_id: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        # Group by (edge_type, source_label, target_label) so each Cypher
        # statement has a fixed shape.
        groups: dict[tuple[str, str, str], list[DimensionEdge]] = defaultdict(list)
        for e in edges:
            groups[(e.edge_type, e.source_label, e.target_label)].append(e)

        for (edge_type, src_label, tgt_label), group in groups.items():
            payload = [{
                "src_key": e.source_key_value,
                "tgt_key": e.target_key_value,
                "props":   {**e.properties, "graph_id": graph_id},
            } for e in group]
            cypher = (
                f"UNWIND $rows AS row "
                f"MATCH (s:{_safe_label(src_label)} "
                f"  {{ graph_id: $gid, `_key`: row.src_key }}) "
                f"MATCH (t:{_safe_label(tgt_label)} "
                f"  {{ graph_id: $gid, `_key`: row.tgt_key }}) "
                f"MERGE (s)-[r:{_safe_edge(edge_type)}]->(t) "
                f"SET r += row.props"
            )
            with self._session() as session:
                session.run(cypher, rows=payload, gid=graph_id)
            counts[edge_type] += len(group)
            logger.info("wrote %d %s edges (%s→%s, graph_id=%s)",
                        len(group), edge_type, src_label, tgt_label, graph_id)
        return dict(counts)

    def _stamp_brief(self, study: Study, graph_id: str) -> None:
        b = study.brief
        if not b.content_id:
            return
        cypher = (
            "MERGE (br:Brief { graph_id: $gid, `_key`: $key }) "
            "SET br += $props"
        )
        props = {
            "content_id":      b.content_id,
            "title":           b.title,
            "genre":           b.genre,
            "slot":            b.slot,
            "channel":         b.channel,
            "runtime_minutes": b.runtime_minutes,
            "air_date":        b.air_date,
            "synopsis":        b.synopsis,
            "rules":           list(b.rules),
            "graph_id":        graph_id,
        }
        with self._session() as session:
            session.run(cypher, gid=graph_id, key=b.content_id, props=props)


# --- helpers ---

def _safe_label(label: str) -> str:
    if not label.replace("_", "").isalnum() or not label[:1].isalpha():
        raise ValueError(f"unsafe label: {label!r}")
    return f"`{label}`"


def _safe_edge(edge_type: str) -> str:
    if not edge_type.replace("_", "").isalnum() or not edge_type[:1].isalpha():
        raise ValueError(f"unsafe edge type: {edge_type!r}")
    return f"`{edge_type}`"


def _count_labels(target_nodes: dict[tuple[str, str], Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for (label, _), _ in target_nodes.items():
        counts[label] += 1
    return dict(counts)


# ---------- derived dimensions ----------

# These derive nodes from panelist properties so the graph reads as a
# behavioural model — panelists who share a region / household type / voice
# register / clarity sensitivity / gender / age band become visibly
# connected rather than sitting as flat row attributes.
_DERIVED_DIMENSIONS = [
    {"prop": "region",              "label": "Region",             "edge": "LIVES_IN"},
    {"prop": "household",           "label": "HouseholdType",      "edge": "HOUSEHOLD_IS"},
    {"prop": "voice_register",      "label": "VoiceRegister",      "edge": "SPEAKS_IN"},
    {"prop": "clarity_sensitivity", "label": "ClaritySensitivity", "edge": "CLARITY_LEVEL"},
    {"prop": "gender",              "label": "Gender",             "edge": "IDENTIFIES_AS"},
]


def _age_band(age: Any) -> str | None:
    try:
        a = int(age)
    except (TypeError, ValueError):
        return None
    if a < 18: return "<18"
    if a < 25: return "18-24"
    if a < 35: return "25-34"
    if a < 45: return "35-44"
    if a < 55: return "45-54"
    if a < 65: return "55-64"
    return "65+"


def _derive_implicit_dimensions(
    study: Study,
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[DimensionEdge]]:
    """Build extra target nodes + edges from panelist properties."""
    extra_targets: dict[tuple[str, str], dict[str, Any]] = {}
    extra_edges: list[DimensionEdge] = []

    for node in study.nodes:
        # Simple string-valued dimensions
        for dim in _DERIVED_DIMENSIONS:
            raw = node.properties.get(dim["prop"])
            if raw is None or raw == "":
                continue
            value = str(raw).strip()
            if not value:
                continue
            label = dim["label"]
            extra_targets[(label, value)] = {"name": value}
            extra_edges.append(DimensionEdge(
                edge_type=dim["edge"],
                source_label=node.label,
                source_key_field=node.key_field,
                source_key_value=node.key_value,
                target_label=label,
                target_key_field="value",
                target_key_value=value,
                properties={},
            ))

        # Age band (derived from age int)
        band = _age_band(node.properties.get("age"))
        if band:
            extra_targets[("AgeBand", band)] = {"name": band}
            extra_edges.append(DimensionEdge(
                edge_type="AGE_BAND",
                source_label=node.label,
                source_key_field=node.key_field,
                source_key_value=node.key_value,
                target_label="AgeBand",
                target_key_field="value",
                target_key_value=band,
                properties={},
            ))

    return extra_targets, extra_edges
