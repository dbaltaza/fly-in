"""Multi-path scheduling for the drone fleet.

The single shortest path forces every drone through the same bottleneck zones,
which serialises throughput badly when those zones are restricted (2-turn) or
capacity-1. This module finds several *diverse* paths from start to end and
distributes the drones across them so independent traffic lanes stay busy in
parallel, while the engine still enforces every per-turn capacity rule.
"""

import heapq

from ..models.graph import Graph
from ..models.zone import Zone
from .dijkstra import ZONE_COSTS

# Real per-turn cost of arriving in a zone (restricted moves take 2 turns).
TURN_COSTS: dict[str, int] = {
    "normal": 1,
    "priority": 1,
    "restricted": 2,
}

# Extra cost added to every edge of a path once it has been chosen, so the next
# Dijkstra run is pushed onto a different lane wherever an alternative exists.
PENALTY_BUMP: float = 4.0


def _edge_key(a: str, b: str) -> frozenset[str]:
    """Return an undirected key for the edge between zones ``a`` and ``b``."""
    return frozenset((a, b))


def _dijkstra_penalized(
    graph: Graph,
    start: Zone,
    end: Zone,
    penalty: dict[frozenset[str], float],
) -> list[Zone]:
    """Shortest path under base zone costs plus per-edge penalties.

    Identical to the plain Dijkstra but each edge cost is increased by any
    accumulated ``penalty`` so previously used lanes become less attractive.

    Args:
        graph: The routing graph with adjacency data.
        start: The zone to begin from.
        end: The target zone to reach.
        penalty: Accumulated extra cost per undirected edge.

    Returns:
        The cheapest path as a list of zones, or an empty list if none exists.
    """
    heap: list[tuple[float, str]] = [(0.0, start.name)]
    costs: dict[str, float] = {start.name: 0.0}
    previous: dict[str, str | None] = {start.name: None}
    visited: set[str] = set()

    while heap:
        current_cost, current_name = heapq.heappop(heap)
        if current_name in visited:
            continue
        visited.add(current_name)
        if current_name == end.name:
            break

        for neighbor, _ in graph.adjacency[current_name]:
            if neighbor.zone_type == "blocked":
                continue
            base = ZONE_COSTS[neighbor.zone_type]
            extra = penalty.get(_edge_key(current_name, neighbor.name), 0.0)
            new_cost = current_cost + base + extra
            known = costs.get(neighbor.name)
            if known is None or new_cost < known:
                costs[neighbor.name] = new_cost
                previous[neighbor.name] = current_name
                heapq.heappush(heap, (new_cost, neighbor.name))

    if end.name not in previous:
        return []
    path: list[Zone] = []
    node: str | None = end.name
    while node is not None:
        path.append(graph.zones[node])
        node = previous.get(node)
    path.reverse()
    if not path or path[0].name != start.name:
        return []
    return path


def find_paths(
    graph: Graph, start: Zone, end: Zone, k: int
) -> list[list[Zone]]:
    """Find up to ``k`` distinct start→end paths, preferring diverse lanes.

    Runs Dijkstra repeatedly, penalising the edges of each path found so the
    next run diverges where the graph offers a choice. Forced edges (a sole
    exit, the final corridor) are reused as needed. Returns at least the single
    shortest path when no alternatives exist.

    Args:
        graph: The routing graph.
        start: The start zone.
        end: The end zone.
        k: Maximum number of distinct paths to return.

    Returns:
        A list of distinct paths, ordered from the cheapest discovered onward.
    """
    penalty: dict[frozenset[str], float] = {}
    paths: list[list[Zone]] = []
    seen: set[tuple[str, ...]] = set()

    for _ in range(max(k, 1) * 4):
        if len(paths) >= k:
            break
        path = _dijkstra_penalized(graph, start, end, penalty)
        if not path:
            break
        for a, b in zip(path, path[1:]):
            key = _edge_key(a.name, b.name)
            penalty[key] = penalty.get(key, 0.0) + PENALTY_BUMP
        names = tuple(z.name for z in path)
        if names not in seen:
            seen.add(names)
            paths.append(path)

    return paths


def path_travel_time(path: list[Zone]) -> int:
    """Return the turns one lone drone needs to traverse ``path``.

    Args:
        path: A start→end path as a list of zones.

    Returns:
        Sum of per-zone turn costs along the path (restricted zones count 2).
    """
    return sum(TURN_COSTS.get(z.zone_type, 1) for z in path[1:])


def assign_drones(paths: list[list[Zone]], n: int) -> list[list[Zone]]:
    """Distribute ``n`` drones across ``paths`` to balance completion time.

    Greedy lem-in style distribution: each successive drone is placed on the
    path that currently minimises ``travel_time + drones_already_assigned``.
    With several equal-length lanes this round-robins them, keeping every lane
    fed; shorter lanes naturally absorb more drones.

    Args:
        paths: The candidate paths (must be non-empty).
        n: The number of drones to assign.

    Returns:
        A list of length ``n``: entry ``i`` is the path for drone ``i``.
    """
    lengths = [path_travel_time(p) for p in paths]
    counts = [0] * len(paths)
    assignment: list[list[Zone]] = []
    for _ in range(n):
        best = min(
            range(len(paths)),
            key=lambda i: lengths[i] + counts[i],
        )
        counts[best] += 1
        assignment.append(paths[best])
    return assignment
