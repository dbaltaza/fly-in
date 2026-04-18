from pydantic import BaseModel, field_validator
from .zone import Zone
from ..parser.c_errors import MaxCapacity


class Connection(BaseModel):
    """A bidirectional link between two zones."""

    zone_a: Zone
    zone_b: Zone
    max_link_capacity: int = 1
    current_usage: int = 0

    @field_validator("max_link_capacity")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Validate max_link_capacity is positive."""
        if v < 1:
            raise MaxCapacity(f"max_link_capacity must be >= 1, got {v}")
        return v
