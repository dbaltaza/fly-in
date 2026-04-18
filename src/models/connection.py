from pydantic import BaseModel, field_validator
from .zone import Zone
from ..parser.errors import MaxCapacity


class Connection(BaseModel):
    """A bidirectional link between two zones.

    Attributes:
        zone_a: One end of the connection.
        zone_b: The other end of the connection.
        max_link_capacity: Maximum drones that can traverse per turn.
                            Defaults to 1.
        current_usage: Number of drones currently traversing this turn.
    """

    zone_a: Zone
    zone_b: Zone
    max_link_capacity: int = 1
    current_usage: int = 0

    @field_validator("max_link_capacity")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Ensure max_link_capacity is a positive integer."""
        if v < 1:
            raise MaxCapacity(f"max_link_capacity must be >= 1, got {v}")
        return v
