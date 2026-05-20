*This project has been created as part of the 42 curriculum by dbaltaza.*

# fly-in — Drone Fleet Routing Simulation

## Description

A drone fleet routing simulation written in Python. Given a map of connected zones, the program moves all drones from a start hub to an end hub in the fewest possible simulation turns, respecting zone capacity limits, connection bandwidth limits, and restricted-zone transit rules.

The system parses a custom map format, runs Dijkstra's algorithm to find the optimal path, simulates turn-by-turn drone movement with full constraint enforcement, and provides a graphical replay via pygame.

## Instructions

### Install

```bash
make install
```

Requires Python 3.10+. Creates a `.venv` and installs all dependencies from `requirements.txt`.

### Run

```bash
make run                                    # default: easy linear path map
make run MAP=maps/hard/02_capacity_hell.txt # specify a map
```

Text output (one line per turn, space-separated drone moves) is printed to stdout:

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

### Pygame visual replay

```bash
.venv/bin/python main.py maps/hard/02_capacity_hell.txt --pygame
.venv/bin/python main.py maps/hard/02_capacity_hell.txt --pygame --speed 300
```

Controls inside the window:

| Key | Action |
|-----|--------|
| Space / → | Next turn |
| ← | Previous turn |
| A | Toggle auto-play |
| + / - | Speed up / slow down |
| Scroll wheel | Zoom in / out |
| Middle-drag | Pan view |
| F / 0 | Fit all zones on screen |
| D | Toggle Dijkstra algorithm replay |
| Q / Esc | Quit |

### Debug

```bash
make debug MAP=maps/medium/01_dead_end_trap.txt
```

### Lint

```bash
make lint         # flake8 + mypy (standard)
make lint-strict  # flake8 + mypy --strict
```

### Clean

```bash
make clean
```

## Resources

### References

- [Dijkstra's algorithm — Wikipedia](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
- [Python heapq — stdlib docs](https://docs.python.org/3/library/heapq.html)
- [Python typing — stdlib docs](https://docs.python.org/3/library/typing.html)
- [Pydantic v2 — docs](https://docs.pydantic.dev/latest/)
- [pygame-ce — docs](https://pyga.me/docs/)

### AI usage

Claude (Anthropic) was used throughout this project as a development assistant. Specific tasks:

- **Parser**: AI helped structure the regex-based line parser and the custom exception hierarchy.
- **Dijkstra**: AI suggested using a cost of `0.9` for priority zones (instead of `1.0`) so `heapq` naturally prefers them without extra tie-breaking logic.
- **Simulation engine**: AI helped reason through the same-turn capacity freeing rule (drones leaving a zone free their slot before incoming drones are checked).
- **Pygame display**: AI implemented the adaptive zone sizing, mouse-centered zoom, drone animation (linear interpolation between snapshots, two-phase waypoint animation for restricted-zone pass-throughs), and the Dijkstra algorithm step replay overlay.
- **Type safety**: AI helped resolve mypy errors and maintain full type annotation coverage.

All generated code was reviewed, tested against all provided maps, and understood before being kept.

## Algorithm choices

### Pathfinding — Dijkstra with zone-type cost bias

A single Dijkstra run from start to end is performed at startup. Edge costs are assigned by **destination zone type**:

| Zone type | Cost |
|-----------|------|
| `normal` | 1.0 |
| `priority` | 0.9 |
| `restricted` | 2.0 |
| `blocked` | skipped entirely |

Using `0.9` for priority zones (rather than `1.0` with a tie-breaker) means `heapq` automatically settles priority zones first at equal distance — no secondary sort key needed.

The algorithm records every settle event as a `DijkstraStep`, enabling the graphical replay of the algorithm frame by frame (press D in the pygame window).

### Simulation — greedy single-path with staggered departure

All drones follow the same Dijkstra path. The engine processes each turn in two phases:

1. **Tick transit**: advance any drone mid-way through a restricted zone (turn 2 of a 2-turn move).
2. **Move waiting drones**: for each waiting drone, attempt to move to its next path zone. Checks:
   - Connection `max_link_capacity` not exceeded this turn.
   - Destination zone `max_drones` not exceeded (start and end zones are unlimited).
   - Drones that departed earlier in the same pass have already freed their source slot.

This same-pass slot freeing is the key scheduling insight: drone A leaves zone X → slot freed → drone B can enter zone X in the same turn. This naturally staggers the fleet without a separate scheduler.

A deadlock guard raises `RuntimeError` if no drone moves in a turn.

### Restricted zone transit

A restricted zone costs 2 turns. On turn 1 the drone commits to the crossing (shown as `D1-zonea_zoneb` in output). On turn 2 it arrives. The drone cannot stop mid-connection — once committed it must arrive.

### Performance results

| Map | Drones | Target | Achieved |
|-----|--------|--------|----------|
| Easy: linear path | 2 | ≤ 6 | **4** |
| Easy: simple fork | 4 | ≤ 8 | **6** |
| Easy: basic capacity | 4 | ≤ 6 | **4** |
| Medium: dead end trap | 5 | ≤ 12 | **8** |
| Medium: circular loop | 6 | ≤ 15 | **9** |
| Medium: priority puzzle | 5 | ≤ 12 | **8** |
| Hard: maze nightmare | 8 | ≤ 30 | **13** |
| Hard: capacity hell | 12 | ≤ 35 | **16** |
| Hard: ultimate challenge | 15 | ≤ 45 | **26** |
| Challenger: impossible dream | 25 | ref 45 | **39** ✓ |

## Visual representation

### Pygame graphical interface (`--pygame`)

The pygame window uses a dark cyberpunk theme and renders the graph as a force-directed-style node diagram positioned exactly at each zone's map coordinates.

**Zone nodes** are drawn as filled circles sized adaptively to the current zoom level. Color encodes zone type (green = start, yellow = end, blue = normal, orange/red = restricted, teal = priority, dark = blocked). A capacity arc around each node shows current occupancy as a fraction of `max_drones`. A badge above-right shows the drone count when occupied.

**Connections** are drawn as lines. Active connections (traversed this turn) glow gold with an arrowhead at the midpoint indicating direction of travel.

**Drones** are animated smoothly between turns using smoothstep easing. In-transit drones (mid restricted-zone crossing) sit at the midpoint of their connection and turn gold. When a drone passes through a restricted zone in a single engine turn (arrives and immediately departs), a two-phase waypoint animation ensures it visibly touches the hub rather than skipping it.

**Dijkstra replay** (press D): overlays the algorithm's state step by step. Settled zones are dimmed, the currently settling zone pulses cyan, frontier zones glow gold with their cost displayed, and the cheapest path from start to the current zone is drawn in blue. When the end zone is settled the final shortest path glows green. The side panel shows the frontier queue, path-to-current, and explored-zone progress.

**Navigation**: mouse-wheel zoom (centered on cursor), middle-mouse-button drag to pan, F/0 to fit all zones. A clickable timeline at the bottom lets you jump to any turn.
