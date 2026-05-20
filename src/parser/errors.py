
class InvalidType(Exception):
    """Base exception for all map validation and parsing errors."""
    pass


class MaxDrones(InvalidType):
    """Raised when a zone's max_drones value is not a positive integer."""
    pass


class InvalidZone(InvalidType):
    """Raised when a zone_type is not one of the allowed values."""
    pass


class MaxCapacity(InvalidType):
    """Raised when a connection's max_link_capacity is not positive."""
    pass


class MapParseError(InvalidType):
    """Raised when the map file contains malformed or invalid directives."""
    pass
