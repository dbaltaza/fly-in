from typing import TypedDict

from ..models.graph import Graph
from ..models.zone import Zone
from ..models.drone import Drone
from ..pathfinding.dijkstra import dijkstra_with_steps, DijkstraStep
from ..pathfinding.scheduler import find_paths, assign_drones


class DroneSnapshot(TypedDict):
    """State of one drone captured at the end of a turn.

    Attributes:
        id: Drone identifier number.
        zone: Name of the zone the drone occupies (source if in_transit).
        state: One of 'waiting', 'in_transit', or 'arrived'.
        dest: Name of the transit destination zone, or None.
    """

    id: int
    zone: str
    state: str
    dest: str | None


class TurnSnapshot(TypedDict):
    """Complete simulation state captured at the end of one turn.

    Attributes:
        turn: Turn number (0 = initial state before any moves).
        moves: Move strings emitted this turn (e.g. ['D1-roof1']).
        drones: Snapshot of every drone's state.
        active_connections: Zone-name pairs traversed this turn.
    """

    turn: int
    moves: list[str]
    drones: list[DroneSnapshot]
    active_connections: list[tuple[str, str]]


class SimulationEngine:
    """Runs the turn-by-turn drone routing simulation.

    Attributes:
        graph: The routing graph with zones, connections, and adjacency.
        drones: All drones participating in the simulation.
        turn: The current turn counter.
        turn_moves: Drone movement strings collected during the current turn.
        snapshots: One TurnSnapshot per turn (index 0 = initial state).
    """

    def __init__(self, graph: Graph) -> None:
        """Initialise the engine and create all drones with planned paths.

        Args:
            graph: The fully parsed routing graph.

        Raises:
            ValueError: If the graph has no start/end zone or no path exists.
        """
        if graph.start is None or graph.end is None:
            raise ValueError("Graph must have a start and end zone.")
        self.graph = graph
        self.start: Zone = graph.start
        self.end: Zone = graph.end
        self.drones: list[Drone] = []
        self.turn = 0
        self.turn_moves: list[str] = []
        self.snapshots: list[TurnSnapshot] = []
        self._arrived_this_turn: set[int] = set()
        self._active_connections: list[tuple[str, str]] = []
        self.dijkstra_steps: list[DijkstraStep] = []

        path, self.dijkstra_steps = dijkstra_with_steps(
            graph, self.start, self.end
        )
        if not path:
            raise ValueError("No path exists from start to end zone.")

        self._assignment = self._plan(path)
        self._build_drones(self._assignment)

    def _plan(self, shortest: list[Zone]) -> list[list[Zone]]:
        """Choose the drone→path assignment that finishes in the fewest turns.

        Finds several diverse lanes, then sweeps over how many of them to use
        (1 = everyone on the shortest path, up to all of them). Each candidate
        is dry-run silently and the fastest one wins, so spreading the fleet
        can only ever help — a worse split is simply never selected.

        Args:
            shortest: The plain shortest path, used as a guaranteed fallback.

        Returns:
            A per-drone list of paths (index i → drone i+1's path).
        """
        n = self.graph.nb_drones
        paths = find_paths(self.graph, self.start, self.end, k=min(n, 8))
        if not paths:
            paths = [shortest]

        best_assignment = assign_drones(paths[:1], n)
        best_turns: int | None = None
        for width in range(1, len(paths) + 1):
            candidate = assign_drones(paths[:width], n)
            self._build_drones(candidate)
            turns = self._simulate(record=False)
            if turns is None:
                continue
            if best_turns is None or turns < best_turns:
                best_turns = turns
                best_assignment = candidate
        return best_assignment

    def _build_drones(self, assignment: list[list[Zone]]) -> None:
        """Reset graph occupancy and create the fleet for ``assignment``.

        Args:
            assignment: Per-drone paths (index i → drone i+1's path).
        """
        for zone in self.graph.zones.values():
            zone.current_drones = 0
        for connection in self.graph.connections:
            connection.current_usage = 0
        self.start.current_drones = self.graph.nb_drones
        self.drones = []
        for i in range(1, self.graph.nb_drones + 1):
            self.drones.append(Drone(
                id=i,
                current_zone=self.start,
                path=assignment[i - 1],
                path_index=0,
                state="waiting",
                transit_turns_remaining=0,
            ))

    def run(self) -> None:
        """Run the chosen plan to completion, logging each turn.

        Raises:
            RuntimeError: If no drone moves in a turn (deadlock detected).
        """
        self._build_drones(self._assignment)
        self._simulate(record=True)

    def _simulate(self, *, record: bool) -> int | None:
        """Advance the pre-built fleet until every drone has arrived.

        Args:
            record: When True, capture a snapshot per turn and print the turn
                log, and raise on deadlock. When False, run silently and return
                None on deadlock (used to score candidate plans).

        Returns:
            The number of turns taken, or None if a deadlock occurred during a
            silent run.

        Raises:
            RuntimeError: On deadlock during a recorded run.
        """
        self.turn = 0
        self.turn_moves = []
        self._active_connections = []
        self._arrived_this_turn = set()
        if record:
            self.snapshots = [self._take_snapshot()]

        while not all(drone.is_done() for drone in self.drones):
            self.turn += 1
            self.turn_moves = []
            self._active_connections = []
            self._arrived_this_turn = set()
            self._reset_connections()
            self._tick_transit()
            self._move_drones()
            if not self.turn_moves:
                if record:
                    raise RuntimeError(
                        f"Deadlock detected at turn {self.turn}: "
                        "no drone moved."
                    )
                return None
            if record:
                self.snapshots.append(self._take_snapshot())
                self._print_turn()
        return self.turn

    def _take_snapshot(self) -> TurnSnapshot:
        """Capture the current drone states into a TurnSnapshot.

        Returns:
            A TurnSnapshot reflecting the state at the end of the current turn.
        """
        drones: list[DroneSnapshot] = []
        for drone in self.drones:
            dest = (
                drone.transit_destination.name
                if drone.transit_destination
                else None
            )
            drones.append(
                DroneSnapshot(
                    id=drone.id,
                    zone=drone.current_zone.name,
                    state=drone.state,
                    dest=dest,
                )
            )
        return TurnSnapshot(
            turn=self.turn,
            moves=list(self.turn_moves),
            drones=drones,
            active_connections=list(self._active_connections),
        )

    def _reset_connections(self) -> None:
        """Reset per-turn connection usage counters to zero."""
        for connection in self.graph.connections:
            connection.current_usage = 0

    def _tick_transit(self) -> None:
        """Advance restricted-transit drones by one turn.

        Drones that complete transit this turn are logged for output.
        """
        for drone in self.drones:
            if drone.state != "in_transit":
                continue
            dest_name = (
                drone.transit_destination.name
                if drone.transit_destination
                else None
            )
            drone.tick_transit()
            if drone.state != "in_transit":
                self._arrived_this_turn.add(drone.id)
                self.turn_moves.append(
                    f"{drone.label()}-{drone.current_zone.name}"
                )
                if dest_name:
                    self._active_connections.append(
                        (drone.current_zone.name, dest_name)
                    )

    def _move_drones(self) -> None:
        """Attempt to move each waiting drone one step along its path.

        Checks both connection and destination zone capacity before committing.
        Because drone.start_move() immediately decrements the source zone's
        current_drones, a drone leaving zone X this turn frees a slot for a
        drone entering it in the same pass (matches the spec rule).
        """
        for drone in self.drones:
            if not drone.can_move():
                continue
            # A drone that completed a restricted transit this turn has already
            # used its action (the arrival); it cannot also depart this turn.
            if drone.id in self._arrived_this_turn:
                continue
            next_zone = drone.next_zone()
            if next_zone is None:
                continue

            conn = None
            adj = self.graph.adjacency[drone.current_zone.name]
            for neighbor, connection in adj:
                if neighbor.name == next_zone.name:
                    conn = connection
                    break
            if conn is None:
                continue

            if conn.current_usage >= conn.max_link_capacity:
                continue

            is_unlimited = (
                next_zone.name == self.end.name
                or next_zone.name == self.start.name
            )
            zone_full = next_zone.current_drones >= next_zone.max_drones
            if not is_unlimited and zone_full:
                continue

            source_name = drone.current_zone.name
            drone.start_move(conn)

            self._active_connections.append((source_name, next_zone.name))

            if drone.state == "in_transit":
                td = drone.transit_destination
                dst = td.name  # type: ignore[union-attr]
                # Restricted transit: emit the connection name (source-dest),
                # matching the map file's `name1-name2` connection format.
                self.turn_moves.append(
                    f"{drone.label()}-{source_name}-{dst}"
                )
            else:
                self.turn_moves.append(
                    f"{drone.label()}-{drone.current_zone.name}"
                )

    def _print_turn(self) -> None:
        """Print all drone movements for the current turn on one line."""
        print(" ".join(self.turn_moves))
