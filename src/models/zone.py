
from pydantic import BaseModel, field_validator
from ..parser.c_errors import InvalidZone, MaxDrones


class Zone(BaseModel):
    """A node in the drone routing graph.

    Attributes:
        name: Unique zone identifier (no spaces or dashes).
        x: X coordinate used for display.
        y: Y coordinate used for display.
        zone_type: One of "normal", "blocked", "restricted", "priority".
        color: Optional display color.
        max_drones: Maximum drones allowed in the zone at once. Defaults to 1.
        current_drones: Number of drones currently occupying the zone.
    """

    name: str
    x: int
    y: int
    zone_type: str = "normal"
    color: str | None = None
    max_drones: int = 1
    current_drones: int = 0

    @field_validator("zone_type")
    @classmethod
    def validate_zone_type(cls, v: str) -> str:
        """Ensure zone_type is one of the four allowed values.

        Args:
            v: The zone_type value provided at construction.
        Returns:
            The validated zone_type string.
        Raises:
            InvalidZone: If v is not one of the allowed zone types.
        """
        allowed = {"normal", "blocked", "restricted", "priority"}
        if v not in allowed:
            raise InvalidZone(
                f"'{v}' is not a valid zone type, must be one of {allowed}"
            )
        return v

    @field_validator("max_drones")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Ensure max_drones is a positive integer.

        Args:
            v: The max_drones value provided at construction.
        Returns:
            The validated max_drones integer.
        Raises:
            MaxDrones: If v is less than 1.
        """
        if v < 1:
            raise MaxDrones(f"max_drones must be >= 1, got {v}")
        return v
