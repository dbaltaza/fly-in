from pydantic import BaseModel, ConfigDict
from .zone import Zone
from .connection import Connection


class Drone(BaseModel):
    """A drone navigating from the start zone to the end zone.

    Attributes:
        id: Unique numeric identifier, used to build the display label.
        current_zone: The zone the drone currently occupies.
        path: Ordered list of zones from start to end, planned by Dijkstra.
        path_index: Index of the drone's current position within path.
        state: One of 'waiting', 'in_transit', or 'arrived'.
        transit_turns_remaining: Countdown for restricted transit (2 → 0).
        transit_destination: Target zone during restricted transit, else None.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int
    current_zone: Zone
    path: list[Zone]
    path_index: int
    state: str
    transit_turns_remaining: int
    transit_destination: Zone | None = None

    def label(self) -> str:
        """Return the display label for output, e.g. 'D1'."""
        return f"D{self.id}"

    def is_done(self) -> bool:
        """Return True if the drone has reached the end zone."""
        return self.state == "arrived"

    def next_zone(self) -> Zone | None:
        """Return the next Zone in path, or None if already at the end.

        Returns:
            The Zone at path_index + 1, or None if no further zone exists.
        """
        next_index = self.path_index + 1
        if next_index >= len(self.path):
            return None
        else:
            return self.path[next_index]

    def can_move(self) -> bool:
        """Return True if the drone can attempt to move this turn."""
        return self.state == "waiting"

    def start_move(self, connection: Connection) -> None:
        """Commit this drone to moving toward next_zone via the connection.

        Frees the current zone's capacity and claims the connection. Completes
        the move immediately for normal/priority zones, or enters restricted
        transit for arrival next turn.

        Args:
            connection: The Connection being traversed toward next_zone.
        """
        nz = self.next_zone()
        if nz is None:
            return
        self.current_zone.current_drones -= 1
        connection.current_usage += 1
        if nz.zone_type == "restricted":
            self.state = "in_transit"
            self.transit_destination = nz
            self.transit_turns_remaining = 1
        else:
            self.arrive(nz)

    def tick_transit(self) -> None:
        """Advance restricted transit by one turn.

        Decrements transit_turns_remaining. When it hits zero, completes
        arrival: updates current_zone, clears transit fields, updates state.
        """
        self.transit_turns_remaining -= 1
        if self.transit_turns_remaining == 0:
            if self.transit_destination is None:
                return
            dest = self.transit_destination
            self.arrive(dest)
            self.transit_destination = None
            self.transit_turns_remaining = 0

    def arrive(self, zone: Zone) -> None:
        """Land the drone in the given zone.

        Updates current_zone and zone occupancy, advances path_index, and
        sets state to 'arrived' if this is the final zone, else 'waiting'.

        Args:
            zone: The Zone the drone is landing in.
        """
        self.current_zone = zone
        self.path_index += 1
        zone.current_drones += 1
        if zone.name == self.path[-1].name:
            self.state = "arrived"
        else:
            self.state = "waiting"
