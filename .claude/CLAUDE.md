# CLAUDE.md — Fly-in Drone Routing Project

## Project Overview

This is a 42 school project. The goal is to build a drone fleet routing simulation in Python that moves all drones from a start zone to an end zone through a network of connected zones in the fewest possible simulation turns.

The full subject PDF is `en_subject9.pdf`. Read it if you need precise rules.

---

## Hard Constraints (never violate these)

- **Python 3.10+** only
- **No graph libraries** — networkx, graphlib, and similar are strictly forbidden. Implement all graph logic from scratch.
- **Fully object-oriented** — everything must be in classes
- **Fully type-safe** — all functions must have type hints, must pass `mypy` and `flake8` without errors
- **Docstrings** on all classes and functions (Google or NumPy style, PEP 257)
- **Exception handling** — use try/except, never let the program crash on bad input

---

## Project Architecture

```
fly-in/
├── main.py                    # Entry point, CLI argument parsing
├── src/
│   ├── parser/
│   │   └── map_parser.py      # Parses .txt map files into graph objects
│   ├── models/
│   │   ├── zone.py            # Zone class
│   │   ├── connection.py      # Connection class
│   │   ├── graph.py           # Graph class (adjacency, zone/connection storage)
│   │   └── drone.py           # Drone class (state, path, transit)
│   ├── pathfinding/
│   │   ├── dijkstra.py        # Dijkstra shortest path finder (no external libs)
│   │   └── scheduler.py       # Path assignment and departure staggering
│   ├── simulation/
│   │   └── engine.py          # Turn-by-turn simulation loop
│   └── visual/
│       ├── terminal.py        # ANSI colored terminal output
│       └── pygame_display.py  # Pygame graphical interface
├── maps/                      # Map .txt files
├── Makefile
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Map File Format

```
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: obstacleX 5 5 [zone=blocked color=gray]

connection: hub-roof1
connection: corridorA-goal [max_link_capacity=2]
```

### Zone types and movement costs
| Type | Movement cost | Notes |
|------|--------------|-------|
| `normal` | 1 turn | Default |
| `restricted` | 2 turns | Drone occupies connection during transit, MUST arrive next turn |
| `priority` | 1 turn | Same cost as normal but should be preferred by pathfinding |
| `blocked` | ∞ | Cannot be entered, any path through it is invalid |

### Metadata defaults
- `zone=normal` (default if omitted)
- `max_drones=1` (default if omitted) — except start/end which are unlimited
- `max_link_capacity=1` (default if omitted)
- `color` is optional, used for display only

### Parser rules (enforce strictly)
- First line must be `nb_drones: <positive_integer>`
- Exactly one `start_hub` and one `end_hub`
- Zone names: no dashes, no spaces
- No duplicate connections (a-b and b-a are the same)
- Zone types must be one of: normal, blocked, restricted, priority — else raise parse error
- Capacity values must be positive integers
- Connections must reference previously defined zones
- Comments start with `#` and are ignored
- On any parse error: print clear message with line number and cause, then exit

---

## Models

### Zone
```python
class Zone:
    name: str
    x: int
    y: int
    zone_type: str          # "normal" | "restricted" | "priority" | "blocked"
    color: str | None
    max_drones: int         # default 1
    current_drones: int     # tracked during simulation
```

### Connection
```python
class Connection:
    zone_a: Zone
    zone_b: Zone
    max_link_capacity: int  # default 1
    current_usage: int      # drones currently traversing this turn
```

### Graph
```python
class Graph:
    zones: dict[str, Zone]
    connections: list[Connection]
    adjacency: dict[str, list[tuple[Zone, Connection]]]
    start: Zone
    end: Zone
    nb_drones: int
```

### Drone
```python
class Drone:
    id: int                          # D1, D2, etc.
    current_zone: Zone
    path: list[Zone]                 # planned path
    path_index: int                  # current position in path
    state: str                       # "waiting" | "moving" | "in_transit" | "arrived"
    transit_turns_remaining: int     # for restricted zones (starts at 2, counts down)
    transit_destination: Zone | None # where the drone is headed during transit
```

---

## Simulation Rules (engine must enforce all of these)

### Capacity rules
- A zone can hold at most `max_drones` drones at once
- Start zone: unlimited (all drones begin there)
- End zone: unlimited (delivered drones accumulate there)
- A connection can be traversed by at most `max_link_capacity` drones per turn
- Drones moving **out** of a zone free up capacity **that same turn** (so incoming drones can use that slot)

### Movement rules per turn, each drone may
- Move to an adjacent zone (costs 1 turn for normal/priority, 2 turns for restricted)
- Stay in place (wait)
- Be in transit toward a restricted zone (committed, must arrive next turn — cannot wait on connection)

### Restricted zone transit
- Turn 1: drone leaves its zone, enters the connection (shown as `D1-zonea_zoneb` in output)
- Turn 2: drone arrives at restricted zone (shown as `D1-restrictedzone`)
- The drone CANNOT wait on the connection — once committed it must arrive

### Conflict rules
- Two drones cannot enter the same zone on the same turn if it would exceed capacity
- The scheduler must stagger departures to prevent this
- No deadlocks allowed — the engine must always make progress

---

## Output Format

Each turn is one line. List all movements space-separated. Drones that don't move are omitted. Drones that reached the end are no longer tracked.

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

For a drone in transit toward a restricted zone, use the connection name:
```
D1-zonea_zoneb
```

Simulation ends when all drones have reached the end zone.

---

## Pathfinding & Scheduler

