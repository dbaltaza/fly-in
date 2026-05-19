# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

42 school project: build a drone fleet routing simulation in Python that moves all drones from a start zone to an end zone through a network of connected zones in the fewest possible simulation turns.

The full subject is in `SUBJECT.md`. Read it for precise rules.

---

## Commands

```bash
# Install dependencies (uses .venv)
python -m venv .venv && pip install -r requirements.txt

# Run parser tests
.venv/bin/python -m tests.test_parser

# Run the simulation (entry point — currently wired to parser only)
python main.py

# Lint
flake8 .
mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

# Clean pycache
find . -type d -name __pycache__ -exec rm -rf {} +
```

---

## Hard Constraints (never violate)

- **Python 3.10+** only — project runs on `.venv` with Python 3.14
- **No graph libraries** — networkx, graphlib, etc. are forbidden; all graph logic is hand-rolled
- **Fully object-oriented** — everything in classes
- **Type-safe** — all functions need type hints; must pass `mypy` and `flake8`
- **Docstrings** — on all classes and functions (Google style, PEP 257)
- **Exception handling** — use try/except; never crash on bad input

---

## Implementation Status

| Module | Status |
|--------|--------|
| `src/models/` — Zone, Connection, Graph | Done |
| `src/parser/parser.py` — MapParser | Done |
| `src/parser/errors.py` — exception hierarchy | Done |
| `tests/test_parser.py` — parser test suite | Done |
| `src/pathfinding/dijkstra.py` | Done |
| `src/models/drone.py` | Empty |
| `src/simulation/engine.py` | Empty |
| `src/pathfinding/scheduler.py` | Missing |
| `src/visual/terminal.py` | Missing |
| `src/visual/pygame_display.py` | Missing |
| `main.py` | Minimal — calls parser, prints `graph.zones` |

**Next step in build order:** implement `drone.py`, then `engine.py`, then `scheduler.py`.

---

## Architecture

### Key design choices already made

**Pydantic models** — Zone, Connection, and Graph are `pydantic.BaseModel` subclasses (not plain dataclasses). Validators use `@field_validator`. This is an intentional dependency (`requirements.txt`).

**Custom exception hierarchy** (`src/parser/errors.py`):
- `InvalidType` — base class
- `MapParseError` — malformed map file
- `InvalidZone` — bad zone_type value
- `MaxDrones` / `MaxCapacity` — capacity validation failures

**Graph adjacency** — bidirectional: `add_connection()` appends `(neighbor, conn)` to both endpoints' adjacency lists. Adjacency type is `dict[str, list[tuple[Zone, Connection]]]`.

**Parser** — `MapParser(path).parse()` returns a fully populated `Graph`. All errors are `MapParseError` with a `line {n}: ...` prefix.

### Dijkstra spec (see CLAUDE.md in `.claude/` for full pattern)

- Use `heapq` (stdlib — allowed)
- Skip `blocked` zones
- Costs: normal=1.0, restricted=2.0, priority=0.9 (cheaper to prefer it)
- Return `list[Zone]` from start to end inclusive; empty list if no path

### Simulation output format

One line per turn, space-separated drone moves. Drones that don't move are omitted:
```
D1-roof1 D2-corridorA
D1-goal
```
For a drone in transit through a restricted zone (2-turn move), use connection name:
```
D1-zonea_zoneb
```

### Capacity rules

- Zones cap at `max_drones` (start/end are unlimited)
- Connections cap at `max_link_capacity` per turn
- A drone leaving a zone frees its slot **that same turn** (outgoing before incoming)

### Restricted zone transit

- Turn 1: drone leaves source, shown as `D1-zonea_zoneb` (on the connection)
- Turn 2: drone arrives at restricted zone
- Cannot wait mid-connection — once committed, must arrive

---

## Maps

Located in `maps/` with subdirectories `easy/`, `medium/`, `hard/`, `challenger/`. Format:

```
nb_drones: 5
start_hub: name x y [color=green]
end_hub: name x y
hub: name x y [zone=restricted color=red max_drones=2]
connection: zone_a-zone_b [max_link_capacity=2]
```

Zone names: no dashes, no spaces. Comments start with `#`.

---

## Performance Targets

| Map | Drones | Target turns |
|-----|--------|-------------|
| Easy: linear path | 2 | ≤ 6 |
| Easy: simple fork | 4 | ≤ 8 |
| Easy: basic capacity | 4 | ≤ 6 |
| Medium: dead end trap | 5 | ≤ 12 |
| Medium: circular loop | 6 | ≤ 15 |
| Medium: priority puzzle | 5 | ≤ 12 |
| Hard: maze nightmare | 8 | ≤ 30 |
| Hard: capacity hell | 12 | ≤ 35 |
| Hard: ultimate challenge | 15 | ≤ 45 |
| Challenger: impossible dream | 25 | ≤ 45 (reference record) |
