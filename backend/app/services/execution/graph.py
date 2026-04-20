import logging
from typing import Any, Dict, List, Set

from app.models.database import NodeExecution
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class GraphMixin:

    def _build_workflow_state_snapshot(
        self,
        execution_id: int,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        statuses: Dict[str, str]
    ) -> Dict[str, Any]:
        node_executions = self.db.query(NodeExecution).filter(
            NodeExecution.execution_id == execution_id
        ).order_by(NodeExecution.id.asc()).all()
        executions_by_node_id = {execution.node_id: execution for execution in node_executions}
        seen_node_ids: Set[str] = set()
        snapshot_nodes: List[Dict[str, Any]] = []
        sequence_by_node_id = self._snapshot_sequence_by_topology(nodes, edges)

        for index, node in enumerate(nodes):
            node_id = str(node.get("id") or f"node-{index}")
            node_execution = executions_by_node_id.get(node_id)
            seen_node_ids.add(node_id)
            status = node_execution.status if node_execution else statuses.get(node_id, "not-run")
            snapshot_nodes.append({
                "id": node_id,
                "type": str(node.get("type", "shell")),
                "config": node.get("config", {}) or {},
                "position": node.get("position"),
                "sequence": sequence_by_node_id.get(node_id, str(index + 1)),
                "status": status,
                "node_execution_id": node_execution.id if node_execution else None,
                "started_at": node_execution.started_at.isoformat() if node_execution and node_execution.started_at else None,
                "finished_at": node_execution.finished_at.isoformat() if node_execution and node_execution.finished_at else None,
                "duration": node_execution.duration if node_execution else None,
                "error_message": node_execution.error_message if node_execution else None,
            })

        snapshot_nodes.sort(key=lambda item: self._sequence_sort_key(str(item.get("sequence") or "")))

        for node_execution in node_executions:
            if node_execution.node_id in seen_node_ids:
                continue
            snapshot_nodes.append({
                "id": node_execution.node_id,
                "type": node_execution.node_type,
                "config": {},
                "position": None,
                "sequence": len(snapshot_nodes) + 1,
                "status": node_execution.status,
                "node_execution_id": node_execution.id,
                "started_at": node_execution.started_at.isoformat() if node_execution.started_at else None,
                "finished_at": node_execution.finished_at.isoformat() if node_execution.finished_at else None,
                "duration": node_execution.duration,
                "error_message": node_execution.error_message,
            })

        status_by_node_id = {node["id"]: node["status"] for node in snapshot_nodes}
        snapshot_edges = []
        for edge in edges:
            from_node = str(edge.get("from") or edge.get("from_node") or "")
            to_node = str(edge.get("to") or "")
            if not from_node or not to_node:
                continue
            snapshot_edges.append({
                "from": from_node,
                "to": to_node,
                "label": edge.get("label"),
                "status": self._snapshot_edge_status(
                    status_by_node_id.get(from_node, "not-run"),
                    status_by_node_id.get(to_node, "not-run")
                ),
            })

        return {
            "version": 1,
            "captured_at": utc_now().isoformat(),
            "nodes": snapshot_nodes,
            "edges": snapshot_edges,
        }

    def _snapshot_sequence_by_topology(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        node_ids: List[str] = []
        node_index: Dict[str, int] = {}
        node_positions: Dict[str, Dict[str, Any]] = {}

        for index, node in enumerate(nodes):
            node_id = str(node.get("id") or f"node-{index}")
            if node_id in node_index:
                node_id = f"{node_id}-{index}"
            node_ids.append(node_id)
            node_index[node_id] = index
            node_positions[node_id] = node.get("position") or {}

        parents: Dict[str, Set[str]] = {node_id: set() for node_id in node_ids}
        children: Dict[str, Set[str]] = {node_id: set() for node_id in node_ids}
        for edge in edges:
            from_node = str(edge.get("from") or edge.get("from_node") or "")
            to_node = str(edge.get("to") or "")
            if from_node not in parents or to_node not in parents:
                continue
            parents[to_node].add(from_node)
            children[from_node].add(to_node)

        def sort_key(node_id: str) -> tuple[float, float, int]:
            position = node_positions.get(node_id) or {}
            return (
                float(position.get("x") or 0),
                float(position.get("y") or 0),
                node_index.get(node_id, 0)
            )

        remaining = set(node_ids)
        completed: Set[str] = set()
        layer = 1
        sequence_by_node_id: Dict[str, str] = {}

        while remaining:
            ready = [
                node_id for node_id in remaining
                if all(parent_id in completed for parent_id in parents[node_id])
            ]
            if not ready:
                ready = list(remaining)
            ready = sorted(ready, key=sort_key)

            if len(ready) == 1:
                sequence_by_node_id[ready[0]] = str(layer)
            else:
                for index, node_id in enumerate(ready, 1):
                    sequence_by_node_id[node_id] = f"{layer}-{index}"

            for node_id in ready:
                remaining.discard(node_id)
                completed.add(node_id)
            layer += 1

        return sequence_by_node_id

    def _sequence_sort_key(self, sequence: str) -> tuple[int, int]:
        parts = sequence.split("-", 1)
        try:
            layer = int(parts[0])
        except ValueError:
            layer = 0
        branch = 0
        if len(parts) > 1:
            try:
                branch = int(parts[1])
            except ValueError:
                branch = 0
        return layer, branch

    def _snapshot_edge_status(self, from_status: str, to_status: str) -> str:
        if from_status == "failed":
            return "failed"
        if from_status in {"success", "completed"} and to_status != "not-run":
            return "passed"
        if to_status == "running":
            return "running"
        return "pending"

    def _build_execution_graph(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> tuple[List[str], Dict[str, Dict[str, Any]], Dict[str, List[str]], Dict[str, List[str]], Dict[tuple, str]]:
        node_order: List[str] = []
        nodes_by_id: Dict[str, Dict[str, Any]] = {}

        for index, node in enumerate(nodes):
            node_id = str(node.get("id") or f"node-{index}")
            if node_id in nodes_by_id:
                node_id = f"{node_id}-{index}"
                node = {**node, "id": node_id}
            node_order.append(node_id)
            nodes_by_id[node_id] = node

        parents: Dict[str, List[str]] = {node_id: [] for node_id in node_order}
        children: Dict[str, List[str]] = {node_id: [] for node_id in node_order}
        edge_labels: Dict[tuple, str] = {}

        valid_edge_count = 0
        for edge in edges:
            from_id = edge.get("from")
            to_id = edge.get("to")
            if from_id not in nodes_by_id or to_id not in nodes_by_id:
                continue
            if from_id not in parents[to_id]:
                parents[to_id].append(from_id)
            if to_id not in children[from_id]:
                children[from_id].append(to_id)
            label = edge.get("label") or ""
            if label:
                edge_labels[(from_id, to_id)] = label
            valid_edge_count += 1

        if valid_edge_count == 0:
            for from_id, to_id in zip(node_order, node_order[1:]):
                parents[to_id].append(from_id)
                children[from_id].append(to_id)

        return node_order, nodes_by_id, parents, children, edge_labels

    def _merge_parent_contexts(
        self,
        parent_ids: List[str],
        context_updates: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        for parent_id in parent_ids:
            context.update(context_updates.get(parent_id, {}))
        return context

    def _create_skipped_node_execution(
        self,
        execution_id: int,
        node: Dict[str, Any],
        reason: str
    ) -> None:
        now = utc_now()
        node_execution = NodeExecution(
            execution_id=execution_id,
            node_id=str(node.get("id")),
            node_type=str(node.get("type", "shell")),
            status="skipped",
            started_at=now,
            finished_at=now,
            duration=0,
            input_data=dict(node.get("config", {}) or {}),
            output_data={"exit_status": -1, "skipped": True, "reason": reason},
            error_message=reason
        )
        self.db.add(node_execution)
        self.db.commit()

    def _get_loop_body(
        self,
        loop_node_id: str,
        children: Dict[str, List[str]]
    ) -> Set[str]:
        body: Set[str] = set()
        stack = list(children.get(loop_node_id, []))
        while stack:
            nid = stack.pop()
            if nid not in body:
                body.add(nid)
                stack.extend(children.get(nid, []))
        return body

    def _check_loop_iterations(
        self,
        loop_state: Dict[str, Dict[str, Any]],
        statuses: Dict[str, str],
        pending: Set[str],
        context_updates: Dict[str, Dict[str, Any]],
        execution_id: int,
        nodes_by_id: Dict[str, Dict[str, Any]],
        children: Dict[str, List[str]]
    ) -> None:
        for loop_id in list(loop_state.keys()):
            state = loop_state[loop_id]
            body = state["body"]
            if not body:
                del loop_state[loop_id]
                continue

            all_done = all(nid in statuses for nid in body)
            if not all_done:
                continue

            all_success = all(statuses.get(nid) == "success" for nid in body)
            state["current"] += 1

            if all_success and state["current"] < state["total"]:
                for nid in body:
                    statuses.pop(nid, None)
                    pending.add(nid)
                context_updates[loop_id] = {
                    **context_updates.get(loop_id, {}),
                    "_loop_iteration": state["current"],
                    "_loop_total": state["total"],
                }
            else:
                del loop_state[loop_id]
