from pydantic import ValidationError

from ..models.graph import Graph
from ..models.zone import Zone
from ..models.connection import Connection
from .errors import MapParseError, InvalidType


class MapParser:
    """Parses map .txt files into Graph objects."""

    def __init__(self, path: str) -> None:
        """Store the path to the map file to parse.

        Args:
            path: Filesystem path to a ``.txt`` map file.
        """
        self.path = path

    def _err(self, i: int, msg: str) -> MapParseError:
        """Build a MapParseError prefixed with the line number.

        Args:
            i: Zero-based line index.
            msg: Error message body.
        Returns:
            A MapParseError with prefix ``line {i+1}: {msg}``.
        """
        return MapParseError(f"line {i + 1}: {msg}")

    def _parse_int(
        self, raw: str, field: str, i: int, min_value: int | None = 1
    ) -> int:
        """Convert raw to int and optionally validate a lower bound.

        Args:
            raw: The string to convert.
            field: Field name for error messages.
            i: Zero-based line index.
            min_value: Minimum allowed value, or None to skip the check.
                Defaults to 1.
        Returns:
            The parsed integer.
        Raises:
            MapParseError: If raw is not an integer or is below min_value.
        """
        try:
            value = int(raw)
        except ValueError:
            raise self._err(i, f"{field} must be an integer, got '{raw}'")
        if min_value is not None and value < min_value:
            raise self._err(
                i, f"{field} must be >= {min_value}, got {value}"
            )
        return value

    def _parse_metadata(self, line: str, i: int) -> dict[str, str]:
        """Extract key=value pairs from the line's ``[...]`` block.

        Args:
            line: A raw line from the map file, possibly containing a
                bracketed metadata section like
                ``[color=green max_drones=2]``.
            i: Zero-based line index for error reporting.
        Returns:
            A dict mapping each metadata key to its string value. Empty
            if the line has no ``[...]`` block.
        Raises:
            MapParseError: If brackets are mismatched, a token is
                missing ``=``, or a key/value is empty.
        """
        if "[" not in line:
            return {}
        after_open = line.split("[", 1)[1]
        if "]" not in after_open:
            raise self._err(i, "mismatched metadata brackets")
        inside = after_open.split("]", 1)[0]
        result: dict[str, str] = {}
        for pair in inside.split():
            if "=" not in pair:
                raise self._err(
                    i, f"invalid metadata token '{pair}', expected key=value"
                )
            k, v = pair.split("=", 1)
            if not k or not v:
                raise self._err(i, f"empty metadata key or value in '{pair}'")
            result[k] = v
        return result

    def _parse_zone_line(self, line: str, i: int, graph: Graph) -> Zone:
        """Build a Zone from a ``start_hub``/``end_hub``/``hub`` line.

        Args:
            line: The stripped line to parse.
            i: Zero-based line index for error reporting.
            graph: The graph being built, used to detect duplicate zone
                names.
        Returns:
            A populated :class:`Zone` with name, coordinates, and any
            metadata (color, max_drones, zone_type) applied.
        Raises:
            MapParseError: If brackets are mismatched, the body is
                malformed, the name contains ``-``, the name duplicates
                an existing zone, or any field fails model validation.
        """
        if ("[" in line) != ("]" in line):
            raise self._err(i, "mismatched metadata brackets")
        body = line.split(":", 1)[1].split("[", 1)[0]
        parts = body.split()
        if len(parts) != 3:
            raise self._err(
                i,
                f"expected 'name x y' after directive, got '{body.strip()}'",
            )
        name, x_raw, y_raw = parts
        if "-" in name:
            raise self._err(i, f"zone name '{name}' must not contain '-'")
        if name in graph.zones:
            raise self._err(i, f"duplicate zone name '{name}'")
        x = self._parse_int(x_raw, "x", i, min_value=None)
        y = self._parse_int(y_raw, "y", i, min_value=None)
        meta = self._parse_metadata(line, i)
        max_drones = self._parse_int(
            meta.get("max_drones", "1"), "max_drones", i
        )
        try:
            return Zone(
                name=name,
                x=x,
                y=y,
                color=meta.get("color"),
                max_drones=max_drones,
                zone_type=meta.get("zone", "normal"),
            )
        except (InvalidType, ValidationError) as e:
            raise self._err(i, str(e))

    def _parse_connection(
        self, line: str, i: int, graph: Graph
    ) -> Connection:
        """Build a Connection from a ``connection`` line.

        Args:
            line: The stripped line to parse.
            i: Zero-based line index for error reporting.
            graph: The graph being built, used to look up referenced
                zones and to check for duplicates.
        Returns:
            A populated :class:`Connection` with ``max_link_capacity``
            applied (defaults to 1).
        Raises:
            MapParseError: If brackets are mismatched, the body is
                malformed, the connection is a self-loop, either zone
                is unknown, the connection duplicates an existing one,
                or the field fails model validation.
        """
        if ("[" in line) != ("]" in line):
            raise self._err(i, "mismatched metadata brackets")
        body = line.split(":", 1)[1].split("[", 1)[0].strip()
        parts = body.split("-")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise self._err(i, f"expected 'zone_a-zone_b', got '{body}'")
        name_a, name_b = parts
        if name_a == name_b:
            raise self._err(
                i, f"self-loop connection '{name_a}-{name_b}' not allowed"
            )
        if name_a not in graph.zones:
            raise self._err(i, f"unknown zone '{name_a}'")
        if name_b not in graph.zones:
            raise self._err(i, f"unknown zone '{name_b}'")
        for existing in graph.connections:
            existing_pair = {existing.zone_a.name, existing.zone_b.name}
            if existing_pair == {name_a, name_b}:
                raise self._err(
                    i, f"duplicate connection '{name_a}-{name_b}'"
                )
        meta = self._parse_metadata(line, i)
        max_cap = self._parse_int(
            meta.get("max_link_capacity", "1"), "max_link_capacity", i
        )
        try:
            return Connection(
                zone_a=graph.zones[name_a],
                zone_b=graph.zones[name_b],
                max_link_capacity=max_cap,
            )
        except (InvalidType, ValidationError) as e:
            raise self._err(i, str(e))

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
            MapParseError: If the file cannot be read, any directive
                is malformed, a zone reference is unknown, a connection
                is duplicated, or the map is missing any of
                ``nb_drones``, ``start_hub``, or ``end_hub``.
        """
        graph = Graph()
        try:
            with open(self.path) as f:
                lines = f.readlines()
        except OSError as e:
            raise MapParseError(f"cannot read map '{self.path}': {e}")

        nb_drones_set = False
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("nb_drones:"):
                if nb_drones_set:
                    raise self._err(i, "duplicate nb_drones directive")
                raw = line.split(":", 1)[1].strip()
                graph.nb_drones = self._parse_int(raw, "nb_drones", i)
                nb_drones_set = True
            elif line.startswith("start_hub:"):
                if graph.start is not None:
                    raise self._err(i, "duplicate start_hub directive")
                zone = self._parse_zone_line(line, i, graph)
                graph.add_zone(zone)
                graph.start = zone
            elif line.startswith("end_hub:"):
                if graph.end is not None:
                    raise self._err(i, "duplicate end_hub directive")
                zone = self._parse_zone_line(line, i, graph)
                graph.add_zone(zone)
                graph.end = zone
            elif line.startswith("hub:"):
                zone = self._parse_zone_line(line, i, graph)
                graph.add_zone(zone)
            elif line.startswith("connection:"):
                connection = self._parse_connection(line, i, graph)
                graph.add_connection(connection)
            else:
                first = line.split(":", 1)[0]
                raise self._err(i, f"unknown directive '{first}'")

        if not nb_drones_set:
            raise MapParseError("missing nb_drones directive")
        if graph.start is None:
            raise MapParseError("missing start_hub directive")
        if graph.end is None:
            raise MapParseError("missing end_hub directive")
        return graph
