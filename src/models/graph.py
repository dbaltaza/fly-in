
from pydantic import BaseModel, Field
from .connection import Connection
from .zone import Zone


class Graph(BaseModel):
    """The drone routing graph holding zones, connections, and adjacency."""

    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    adjacency: dict[str, list[tuple[Zone, Connection]]] = Field(
        default_factory=dict
    )
    start: Zone | None = None
    end: Zone | None = None
    nb_drones: int = 0

    def add_zone(self, zone: Zone) -> None:
        """Register a zone and initialize its adjacency list."""
        self.zones[zone.name] = zone
        self.adjacency[zone.name] = []

    def add_connection(self, conn: Connection) -> None:
        """Register a bidirectional connection between two zones."""
        self.connections.append(conn)
        self.adjacency[conn.zone_a.name].append((conn.zone_b, conn))
        self.adjacency[conn.zone_b.name].append((conn.zone_a, conn))
