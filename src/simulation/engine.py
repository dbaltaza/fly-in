from typing import TypedDict

from ..models.graph import Graph
from ..models.zone import Zone
from ..models.drone import Drone
from ..pathfinding.dijkstra import dijkstra_with_steps, DijkstraStep


class DroneSnapshot(TypedDict):
    """State of one drone captured at the end of a turn.

    Attributes:
        id: Drone identifier number.
        zone: Name of the zone the drone currently occupies (source if in_transit).
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
        moves: Move strings emitted this turn (e.g. ['D1-roof1', 'D2-corridorA']).
        drones: Snapshot of every drone's state.
        active_connections: Zone-name pairs for connections traversed this turn.
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
        self._active_connections: list[tuple[str, str]] = []
        self.dijkstra_steps: list[DijkstraStep] = []

        path, self.dijkstra_steps = dijkstra_with_steps(graph, self.start, self.end)
        if not path:
            raise ValueError("No path exists from start to end zone.")

        self.start.current_drones = graph.nb_drones
        for i in range(1, graph.nb_drones + 1):
            drone = Drone(
                id=i,
                current_zone=graph.start,
                path=path,
                path_index=0,
                state="waiting",
                transit_turns_remaining=0,
            )
            self.drones.append(drone)

        self.snapshots.append(self._take_snapshot())

    def run(self) -> None:
        """Run the simulation until all drones reach the end zone.

        Raises:
            RuntimeError: If no drone moves in a turn (deadlock detected).
        """
        while not all(drone.is_done() for drone in self.drones):
            self.turn += 1
            self.turn_moves = []
            self._active_connections = []
            self._reset_connections()
            self._tick_transit()
            self._move_drones()
            if not self.turn_moves:
                raise RuntimeError(
                    f"Deadlock detected at turn {self.turn}: no drone moved."
                )
            self.snapshots.append(self._take_snapshot())
            self._print_turn()

    def _take_snapshot(self) -> TurnSnapshot:
        """Capture the current drone states into a TurnSnapshot.

        Returns:
            A TurnSnapshot reflecting the state at the end of the current turn.
        """
        drones: list[DroneSnapshot] = []
        for drone in self.drones:
            dest = drone.transit_destination.name if drone.transit_destination else None
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
            dest_name = drone.transit_destination.name if drone.transit_destination else None
            drone.tick_transit()
            if drone.state != "in_transit":
                self.turn_moves.append(f"{drone.label()}-{drone.current_zone.name}")
                if dest_name:
                    self._active_connections.append((drone.current_zone.name, dest_name))

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
            next_zone = drone.next_zone()
            if next_zone is None:
                continue

            conn = None
            for neighbor, connection in self.graph.adjacency[drone.current_zone.name]:
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
            if not is_unlimited and next_zone.current_drones >= next_zone.max_drones:
                continue

            source_name = drone.current_zone.name
            drone.start_move(conn)

            self._active_connections.append((source_name, next_zone.name))

            if drone.state == "in_transit":
                dst = drone.transit_destination.name  # type: ignore[union-attr]
                self.turn_moves.append(f"{drone.label()}-{source_name}_{dst}")
            else:
                self.turn_moves.append(f"{drone.label()}-{drone.current_zone.name}")

    def _print_turn(self) -> None:
        """Print all drone movements for the current turn on one line."""
        print(" ".join(self.turn_moves))