### Dijkstra (dijkstra.py)
- Implement Dijkstra's algorithm using Python's `heapq` (stdlib, not a graph lib — allowed)
- Must skip blocked zones entirely
- Edge weights based on **destination** zone type: normal=1, restricted=2, priority=1
- Priority zones must be preferred when costs are tied — use a small bias (e.g. 0.5) or secondary sort key so heapq picks them first
- Returns a list of Zone objects representing the cheapest path
- Must track visited nodes to avoid infinite loops on circular maps

### Dijkstra implementation pattern
```python
import heapq

def dijkstra(graph: Graph, start: Zone, end: Zone) -> list[Zone]:
    # heap entries: (cost, zone_name)
    heap: list[tuple[float, str]] = [(0.0, start.name)]
    costs: dict[str, float] = {start.name: 0.0}
    previous: dict[str, str | None] = {start.name: None}
    visited: set[str] = set()

    while heap:
        current_cost, current_name = heapq.heappop(heap)

        if current_name in visited:
            continue
        visited.add(current_name)

        if current_name == end.name:
            break

        for neighbor, connection in graph.adjacency[current_name]:
            if neighbor.zone_type == "blocked":
                continue

            if neighbor.zone_type == "restricted":
                move_cost = 2.0
            elif neighbor.zone_type == "priority":
                move_cost = 0.9  # cheaper than normal to prefer it
            else:
                move_cost = 1.0

            new_cost = current_cost + move_cost

            if neighbor.name not in costs or new_cost < costs[neighbor.name]:
                costs[neighbor.name] = new_cost
                previous[neighbor.name] = current_name
                heapq.heappush(heap, (new_cost, neighbor.name))

    # Reconstruct path
    path: list[Zone] = []
    node: str | None = end.name
    while node is not None:
        path.append(graph.zones[node])
        node = previous.get(node)
    path.reverse()

    # Return empty list if no path found
    if not path or path[0].name != start.name:
        return []
    return path
```

### Scheduler (scheduler.py)
- Call Dijkstra to get the primary shortest path
- Use a modified Dijkstra (or DFS) to find K alternative paths for multi-path distribution
- Distribute drones across paths to maximize throughput
- Stagger drone departures to avoid capacity conflicts at bottlenecks
- Handle the case where only one path exists (queue drones with timed departures)
- Must coordinate all drones simultaneously — this is the core algorithm challenge

### Algorithm approach
1. Run Dijkstra to find the shortest path
2. Find alternative paths (re-run Dijkstra with temporarily removed edges, or DFS)
3. Assign drones to paths based on path cost and zone capacity along the route
4. Compute staggered departure turns to avoid zone conflicts
5. Run the simulation turn-by-turn, re-checking constraints each turn

---

## Visual Display

### Terminal (terminal.py)
- Use ANSI escape codes (no external lib needed)
- Color zones by type: restricted=orange, priority=cyan, blocked=gray, normal=blue
- Show each turn clearly with drone positions

### Pygame (pygame_display.py)
- Draw zones as circles at their (x, y) coordinates
- Draw connections as lines between zones
- Color zones by type
- Show drones as small dots on their current zone
- Update each turn (step through with keypress or auto-play with delay)
- Show turn counter and drone count

---

## CLI Interface (main.py)

```
python main.py <map_file> [--visual] [--pygame] [--speed <ms>]
```

- `--visual` enables colored terminal output
- `--pygame` opens the pygame window
- `--speed` sets milliseconds between turns in pygame (default 500)
- Without flags: prints only the formatted log output to stdout

---

## Makefile

```makefile
install:
    pip install -r requirements.txt

run:
    python main.py maps/easy/01_linear_path.txt

debug:
    python -m pdb main.py maps/easy/01_linear_path.txt

clean:
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type d -name .mypy_cache -exec rm -rf {} +

lint:
    flake8 .
    mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
    flake8 .
    mypy . --strict
```

---

## Performance Targets

| Map | Drones | Target turns |
|-----|--------|-------------|
| Easy: linear path | 2 | ≤ 6 |
| Easy: simple fork | 3 | ≤ 6 |
| Easy: basic capacity | 4 | ≤ 8 |
| Medium: dead end trap | 5 | ≤ 15 |
| Medium: circular loop | 6 | ≤ 20 |
| Medium: priority puzzle | 4 | ≤ 12 |
| Hard: maze nightmare | 8 | ≤ 45 |
| Hard: capacity hell | 12 | ≤ 60 |
| Hard: ultimate challenge | 15 | ≤ 35 |
| Bonus: impossible dream | 25 | < 41 |

---

## Build Order

1. `models/` — Zone, Connection, Graph, Drone (pure data, no logic yet)
2. `parser/map_parser.py` — parse maps, populate graph, raise errors
3. `pathfinding/dijkstra.py` — Dijkstra shortest path
4. `simulation/engine.py` — turn loop with rules, terminal log output
5. `pathfinding/scheduler.py` — multi-path distribution and staggering
6. `visual/terminal.py` — colored output
7. `visual/pygame_display.py` — graphical interface
8. `main.py` — wire everything together with CLI

---

## Common Pitfalls

- **Circular loops**: Dijkstra must track visited nodes or it loops forever on circular maps
- **Priority bias**: use a cost of 0.9 instead of 1.0 for priority zones so heapq naturally prefers them without breaking the algorithm
- **Restricted transit**: once a drone starts toward a restricted zone it cannot stop — schedule carefully
- **Capacity freed same turn**: if drone A leaves zone X and drone B enters zone X on the same turn, that is valid as long as net occupancy stays within limits
- **Connection direction**: connections are bidirectional — store both directions in adjacency
- **Duplicate connections**: `a-b` and `b-a` in the input file is an error — detect it in the parser
- **Deadlocks**: if all drones are waiting for each other, the simulation hangs — the scheduler must prevent this