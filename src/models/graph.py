
from pydantic import BaseModel, Field
from .connection import Connection
from .zone import Zone


class Graph(BaseModel):
    """The drone routing graph holding zones, connections, and adjacency.

    Attributes:
        zones: Mapping of zone name to :class:`Zone` instance.
        connections: List of all :class:`Connection` instances in the graph.
        adjacency: For each zone name, the list of (neighbor zone, connection)
            tuples reachable from it. Populated bidirectionally.
        start: The designated start hub, set once by the parser.
        end: The designated end hub, set once by the parser.
        nb_drones: Number of drones that must travel from start to end.
    """

    zones: dict[str, Zone] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    adjacency: dict[str, list[tuple[Zone, Connection]]] = Field(
        default_factory=dict
    )
    start: Zone | None = None
    end: Zone | None = None
    nb_drones: int = 0

    def add_zone(self, zone: Zone) -> None:
        """Register a zone and initialize its adjacency list.

        Args:
            zone: The :class:`Zone` to add to the graph. Its name is used
                as the key in both ``zones`` and ``adjacency``.
        """
        self.zones[zone.name] = zone
        self.adjacency[zone.name] = []

    def add_connection(self, conn: Connection) -> None:
        """Register a bidirectional connection between two zones.

        Args:
            conn: The :class:`Connection` to add. Entries are appended to
                the adjacency lists of both ``conn.zone_a`` and
                ``conn.zone_b`` so the link is traversable in either
                direction.
        """
        self.connections.append(conn)
        self.adjacency[conn.zone_a.name].append((conn.zone_b, conn))
        self.adjacency[conn.zone_b.name].append((conn.zone_a, conn))
