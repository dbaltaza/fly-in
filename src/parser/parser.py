from ..models.graph import Graph
from ..models.zone import Zone
from ..models.connection import Connection
from .errors import MapParseError


class MapParser:
    """Parses map .txt files into Graph objects."""

    def __init__(self, path: str) -> None:
        """Store the path to the map file to parse.

        Args:
            path: Filesystem path to a ``.txt`` map file.
        """
        self.path = path

    def _parse_metadata(self, line: str) -> dict[str, str]:
        """Extract key=value pairs from the line's [...] block.

        Args:
            line: A raw line from the map file, possibly containing a
                bracketed metadata section like ``[color=green max_drones=2]``.
        Returns:
            A dict mapping each metadata key to its string value. Empty
            if the line has no ``[...]`` block.
        """
        if "[" not in line:
            return {}
        inside = line.split("[", 1)[1]
        inside = inside[:-1]
        pairs = inside.split()      # ["color=green", "max_drones=2"]
        result: dict[str, str] = {}
        for pair in pairs:
            k, v = pair.split("=", 1)
            result[k] = v
        return result
    
    def _parse_zone_line(self, line: str, i: int) -> Zone:
        """Build a Zone from a ``start_hub``/``end_hub``/``hub`` line.

        Args:
            line: The stripped line to parse.
            i: Zero-based line index, used to report accurate line numbers
                in error messages.
        Returns:
            A populated :class:`Zone` with name, coordinates, and any
            metadata (color, max_drones, zone_type) applied.
        Raises:
            MapParseError: If brackets are mismatched or the body is
                missing coordinate values.
        """
        if ("[" in line) != ("]" in line):
            raise MapParseError(f"line {i + 1}: mismatched "
                                "metadata brackets")
        if "-" not in line:
            raise MapParseError(f"Error on the sintax on line {i + 1}")
        try:
            body = line.split(":", 1)[1].split("[", 1)[0]
            name, x, y = body.split()
        except ValueError:
            raise MapParseError(f"line {i + 1}: missing value for x or y")
        meta = self._parse_metadata(line)
        return Zone(
            name=name,
            x=int(x),
            y=int(y),
            color=meta.get("color"),
            max_drones=int(meta.get("max_drones", 1)),
            zone_type=meta.get("zone", "normal"),
        )
    
    def _parse_connection(self, line: str, i: int, graph: Graph) -> Connection:
        """Build a Connection from a ``connection`` line.

        Args:
            line: The stripped line to parse.
            i: Zero-based line index, used to report accurate line numbers
                in error messages.
            graph: The graph being built, used to look up referenced zones
                and to check for duplicate connections.

        Returns:
            A populated :class:`Connection` between the two named zones,
            with ``max_link_capacity`` applied from metadata (defaults to 1).
        Raises:
            MapParseError: If brackets are mismatched, the connection
                duplicates an existing one (order-independent), or either
                zone name is unknown.
        """
        if ("[" in line) != ("]" in line):
            raise MapParseError(f"line {i + 1}: mismatched "
                                "metadata brackets")
        body = line.split(":", 1)[1].split("[", 1)[0].strip()   # "hub-roof1"
        name_a, name_b = body.split("-")
        for existing in graph.connections:
            existing_pair = {existing.zone_a.name, existing.zone_b.name}
            if existing_pair == {name_a, name_b}:
                raise MapParseError(
                    f"line {i+1}: duplicate connection '{name_a}-{name_b}'"
                )
        if name_a not in graph.zones:
            raise MapParseError(f"line {i+1}: unknown zone '{name_a}'")
        if name_b not in graph.zones:
            raise MapParseError(f"line {i+1}: unknown zone '{name_b}'")
        meta = self._parse_metadata(line)
        max_cap = int(meta.get("max_link_capacity", 1))
        return Connection(
            zone_a=graph.zones[name_a],
            zone_b=graph.zones[name_b],
            max_link_capacity=max_cap,
        )

    def parse(self) -> Graph:
        """Parse the map file and return a populated Graph.

        Reads the file line by line, dispatching to the appropriate
        handler for ``nb_drones``, ``start_hub``, ``end_hub``, ``hub``,
        and ``connection`` directives. Blank lines and comments (``#``)
        are skipped.

        Returns:
            A fully populated :class:`Graph` with zones, connections,
            adjacency, start, end, and nb_drones all set.
        Raises:
            MapParseError: If any directive is malformed, a zone
                reference is unknown, a connection is duplicated, or
                the map is missing a start/end hub.
        """
        graph = Graph()
        try:
            with open(self.path) as f:
                lines = f.readlines()
        except Exception as e:
            raise MapParseError(f"{e}")

        nb_drones_set = False
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            elif line.startswith("nb_drones:"):
                if nb_drones_set:
                    raise MapParseError(f"line {i+1}: duplicate nb_drones "
                                        "directive")
                raw = line.split(":", 1)[1].strip()
                try:
                    value = int(raw)
                except ValueError:
                    raise MapParseError(f"line {i+1}: nb_drones must be an "
                                        f"integer, got '{raw}'")
                if value < 1:
                    raise MapParseError(f"line {i+1}: nb_drones must be >= 1, "
                                        f"got {value}")
                graph.nb_drones = value
                nb_drones_set = True

            elif line.startswith("start_hub:") and graph.start is None:
                zone = self._parse_zone_line(line, i)
                graph.add_zone(zone)
                graph.start = zone
            elif line.startswith("end_hub:") and graph.end is None:
                zone = self._parse_zone_line(line, i)
                graph.add_zone(zone)
                graph.end = zone
            elif line.startswith("hub:"):
                zone = self._parse_zone_line(line, i)
                graph.add_zone(zone)
            elif line.startswith("connection:"):
                connection = self._parse_connection(line, i, graph)
                graph.add_connection(connection)
            else:
                raise MapParseError(f"line {i+1}: unknown "
                                    f"directive '{line.split(':', 1)[0]}'")
            
        if not graph.start:
            raise MapParseError("Start not set!")
        if not graph.end:
            raise MapParseError("End not set!")
        if not nb_drones_set:  
            raise MapParseError("Missing nb_drones directive!")
        return graph
