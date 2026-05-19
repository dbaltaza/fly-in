"""Entry point for the fly-in drone routing simulation."""

import argparse
import sys

from src.parser.parser import MapParser
from src.parser.errors import MapParseError
from src.simulation.engine import SimulationEngine


def main() -> None:
    """Parse CLI arguments, load the map, and run the simulation."""
    parser = argparse.ArgumentParser(
        description="Drone fleet routing simulation."
    )
    parser.add_argument("map_file", help="Path to the map .txt file")
    parser.add_argument(
        "--pygame",
        action="store_true",
        help="Open a pygame window to replay the simulation visually.",
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=500,
        metavar="MS",
        help="Milliseconds between turns in auto-play mode (default: 500).",
    )
    args = parser.parse_args()

    try:
        graph = MapParser(args.map_file).parse()
    except MapParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        engine = SimulationEngine(graph)
        engine.run()
    except (ValueError, RuntimeError) as e:
        print(f"Simulation error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.pygame:
        from src.visual.pygame_display import PygameDisplay
        path = [z.name for z in engine.drones[0].path] if engine.drones else []
        PygameDisplay(
            graph,
            engine.snapshots,
            speed_ms=args.speed,
            primary_path=path,
            dijkstra_steps=engine.dijkstra_steps,
        ).run()


if __name__ == "__main__":
    main()
