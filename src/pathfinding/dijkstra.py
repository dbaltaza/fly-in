
import heapq
from typing import TypedDict
from src.models.graph import Graph
from src.models.zone import Zone

ZONE_COSTS: dict[str, float] = {
    "normal": 1.0,
    "priority": 0.9,   # cheaper than normal → heap naturally prefers it
    "restricted": 2.0,
    "blocked": float("inf"),
}


class DijkstraStep(TypedDict):
    """One step of Dijkstra — captured each time a zone is settled.

    Attributes:
        step: Sequential step index (0-based).
        current: Name of the zone just settled (popped from heap).
        visited: Names of all zones settled so far, including current.
        frontier: Mapping of zone name → best known cost for zones that have a
            known cost but have not yet been settled.
        costs: Best known cost to every reached zone at this point.
        path_to_current: Cheapest known path from start to the current zone.
        final_path: Filled with the complete shortest path only when the end
            zone is settled; empty for all earlier steps.
    """

    step: int
    current: str
    visited: list[str]
    frontier: dict[str, float]
    costs: dict[str, float]
    path_to_current: list[str]
    final_path: list[str]


def dijkstra(graph: Graph, start: Zone, end: Zone) -> list[Zone]:
    """Find the cheapest path from start to end using Dijkstra's algorithm.

    Skips blocked zones entirely. Costs are based on the destination zone type:
    normal=1.0, priority=0.9 (preferred), restricted=2.0.

    Args:
        graph: The routing graph with adjacency data.
        start: The zone to begin from.
        end: The target zone to reach.

    Returns:
        A list of Zone objects from start to end inclusive, or an empty list
        if no path exists.
    """
    path, _ = dijkstra_with_steps(graph, start, end)
    return path


def dijkstra_with_steps(
    graph: Graph, start: Zone, end: Zone
) -> tuple[list[Zone], list[DijkstraStep]]:
    """Run Dijkstra and record one DijkstraStep for each zone settled.

    Each step captures the full frontier and visited-set state so that a
    visualiser can replay the algorithm frame by frame.

    Args:
        graph: The routing graph with adjacency data.
        start: The zone to begin from.
        end: The target zone to reach.

    Returns:
        A tuple of (path, steps) where path is the same as dijkstra() returns
        and steps is a list of DijkstraStep records in settle order.
    """
    heap: list[tuple[float, str]] = [(0.0, start.name)]
    costs: dict[str, float] = {start.name: 0.0}
    previous: dict[str, str | None] = {start.name: None}
    visited: set[str] = set()
    steps: list[DijkstraStep] = []

    def _partial_path(node: str) -> list[str]:
        """Reconstruct zone-name path from start to node via previous."""
        result: list[str] = []
        n: str | None = node
        while n is not None:
            result.append(n)
            n = previous.get(n)
        result.reverse()
        return result

    while heap:
        current_cost, current_name = heapq.heappop(heap)

        if current_name in visited:
            continue
        visited.add(current_name)

        # Explore neighbours and update costs before recording the step so the
        # snapshot shows the frontier *after* this node's edges are relaxed.
        is_end = current_name == end.name
        if not is_end:
            for neighbor, _ in graph.adjacency[current_name]:
                if neighbor.zone_type == "blocked":
                    continue
                move_cost = ZONE_COSTS[neighbor.zone_type]
                new_cost = current_cost + move_cost
                known = costs.get(neighbor.name)
                if known is None or new_cost < known:
                    costs[neighbor.name] = new_cost
                    previous[neighbor.name] = current_name
                    heapq.heappush(heap, (new_cost, neighbor.name))

        frontier = {
            name: c for name, c in costs.items() if name not in visited
        }
        final_path = (
            _partial_path(end.name)
            if is_end and end.name in previous
            else []
        )

        steps.append(DijkstraStep(
            step=len(steps),
            current=current_name,
            visited=list(visited),
            frontier=frontier,
            costs=dict(costs),
            path_to_current=_partial_path(current_name),
            final_path=final_path,
        ))

        if is_end:
            break

    # ── Path reconstruction ──────────────────────────────────────────────────
    if end.name not in previous:
        return [], steps

    path: list[Zone] = []
    node: str | None = end.name
    while node is not None:
        path.append(graph.zones[node])
        node = previous.get(node)
    path.reverse()

    if not path or path[0].name != start.name:
        return [], steps

    return path, steps
