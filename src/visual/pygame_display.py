"""Pygame graphical display for the drone routing simulation."""

import math
import sys
from typing import Any

try:
    import pygame
except ImportError:
    print("pygame is not installed. Run: pip install pygame-ce", file=sys.stderr)
    sys.exit(1)

from ..models.graph import Graph
from ..simulation.engine import TurnSnapshot, DroneSnapshot
from ..pathfinding.dijkstra import DijkstraStep

# ── Colour palette (cyberpunk dark theme) ────────────────────────────────────

_BG         = (8,   8,  16)
_PANEL      = (12,  12,  22)
_BORDER     = (30,  35,  55)
_ACCENT     = (0,  200, 255)    # cyan
_GOLD       = (255, 215,  40)   # gold / active
_TEXT       = (190, 200, 220)
_DIM        = (65,  75, 105)
_SEP        = (22,  25,  40)

_C_START    = (  0, 255, 136)
_C_END      = (255, 210,   0)
_C_NORMAL   = ( 55, 120, 195)
_C_RESTRICT = (220,  70,  30)
_C_PRIORITY = (  0, 210, 165)
_C_BLOCKED  = ( 40,  40,  55)
_C_DRONE    = (255, 255, 255)
_C_TRANSIT  = (255, 215,  40)
_C_PATH     = ( 40, 160, 220)

_NAME_RGB: dict[str, tuple[int, int, int]] = {
    "red":    (210,  55,  55),
    "green":  (  0, 210, 100),
    "blue":   ( 55, 130, 210),
    "yellow": (220, 190,  30),
    "orange": (220, 120,  30),
    "gray":   ( 95,  95, 110),
    "grey":   ( 95,  95, 110),
    "cyan":   (  0, 210, 210),
    "purple": (155,  75, 205),
    "white":  (210, 215, 225),
    "black":  ( 40,  40,  50),
    "pink":   (215, 115, 175),
}

_ZONE_TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "normal":     _C_NORMAL,
    "restricted": _C_RESTRICT,
    "priority":   _C_PRIORITY,
    "blocked":    _C_BLOCKED,
}

# ── Layout ────────────────────────────────────────────────────────────────────

_W          = 1280
_H          = 820
_GRAPH_W    = 890
_PANEL_W    = _W - _GRAPH_W
_TIMELINE_H = 58
_GRAPH_H    = _H - _TIMELINE_H
_PAD        = 68


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _txt(font: Any, text: str, color: tuple[int, int, int]) -> pygame.Surface:
    """Render text using a pygame.freetype font.

    Args:
        font: A pygame.freetype Font instance.
        text: The string to render.
        color: RGB colour tuple.

    Returns:
        Rendered pygame Surface.
    """
    surf, _ = font.render(text, color)
    return surf


def _glow(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    pos: tuple[int, int],
    radius: int,
    layers: int = 3,
    strength: int = 90,
) -> None:
    """Draw a soft radial glow around a position using alpha blending.

    Args:
        surface: Target surface to draw on.
        color: RGB glow colour.
        pos: Centre (x, y) pixel position.
        radius: Base radius the glow extends from.
        layers: Number of concentric rings.
        strength: Maximum alpha of the innermost glow ring.
    """
    for i in range(layers, 0, -1):
        r = radius + i * 7
        alpha = int(strength * (i / layers) ** 2)
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (*color, alpha), (r, r), r)
        surface.blit(g, (pos[0] - r, pos[1] - r))


def _draw_dashed_line(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    start: tuple[int, int],
    end: tuple[int, int],
    dash: int = 8,
    gap: int = 6,
    width: int = 1,
) -> None:
    """Draw a dashed line between two points.

    Args:
        surface: Target surface.
        color: Line colour.
        start: Start pixel position.
        end: End pixel position.
        dash: Length of each dash segment in pixels.
        gap: Length of each gap segment in pixels.
        width: Line width in pixels.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    nx, ny = dx / length, dy / length
    step = dash + gap
    pos = 0.0
    while pos < length:
        x0 = int(start[0] + nx * pos)
        y0 = int(start[1] + ny * pos)
        seg_end = min(pos + dash, length)
        x1 = int(start[0] + nx * seg_end)
        y1 = int(start[1] + ny * seg_end)
        pygame.draw.line(surface, color, (x0, y0), (x1, y1), width)
        pos += step


def _draw_arrow_head(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    tip: tuple[int, int],
    angle_rad: float,
    size: int = 8,
) -> None:
    """Draw a filled triangle arrowhead at tip pointing in the given direction.

    Args:
        surface: Target surface.
        color: Fill colour.
        tip: (x, y) position of the arrowhead tip.
        angle_rad: Direction angle in radians.
        size: Arrowhead size in pixels.
    """
    a = angle_rad + math.pi
    left  = (tip[0] + int(math.cos(a - 0.4) * size),
             tip[1] + int(math.sin(a - 0.4) * size))
    right = (tip[0] + int(math.cos(a + 0.4) * size),
             tip[1] + int(math.sin(a + 0.4) * size))
    pygame.draw.polygon(surface, color, [tip, left, right])


def _zone_fill_color(
    name: str,
    zone_type: str,
    color_hint: str | None,
    start_name: str,
    end_name: str,
) -> tuple[int, int, int]:
    """Return the primary fill colour for a zone node.

    Args:
        name: Zone name.
        zone_type: Zone type string.
        color_hint: Optional color name from map metadata.
        start_name: Name of the start zone.
        end_name: Name of the end zone.

    Returns:
        RGB fill colour.
    """
    if name == start_name:
        return _C_START
    if name == end_name:
        return _C_END
    if color_hint and color_hint.lower() in _NAME_RGB:
        return _NAME_RGB[color_hint.lower()]
    return _ZONE_TYPE_COLORS.get(zone_type, _C_NORMAL)



def _lighter(color: tuple[int, int, int], factor: float = 0.4) -> tuple[int, int, int]:
    """Return a lighter version of an RGB colour by blending toward white.

    Args:
        color: Base RGB colour.
        factor: Blend factor toward white (0 = unchanged, 1 = white).

    Returns:
        Lightened RGB colour.
    """
    return (
        int(color[0] + (255 - color[0]) * factor),
        int(color[1] + (255 - color[1]) * factor),
        int(color[2] + (255 - color[2]) * factor),
    )


def _darker(color: tuple[int, int, int], factor: float = 0.5) -> tuple[int, int, int]:
    """Return a darker version of an RGB colour by blending toward black.

    Args:
        color: Base RGB colour.
        factor: Blend factor toward black (0 = unchanged, 1 = black).

    Returns:
        Darkened RGB colour.
    """
    return (
        int(color[0] * (1 - factor)),
        int(color[1] * (1 - factor)),
        int(color[2] * (1 - factor)),
    )


def _smoothstep(t: float) -> float:
    """Return smoothstep ease-in-out of t clamped to [0, 1].

    Args:
        t: Raw linear progress in [0.0, 1.0].

    Returns:
        Eased value with smooth acceleration and deceleration.
    """
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# ── Main display class ────────────────────────────────────────────────────────


class PygameDisplay:
    """Graphical replay of the drone simulation using pygame.

    Renders zones, connections, drone positions, and simulation statistics
    turn by turn with a sci-fi dark-theme aesthetic.

    Attributes:
        graph: The routing graph.
        snapshots: Ordered TurnSnapshots (index 0 = initial state).
        speed_ms: Auto-play delay in milliseconds.
        primary_path: Optional ordered list of zone names forming the primary route.
    """

    def __init__(
        self,
        graph: Graph,
        snapshots: list[TurnSnapshot],
        speed_ms: int = 500,
        primary_path: list[str] | None = None,
        dijkstra_steps: list[DijkstraStep] | None = None,
    ) -> None:
        """Initialise the display.

        Args:
            graph: The routing graph.
            snapshots: Turn-by-turn simulation snapshots from the engine.
            speed_ms: Auto-play delay in milliseconds between frames.
            primary_path: Zone name sequence for the primary Dijkstra path to
                highlight as a ghost route on the graph.
            dijkstra_steps: Recorded settle-steps from dijkstra_with_steps(),
                used by the D-key algorithm replay mode.
        """
        self.graph = graph
        self.snapshots = snapshots
        self.speed_ms = speed_ms
        self.primary_path = primary_path or []
        self.dijkstra_steps: list[DijkstraStep] = dijkstra_steps or []
        # Grid-space zone positions (centered at origin, in map coordinate units)
        self._grid_pos: dict[str, tuple[float, float]] = {}
        # View state — pixels per grid unit, and pixel position of grid origin
        self._view_scale: float = 1.0
        self._view_cx: float = _GRAPH_W / 2.0
        self._view_cy: float = _GRAPH_H / 2.0
        # Derived screen positions and adaptive sizes (updated by _update_view)
        self._positions: dict[str, tuple[int, int]] = {}
        self._zone_r: int = 28
        self._drone_r: int = 8

    def run(self) -> None:
        """Open the pygame window and enter the interactive event loop.

        Controls:
            Space / Right arrow  — next turn
            Left arrow           — previous turn
            A                    — toggle auto-play
            +  /  =              — increase auto-play speed
            -                    — decrease auto-play speed
            Q / Escape           — quit
            Mouse click          — click timeline dots to jump to a turn
        """
        pygame.init()
        from pygame import freetype as _ft
        _ft.init()

        screen = pygame.display.set_mode((_W, _H))
        pygame.display.set_caption("Fly-in  —  Drone Fleet Simulation")
        clock = pygame.time.Clock()

        f_title: Any = _ft.SysFont("monospace", 18, bold=True)
        f_head:  Any = _ft.SysFont("monospace", 15, bold=True)
        f_body:  Any = _ft.SysFont("monospace", 12)
        f_sm:    Any = _ft.SysFont("monospace", 10)
        f_xs:    Any = _ft.SysFont("monospace", 9)

        self._compute_positions()

        # Simulation mode state
        idx = 0
        autoplay = False
        last_advance = 0
        anim_t = 1.0

        # Dijkstra replay mode state (D key toggles)
        dijkstra_mode = False
        d_idx = 0

        # Pan/zoom drag state
        dragging = False
        drag_start = (0, 0)
        drag_cx0 = self._view_cx
        drag_cy0 = self._view_cy

        while True:
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        pygame.quit()
                        return

                    if event.key == pygame.K_d and self.dijkstra_steps:
                        dijkstra_mode = not dijkstra_mode
                        d_idx = 0
                        autoplay = False

                    elif dijkstra_mode:
                        if event.key in (pygame.K_RIGHT, pygame.K_SPACE):
                            d_idx = min(d_idx + 1, len(self.dijkstra_steps) - 1)
                            autoplay = False
                        elif event.key == pygame.K_LEFT:
                            d_idx = max(d_idx - 1, 0)
                            autoplay = False
                        elif event.key == pygame.K_a:
                            autoplay = not autoplay
                            last_advance = now
                        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                            self.speed_ms = max(100, self.speed_ms - 100)
                        elif event.key == pygame.K_MINUS:
                            self.speed_ms = min(2000, self.speed_ms + 100)

                    else:
                        if event.key in (pygame.K_RIGHT, pygame.K_SPACE):
                            idx = min(idx + 1, len(self.snapshots) - 1)
                            anim_t = 1.0
                            autoplay = False
                        elif event.key == pygame.K_LEFT:
                            idx = max(idx - 1, 0)
                            anim_t = 1.0
                            autoplay = False
                        elif event.key == pygame.K_a:
                            autoplay = not autoplay
                            last_advance = now
                            anim_t = 1.0
                        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                            self.speed_ms = max(100, self.speed_ms - 100)
                        elif event.key == pygame.K_MINUS:
                            self.speed_ms = min(2000, self.speed_ms + 100)

                    if event.key in (pygame.K_f, pygame.K_0):
                        self._fit_all()

                if event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if mx < _GRAPH_W:
                        factor = 1.12 if event.y > 0 else 0.89
                        self._zoom_at(factor, mx, my)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                    dragging = True
                    drag_start = event.pos
                    drag_cx0 = self._view_cx
                    drag_cy0 = self._view_cy

                if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                    dragging = False

                if event.type == pygame.MOUSEMOTION and dragging:
                    dx = event.pos[0] - drag_start[0]
                    dy = event.pos[1] - drag_start[1]
                    self._view_cx = drag_cx0 + dx
                    self._view_cy = drag_cy0 + dy
                    self._update_view()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if dijkstra_mode:
                        hit = self._timeline_hit(event.pos, len(self.dijkstra_steps))
                        if hit is not None:
                            d_idx = hit
                            autoplay = False
                    else:
                        hit = self._timeline_hit(event.pos, len(self.snapshots))
                        if hit is not None:
                            idx = hit
                            autoplay = False

            # ── Advance autoplay ──────────────────────────────────────────────
            if autoplay:
                elapsed = now - last_advance
                if dijkstra_mode:
                    if elapsed >= self.speed_ms:
                        if d_idx < len(self.dijkstra_steps) - 1:
                            d_idx += 1
                            last_advance = now
                        else:
                            autoplay = False
                else:
                    raw_t = elapsed / self.speed_ms
                    if raw_t >= 1.0:
                        if idx < len(self.snapshots) - 1:
                            idx += 1
                            last_advance = now
                            anim_t = 0.0
                        else:
                            autoplay = False
                            anim_t = 1.0
                    else:
                        anim_t = raw_t

            # ── Render ────────────────────────────────────────────────────────
            screen.fill(_BG)
            self._draw_grid(screen)

            if dijkstra_mode:
                d_step = self.dijkstra_steps[d_idx]
                # Draw graph base (connections + zones) then overlay
                self._draw_connections(screen, self.snapshots[0], f_xs)
                self._draw_zones(screen, self.snapshots[0], f_sm, f_xs)
                self._draw_dijkstra_overlay(screen, d_step, f_xs)
                self._draw_timeline(screen, d_idx, f_xs,
                                    total_override=len(self.dijkstra_steps))
                self._draw_dijkstra_panel(screen, d_step, d_idx,
                                          len(self.dijkstra_steps),
                                          f_title, f_head, f_body, f_sm, autoplay)
            else:
                self._draw_path_ghost(screen)
                snap_from = self.snapshots[max(0, idx - 1)]
                snap      = self.snapshots[idx]
                t_eased   = _smoothstep(anim_t)
                self._draw_connections(screen, snap, f_xs)
                self._draw_zones(screen, snap, f_sm, f_xs)
                self._draw_drones(screen, snap_from, snap, t_eased, f_xs)
                self._draw_timeline(screen, idx, f_xs)
                self._draw_panel(screen, snap, f_title, f_head, f_body, f_sm, autoplay)

            pygame.display.flip()
            clock.tick(60)

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _compute_positions(self) -> None:
        """Compute grid-space zone positions centered at origin, then call _update_view.

        Grid coordinates are centred at the mean of the bounding box so that
        zooming scales symmetrically around the graph centre.
        """
        zones = list(self.graph.zones.values())
        if not zones:
            return
        xs = [float(z.x) for z in zones]
        ys = [float(z.y) for z in zones]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        self._grid_pos = {z.name: (z.x - cx, z.y - cy) for z in zones}
        self._fit_all()

    def _update_view(self) -> None:
        """Recompute pixel positions and adaptive sizes from current view state."""
        self._zone_r = max(6, min(28, int(self._view_scale * 0.42)))
        self._drone_r = max(3, min(8, int(self._zone_r * 0.38)))
        self._positions = {
            name: (
                int(gx * self._view_scale + self._view_cx),
                int(gy * self._view_scale + self._view_cy),
            )
            for name, (gx, gy) in self._grid_pos.items()
        }

    def _fit_all(self) -> None:
        """Reset view to fit all zones inside the graph area with padding."""
        if not self._grid_pos:
            return
        gxs = [gx for gx, _ in self._grid_pos.values()]
        gys = [gy for _, gy in self._grid_pos.values()]
        span_x = max(gxs) - min(gxs) or 1.0
        span_y = max(gys) - min(gys) or 1.0
        avail_w = _GRAPH_W - 2 * _PAD
        avail_h = _GRAPH_H - 2 * _PAD
        self._view_scale = min(avail_w / span_x, avail_h / span_y)
        self._view_cx = _GRAPH_W / 2.0
        self._view_cy = _GRAPH_H / 2.0
        self._update_view()

    def _zoom_at(self, factor: float, mx: int, my: int) -> None:
        """Zoom the view by factor, keeping grid point under (mx, my) fixed.

        Args:
            factor: Scale multiplier (>1 zooms in, <1 zooms out).
            mx: Mouse x position (pixels).
            my: Mouse y position (pixels).
        """
        new_scale = max(5.0, min(400.0, self._view_scale * factor))
        ratio = new_scale / self._view_scale
        self._view_cx = mx - (mx - self._view_cx) * ratio
        self._view_cy = my - (my - self._view_cy) * ratio
        self._view_scale = new_scale
        self._update_view()

    @staticmethod
    def _timeline_hit(mouse: tuple[int, int], total: int) -> int | None:
        """Return the snapshot index if the mouse hit a timeline dot.

        Args:
            mouse: Mouse (x, y) position.
            total: Total number of snapshots.

        Returns:
            Snapshot index or None.
        """
        if total <= 1:
            return None
        spacing = min(24, (_GRAPH_W - 60) // total)
        start_x = (_GRAPH_W - spacing * (total - 1)) // 2
        y_center = _GRAPH_H + _TIMELINE_H // 2
        for i in range(total):
            cx = start_x + i * spacing
            dist = math.hypot(mouse[0] - cx, mouse[1] - y_center)
            if dist <= 10:
                return i
        return None

    # ── Background ────────────────────────────────────────────────────────────

    def _draw_grid(self, surface: pygame.Surface) -> None:
        """Draw a subtle dot-grid background in the graph area.

        Args:
            surface: Target surface.
        """
        step = 40
        dot_color = (18, 20, 34)
        for x in range(0, _GRAPH_W, step):
            for y in range(0, _GRAPH_H, step):
                pygame.draw.circle(surface, dot_color, (x, y), 1)

    # ── Path ghost ────────────────────────────────────────────────────────────

    def _draw_path_ghost(self, surface: pygame.Surface) -> None:
        """Draw the primary Dijkstra path as a faint dashed route.

        This shows the algorithm's planned route even before drones traverse it,
        giving visual insight into the pathfinding decision.

        Args:
            surface: Target surface.
        """
        if len(self.primary_path) < 2:
            return
        ghost_color = (40, 120, 180)
        for i in range(len(self.primary_path) - 1):
            pa = self._positions.get(self.primary_path[i])
            pb = self._positions.get(self.primary_path[i + 1])
            if pa is None or pb is None:
                continue
            _draw_dashed_line(surface, ghost_color, pa, pb, dash=10, gap=8, width=2)

    # ── Connections ───────────────────────────────────────────────────────────

    def _draw_connections(
        self, surface: pygame.Surface, snap: TurnSnapshot, font: Any
    ) -> None:
        """Draw all connections, with glow and arrows on active ones.

        Args:
            surface: Target surface.
            snap: Current turn snapshot.
            font: Tiny font for capacity labels.
        """
        active: set[frozenset[str]] = {
            frozenset(p) for p in snap["active_connections"]
        }
        active_dirs: dict[frozenset[str], tuple[str, str]] = {
            frozenset(p): p for p in snap["active_connections"]
        }

        for conn in self.graph.connections:
            pa = self._positions.get(conn.zone_a.name)
            pb = self._positions.get(conn.zone_b.name)
            if pa is None or pb is None:
                continue
            key = frozenset((conn.zone_a.name, conn.zone_b.name))
            is_active = key in active

            zr = self._zone_r
            active_lw = max(1, zr // 9)
            glow_lw   = max(4, zr // 3)
            arrow_sz  = max(4, zr // 3)

            if is_active:
                # glow overlay
                glow_s = pygame.Surface((_GRAPH_W, _GRAPH_H), pygame.SRCALPHA)
                pygame.draw.line(glow_s, (*_GOLD, 35), pa, pb, glow_lw)
                surface.blit(glow_s, (0, 0))
                pygame.draw.line(surface, _GOLD, pa, pb, active_lw)

                # arrowhead at midpoint
                pair = active_dirs.get(key, (conn.zone_a.name, conn.zone_b.name))
                src_pos = self._positions.get(pair[0])
                dst_pos = self._positions.get(pair[1])
                if src_pos and dst_pos:
                    mx = (src_pos[0] + dst_pos[0]) // 2
                    my = (src_pos[1] + dst_pos[1]) // 2
                    angle = math.atan2(dst_pos[1] - src_pos[1], dst_pos[0] - src_pos[0])
                    _draw_arrow_head(surface, _GOLD, (mx, my), angle, size=arrow_sz)
            else:
                pygame.draw.line(surface, _BORDER, pa, pb, 1)

            if conn.max_link_capacity > 1:
                mid = ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)
                lbl = _txt(font, f"×{conn.max_link_capacity}", _DIM)
                lw, lh = lbl.get_size()
                bg = pygame.Surface((lw + 4, lh + 2), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 120))
                surface.blit(bg, (mid[0] - lw // 2 - 2, mid[1] - lh // 2 - 1))
                surface.blit(lbl, (mid[0] - lw // 2, mid[1] - lh // 2))

    # ── Zones ─────────────────────────────────────────────────────────────────

    def _draw_zones(
        self,
        surface: pygame.Surface,
        snap: TurnSnapshot,
        font: Any,
        font_xs: Any,
    ) -> None:
        """Draw zone nodes with capacity fill, glows, and labels.

        Args:
            surface: Target surface.
            snap: Current turn snapshot.
            font: Font for zone name labels.
            font_xs: Tiny font for capacity badges.
        """
        drone_counts: dict[str, int] = {}
        for d in snap["drones"]:
            # in_transit drones are shown mid-connection, not inside their source zone
            if d["state"] in ("arrived", "in_transit"):
                continue
            drone_counts[d["zone"]] = drone_counts.get(d["zone"], 0) + 1

        start_name = self.graph.start.name if self.graph.start else ""
        end_name   = self.graph.end.name   if self.graph.end   else ""

        for name, zone in self.graph.zones.items():
            pos = self._positions.get(name)
            if pos is None:
                continue
            color  = _zone_fill_color(name, zone.zone_type, zone.color, start_name, end_name)
            count  = drone_counts.get(name, 0)
            is_unlimited = name in (start_name, end_name)

            zr = self._zone_r

            # glow when drones are present
            if count > 0:
                _glow(surface, color, pos, zr, layers=3, strength=80)

            # capacity fill arc (inner ring showing occupancy)
            if not is_unlimited and zone.max_drones > 0 and count > 0 and zr >= 8:
                fill_ratio = min(count / zone.max_drones, 1.0)
                inset = max(2, zr // 7)
                arc_rect = pygame.Rect(
                    pos[0] - zr + inset, pos[1] - zr + inset,
                    (zr - inset) * 2, (zr - inset) * 2
                )
                arc_color = _lighter(color, 0.5) if fill_ratio < 1 else (255, 80, 80)
                end_angle = -math.pi / 2 + fill_ratio * 2 * math.pi
                try:
                    pygame.draw.arc(surface, arc_color, arc_rect, -math.pi / 2, end_angle,
                                    max(1, zr // 10))
                except Exception:
                    pass

            # main circle
            dark = _darker(color, 0.35)
            pygame.draw.circle(surface, dark, pos, zr)
            pygame.draw.circle(surface, color, pos, max(1, zr - 3))

            # border ring
            border_col = _lighter(color, 0.25) if count > 0 else _darker(color, 0.1)
            pygame.draw.circle(surface, border_col, pos, zr, max(1, zr // 14))

            # special markers (only when large enough to see)
            if zr >= 8:
                if zone.zone_type == "blocked":
                    s = int(zr * 0.5)
                    pygame.draw.line(surface, (180, 50, 50),
                                     (pos[0] - s, pos[1] - s), (pos[0] + s, pos[1] + s), 2)
                    pygame.draw.line(surface, (180, 50, 50),
                                     (pos[0] + s, pos[1] - s), (pos[0] - s, pos[1] + s), 2)
                elif name == start_name:
                    s = int(zr * 0.4)
                    pts = [(pos[0] - s // 2, pos[1] - s),
                           (pos[0] + s, pos[1]),
                           (pos[0] - s // 2, pos[1] + s)]
                    pygame.draw.polygon(surface, _darker(_C_START, 0.3), pts)
                elif name == end_name:
                    s = int(zr * 0.45)
                    pts = [(pos[0], pos[1] - s), (pos[0] + s, pos[1]),
                           (pos[0], pos[1] + s), (pos[0] - s, pos[1])]
                    pygame.draw.polygon(surface, _darker(_C_END, 0.3), pts)
                elif zone.zone_type == "priority":
                    pygame.draw.circle(surface, _lighter(_C_PRIORITY, 0.6), pos,
                                       max(2, zr // 6))

            # zone label (below circle) — hidden when zones are too small to read
            if zr >= 12:
                max_chars = max(4, zr // 2)
                display_name = name if len(name) <= max_chars else name[:max_chars - 1] + "…"
                lbl = _txt(font, display_name, _lighter(color, 0.7))
                lw, _ = lbl.get_size()
                surface.blit(lbl, (pos[0] - lw // 2, pos[1] + zr + 3))

            # drone count badge (above-right of circle) — always shown when occupied
            if count > 0:
                badge_txt = str(count)
                badge = _txt(font_xs, badge_txt, _TEXT)
                bw, bh = badge.get_size()
                bx = pos[0] + zr - bw // 2
                by = pos[1] - zr - bh - 2
                bg = pygame.Surface((bw + 6, bh + 3), pygame.SRCALPHA)
                bg.fill((*color, 200))
                surface.blit(bg, (bx - 3, by - 1))
                surface.blit(badge, (bx, by))

    # ── Drones ────────────────────────────────────────────────────────────────

    def _draw_drones(
        self,
        surface: pygame.Surface,
        snap_from: TurnSnapshot,
        snap_to: TurnSnapshot,
        t: float,
        font: Any,
    ) -> None:
        """Draw drones smoothly animated between two consecutive turn snapshots.

        Positions are linearly interpolated between snap_from and snap_to using
        the eased progress t.  In-transit drones (restricted-zone crossing) sit
        at the midpoint of their connection; normal drones sit at their zone
        centre.  A short motion trail is drawn behind each moving drone.

        Args:
            surface: Target surface.
            snap_from: Snapshot at the start of the animation (previous turn).
            snap_to: Snapshot at the end of the animation (current turn).
            t: Eased animation progress in [0.0, 1.0].
            font: Tiny font for drone ID labels.
        """
        def drone_px(d: DroneSnapshot) -> tuple[int, int]:
            """Return the canonical pixel position for a drone's logical state.

            In-transit drones sit at the midpoint of the connection they are
            crossing.  All other drones sit below their zone circle so they are
            visible outside the zone node.
            """
            if d["state"] == "in_transit" and d["dest"]:
                pa = self._positions.get(d["zone"])
                pb = self._positions.get(d["dest"])
                if pa and pb:
                    return ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)
            pos = self._positions.get(d["zone"], (0, 0))
            # Place the dot just below the zone circle so it is not hidden by it
            return (pos[0], pos[1] + self._zone_r + self._drone_r + 4)

        from_map: dict[int, DroneSnapshot] = {d["id"]: d for d in snap_from["drones"]}

        # One shared SRCALPHA surface for all motion trails (single blit)
        trail_surf = pygame.Surface((_GRAPH_W, _GRAPH_H), pygame.SRCALPHA)

        for d in snap_to["drones"]:
            # Fully arrived and animation complete — no longer rendered
            if d["state"] == "arrived" and t >= 1.0:
                continue

            from_d = from_map.get(d["id"])
            # If this drone was already arrived in the previous snapshot, skip
            if from_d and from_d["state"] == "arrived":
                continue

            fp = drone_px(from_d) if from_d else drone_px(d)
            tp = drone_px(d)

            # ── Waypoint animation for pass-through restricted zones ───────────
            # When a drone arrives at zone R and immediately departs in the
            # same turn, snap_from shows it heading to R and snap_to shows it
            # already leaving R.  The normal lerp would skip R entirely.
            # Detect this case and split the animation into two phases so the
            # drone visually touches the restricted hub.
            waypoint: tuple[int, int] | None = None
            if (
                from_d is not None
                and from_d["state"] == "in_transit"
                and from_d["dest"] is not None
                and d["state"] == "in_transit"
                and d["zone"] == from_d["dest"]
            ):
                waypoint = self._positions.get(d["zone"])

            if waypoint is not None:
                # Phase 1 (t 0→0.5): fp → waypoint hub center
                # Phase 2 (t 0.5→1): waypoint hub center → tp
                if t < 0.5:
                    t2 = t * 2.0
                    cx = int(fp[0] + (waypoint[0] - fp[0]) * t2)
                    cy = int(fp[1] + (waypoint[1] - fp[1]) * t2)
                else:
                    t2 = (t - 0.5) * 2.0
                    cx = int(waypoint[0] + (tp[0] - waypoint[0]) * t2)
                    cy = int(waypoint[1] + (tp[1] - waypoint[1]) * t2)
            else:
                cx = int(fp[0] + (tp[0] - fp[0]) * t)
                cy = int(fp[1] + (tp[1] - fp[1]) * t)

            # Gold while in transit (either leg of a restricted crossing)
            is_transit = d["state"] == "in_transit" or (
                from_d is not None and from_d["state"] == "in_transit" and t < 1.0
            )
            color = _C_TRANSIT if is_transit else _C_DRONE

            dr = self._drone_r

            # Motion trail: a short fading line from slightly behind the drone
            if t > 0.05 and (cx != fp[0] or cy != fp[1]):
                trail_alpha = int(100 * t)
                trail_w = max(1, dr // 3)
                if waypoint is not None:
                    # Draw trail only within the current phase so it doesn't
                    # cross the waypoint hub in reverse
                    if t < 0.5:
                        trail_t2 = max(0.0, t * 2.0 - 0.4)
                        tx = int(fp[0] + (waypoint[0] - fp[0]) * trail_t2)
                        ty = int(fp[1] + (waypoint[1] - fp[1]) * trail_t2)
                    else:
                        trail_t2 = max(0.0, (t - 0.5) * 2.0 - 0.35)
                        tx = int(waypoint[0] + (tp[0] - waypoint[0]) * trail_t2)
                        ty = int(waypoint[1] + (tp[1] - waypoint[1]) * trail_t2)
                else:
                    trail_t = max(0.0, t - 0.35)
                    tx = int(fp[0] + (tp[0] - fp[0]) * trail_t)
                    ty = int(fp[1] + (tp[1] - fp[1]) * trail_t)
                pygame.draw.line(trail_surf, (*color, trail_alpha), (tx, ty), (cx, cy), trail_w)

            glow_s = 3 if is_transit else 2
            _glow(surface, color, (cx, cy), dr, layers=glow_s, strength=70)
            pygame.draw.circle(surface, color, (cx, cy), dr)
            pygame.draw.circle(surface, _BG, (cx, cy), dr, 1)
            # Show drone ID label only when large enough to read
            if dr >= 5:
                lbl = _txt(font, f"D{d['id']}", _BG)
                lw, lh = lbl.get_size()
                surface.blit(lbl, (cx - lw // 2, cy - lh // 2))

        surface.blit(trail_surf, (0, 0))

    # ── Timeline ──────────────────────────────────────────────────────────────

    def _draw_timeline(
        self,
        surface: pygame.Surface,
        current: int,
        font: Any,
        total_override: int | None = None,
    ) -> None:
        """Draw the clickable timeline bar at the bottom of the graph area.

        Each turn is represented by a dot. The current turn is highlighted.
        Past turns are dim-filled; future turns are outlined only.

        Args:
            surface: Target surface.
            current: Index of the current item being displayed.
            font: Tiny font for turn number labels.
            total_override: If set, use this as the total count instead of
                len(self.snapshots) — used in Dijkstra replay mode.
        """
        total = total_override if total_override is not None else len(self.snapshots)
        if total <= 1:
            return

        # timeline strip background
        strip = pygame.Rect(0, _GRAPH_H, _GRAPH_W, _TIMELINE_H)
        pygame.draw.rect(surface, _PANEL, strip)
        pygame.draw.line(surface, _BORDER, (0, _GRAPH_H), (_GRAPH_W, _GRAPH_H), 1)

        spacing = min(24, (_GRAPH_W - 80) // total)
        start_x = (_GRAPH_W - spacing * (total - 1)) // 2
        cy = _GRAPH_H + _TIMELINE_H // 2

        # connecting line
        lx0 = start_x
        lx1 = start_x + spacing * (total - 1)
        pygame.draw.line(surface, _BORDER, (lx0, cy), (lx1, cy), 1)

        for i in range(total):
            cx = start_x + i * spacing
            if i == current:
                _glow(surface, _ACCENT, (cx, cy), 7, layers=2, strength=80)
                pygame.draw.circle(surface, _ACCENT, (cx, cy), 7)
                lbl = _txt(font, str(i), _BG)
            elif i < current:
                pygame.draw.circle(surface, _DIM, (cx, cy), 5)
                lbl = _txt(font, str(i), _DIM)
            else:
                pygame.draw.circle(surface, _BORDER, (cx, cy), 5, 1)
                lbl = _txt(font, str(i), _SEP)
            lw, lh = lbl.get_size()
            surface.blit(lbl, (cx - lw // 2, cy - lh // 2))

        # label at far right
        total_lbl = _txt(font, f"{current}/{total - 1}", _DIM)
        surface.blit(total_lbl, (_GRAPH_W - total_lbl.get_width() - 10, cy - 5))

    # ── Side panel ────────────────────────────────────────────────────────────

    def _draw_panel(
        self,
        surface: pygame.Surface,
        snap: TurnSnapshot,
        f_title: Any,
        f_head: Any,
        f_body: Any,
        f_sm: Any,
        autoplay: bool,
    ) -> None:
        """Draw the right information panel with stats, moves, controls, legend.

        Args:
            surface: Target surface.
            snap: Current turn snapshot.
            f_title: Large title font.
            f_head: Section heading font.
            f_body: Body text font.
            f_sm: Small font.
            autoplay: Whether auto-play is active.
        """
        px = _GRAPH_W
        # panel background + left border
        pygame.draw.rect(surface, _PANEL, (px, 0, _PANEL_W, _H))
        pygame.draw.line(surface, _BORDER, (px, 0), (px, _H), 1)

        x   = px + 16
        y   = 0
        rw  = _PANEL_W - 32  # usable width inside panel

        def sep() -> None:
            """Draw a horizontal separator line."""
            nonlocal y
            y += 6
            pygame.draw.line(surface, _SEP, (x, y), (x + rw, y), 1)
            y += 8

        def write(
            text: str,
            color: tuple[int, int, int] = _TEXT,
            font: Any = None,
            indent: int = 0,
        ) -> None:
            """Render a line of text and advance y.

            Args:
                text: Text to render.
                color: Text colour.
                font: Font to use (defaults to f_body).
                indent: Extra left indent in pixels.
            """
            nonlocal y
            f = font if font is not None else f_body
            surf = _txt(f, text, color)
            surface.blit(surf, (x + indent, y))
            y += surf.get_height() + 3

        def bar(value: float, width: int, height: int, fg: tuple[int, int, int]) -> None:
            """Draw a filled progress bar.

            Args:
                value: Fill ratio (0.0 – 1.0).
                width: Bar width in pixels.
                height: Bar height in pixels.
                fg: Foreground fill colour.
            """
            nonlocal y
            pygame.draw.rect(surface, _SEP, (x, y, width, height), border_radius=3)
            fill_w = int(width * max(0.0, min(value, 1.0)))
            if fill_w > 0:
                pygame.draw.rect(surface, fg, (x, y, fill_w, height), border_radius=3)
            y += height + 5

        # ── Header ─────────────────────────────────────────────────────────

        y = 18
        write("FLY-IN", _ACCENT, font=f_title)
        write("Drone Fleet Simulation", _DIM, font=f_sm)
        sep()

        # ── Turn indicator ──────────────────────────────────────────────────

        total_turns = len(self.snapshots) - 1
        label = "INITIAL" if snap["turn"] == 0 else f"TURN  {snap['turn']}"
        write(label, _GOLD, font=f_head)
        write(f"of {total_turns} total turns", _DIM, font=f_sm)
        y += 4
        bar(snap["turn"] / total_turns if total_turns else 0, rw, 6, _ACCENT)

        # ── Drone delivery ──────────────────────────────────────────────────

        arrived = sum(1 for d in snap["drones"] if d["state"] == "arrived")
        total_d = len(snap["drones"])
        write("DELIVERED", _TEXT, font=f_head)
        write(f"{arrived} / {total_d} drones", _DIM, font=f_sm)
        y += 2
        bar(arrived / total_d if total_d else 0, rw, 8,
            _C_START if arrived == total_d else _C_PRIORITY)
        sep()

        # ── This turn's moves ───────────────────────────────────────────────

        write("MOVES THIS TURN", _TEXT, font=f_head)
        y += 2
        if snap["moves"]:
            for move in snap["moves"]:
                # colour by drone state: arrived = green, transit = gold, moving = cyan
                if move.endswith("_") or "_" in move.split("-", 1)[-1]:
                    mc = _C_TRANSIT
                else:
                    dest = move.split("-", 1)[-1] if "-" in move else ""
                    end_n = self.graph.end.name if self.graph.end else ""
                    mc = _C_START if dest == end_n else _ACCENT
                write(f"  {move}", mc, font=f_sm)
        else:
            write("  (no moves — initial state)", _DIM, font=f_sm)
        sep()

        # ── Drone states ────────────────────────────────────────────────────

        waiting  = sum(1 for d in snap["drones"] if d["state"] == "waiting")
        in_t     = sum(1 for d in snap["drones"] if d["state"] == "in_transit")

        write("DRONE STATUS", _TEXT, font=f_head)
        y += 2
        if waiting:
            write(f"  {waiting}  waiting", _DIM, font=f_sm)
        if in_t:
            write(f"  {in_t}  in transit", _C_TRANSIT, font=f_sm)
        if arrived:
            write(f"  {arrived}  arrived", _C_START, font=f_sm)
        sep()

        # ── Controls ────────────────────────────────────────────────────────

        write("CONTROLS", _TEXT, font=f_head)
        y += 2
        controls = [
            ("→ / Space", "next turn",   _ACCENT),
            ("←",          "prev turn",   _ACCENT),
            ("A",          f"autoplay {'ON' if autoplay else 'OFF'}", _GOLD if autoplay else _DIM),
            ("+ / -",      f"speed {self.speed_ms}ms", _DIM),
            ("Scroll",     "zoom in/out", _DIM),
            ("Mid-drag",   "pan view",    _DIM),
            ("F / 0",      "fit all",     _DIM),
            ("Q / Esc",    "quit",        _DIM),
        ]
        for key, desc, col in controls:
            ks = _txt(f_sm, key, col)
            surface.blit(ks, (x + 4, y))
            ds = _txt(f_sm, desc, _DIM)
            surface.blit(ds, (x + 68, y))
            y += ks.get_height() + 3
        sep()

        # ── Legend ──────────────────────────────────────────────────────────

        write("LEGEND", _TEXT, font=f_head)
        y += 4
        legend = [
            ("start zone",   _C_START),
            ("end zone",     _C_END),
            ("normal",       _C_NORMAL),
            ("restricted",   _C_RESTRICT),
            ("priority",     _C_PRIORITY),
            ("blocked",      _C_BLOCKED),
            ("drone",        _C_DRONE),
            ("in transit",   _C_TRANSIT),
            ("active conn.", _GOLD),
            ("planned path", _C_PATH),
        ]
        for lname, lcolor in legend:
            _glow(surface, lcolor, (x + 9, y + 7), 7, layers=1, strength=40)
            pygame.draw.circle(surface, lcolor, (x + 9, y + 7), 6)
            lbl = _txt(f_sm, lname, _DIM)
            surface.blit(lbl, (x + 22, y + 1))
            y += lbl.get_height() + 4

    # ── Dijkstra algorithm overlay ────────────────────────────────────────────

    def _draw_dijkstra_overlay(
        self,
        surface: pygame.Surface,
        step: DijkstraStep,
        font_xs: Any,
    ) -> None:
        """Draw the Dijkstra algorithm state on top of the base graph.

        Visited zones receive a dark tint, frontier zones glow gold with their
        cost displayed, and the current (just-settled) zone pulses cyan.  The
        cheapest path from start to the current zone is drawn in blue; if the
        end was just settled, the final shortest path glows green.

        Args:
            surface: Target surface (graph area only).
            step: The DijkstraStep to visualise.
            font_xs: Tiny font for cost labels.
        """
        zr = self._zone_r
        visited: set[str] = set(step["visited"])
        frontier: dict[str, float] = step["frontier"]
        current: str = step["current"]
        path_cur: list[str] = step["path_to_current"]
        final_path: list[str] = step["final_path"]

        # ── Dark overlay on every zone that is not in the frontier ────────────
        overlay = pygame.Surface((_GRAPH_W, _GRAPH_H), pygame.SRCALPHA)
        for name, pos in self._positions.items():
            if pos[0] < 0 or pos[0] > _GRAPH_W or pos[1] < 0 or pos[1] > _GRAPH_H:
                continue
            if name in visited and name != current:
                alpha = 150   # settled — dim grey
            elif name not in frontier and name != current:
                alpha = 200   # unknown — nearly black
            else:
                continue
            pygame.draw.circle(overlay, (0, 0, 0, alpha), pos, zr + 2)
        surface.blit(overlay, (0, 0))

        # ── Path from start to current node (blue line) ───────────────────────
        if len(path_cur) >= 2:
            lw = max(2, zr // 8)
            for i in range(len(path_cur) - 1):
                pa = self._positions.get(path_cur[i])
                pb = self._positions.get(path_cur[i + 1])
                if pa and pb:
                    pygame.draw.line(surface, _C_PATH, pa, pb, lw)

        # ── Final shortest path (green glow, drawn once end is settled) ───────
        if final_path and len(final_path) >= 2:
            glow_surf = pygame.Surface((_GRAPH_W, _GRAPH_H), pygame.SRCALPHA)
            lw = max(2, zr // 8)
            for i in range(len(final_path) - 1):
                pa = self._positions.get(final_path[i])
                pb = self._positions.get(final_path[i + 1])
                if pa and pb:
                    pygame.draw.line(glow_surf, (*_C_START, 50), pa, pb, zr // 2)
                    pygame.draw.line(surface, _C_START, pa, pb, lw)
            surface.blit(glow_surf, (0, 0))

        # ── Frontier zones: gold pulsing rings + cost labels ──────────────────
        if frontier:
            costs_vals = list(frontier.values())
            min_c = min(costs_vals)
            max_c = max(costs_vals) if len(costs_vals) > 1 else min_c + 1.0
            for name, cost in frontier.items():
                pos = self._positions.get(name)
                if pos is None:
                    continue
                ratio = 1.0 - (cost - min_c) / (max_c - min_c + 0.001)
                ring_r = zr + max(2, int(zr * 0.3 * ratio))
                alpha = int(80 + 120 * ratio)
                gs = pygame.Surface((ring_r * 2 + 8, ring_r * 2 + 8), pygame.SRCALPHA)
                pygame.draw.circle(gs, (*_GOLD, alpha // 2),
                                   (ring_r + 4, ring_r + 4), ring_r)
                surface.blit(gs, (pos[0] - ring_r - 4, pos[1] - ring_r - 4))
                pygame.draw.circle(surface, _GOLD, pos, ring_r,
                                   max(1, zr // 10))
                if zr >= 10:
                    clbl = _txt(font_xs, f"{cost:.1f}", _GOLD)
                    lw2, lh2 = clbl.get_size()
                    surface.blit(clbl, (pos[0] - lw2 // 2,
                                        pos[1] - ring_r - lh2 - 2))

        # ── Current zone: bright cyan ring + strong glow ──────────────────────
        pos = self._positions.get(current)
        if pos:
            _glow(surface, _ACCENT, pos, zr + 4, layers=4, strength=130)
            pygame.draw.circle(surface, _ACCENT, pos, zr + 4,
                               max(2, zr // 6))

    # ── Dijkstra side panel ───────────────────────────────────────────────────

    def _draw_dijkstra_panel(
        self,
        surface: pygame.Surface,
        step: DijkstraStep,
        step_idx: int,
        total_steps: int,
        f_title: Any,
        f_head: Any,
        f_body: Any,
        f_sm: Any,
        autoplay: bool,
    ) -> None:
        """Draw the right panel showing Dijkstra algorithm state for this step.

        Args:
            surface: Target surface.
            step: The DijkstraStep to display.
            step_idx: Current step index (0-based).
            total_steps: Total number of recorded steps.
            f_title: Large title font.
            f_head: Section heading font.
            f_body: Body text font.
            f_sm: Small font.
            autoplay: Whether auto-play is active.
        """
        px = _GRAPH_W
        pygame.draw.rect(surface, _PANEL, (px, 0, _PANEL_W, _H))
        pygame.draw.line(surface, _BORDER, (px, 0), (px, _H), 1)

        x  = px + 16
        rw = _PANEL_W - 32
        y  = 0

        def sep() -> None:
            """Draw a separator line."""
            nonlocal y
            y += 6
            pygame.draw.line(surface, _SEP, (x, y), (x + rw, y), 1)
            y += 8

        def write(
            text: str,
            color: tuple[int, int, int] = _TEXT,
            font: Any = None,
            indent: int = 0,
        ) -> None:
            """Render one line of text and advance y."""
            nonlocal y
            f = font if font is not None else f_body
            surf = _txt(f, text, color)
            surface.blit(surf, (x + indent, y))
            y += surf.get_height() + 3

        def bar(value: float, width: int, height: int,
                fg: tuple[int, int, int]) -> None:
            """Draw a filled progress bar."""
            nonlocal y
            pygame.draw.rect(surface, _SEP, (x, y, width, height), border_radius=3)
            fw = int(width * max(0.0, min(value, 1.0)))
            if fw > 0:
                pygame.draw.rect(surface, fg, (x, y, fw, height), border_radius=3)
            y += height + 5

        # ── Header ────────────────────────────────────────────────────────────
        y = 18
        write("DIJKSTRA", _ACCENT, font=f_title)
        write("Algorithm Replay", _DIM, font=f_sm)
        sep()

        # ── Step progress ─────────────────────────────────────────────────────
        write(f"STEP  {step_idx + 1}", _GOLD, font=f_head)
        write(f"of {total_steps} settle events", _DIM, font=f_sm)
        y += 4
        bar(step_idx / max(1, total_steps - 1), rw, 6, _ACCENT)

        # ── Current node ──────────────────────────────────────────────────────
        write("SETTLING", _TEXT, font=f_head)
        zone_obj = self.graph.zones.get(step["current"])
        ztype = zone_obj.zone_type if zone_obj else "?"
        type_color = {
            "normal": _C_NORMAL, "restricted": _C_RESTRICT,
            "priority": _C_PRIORITY, "blocked": _C_BLOCKED,
        }.get(ztype, _TEXT)
        write(f"  {step['current']}", _ACCENT, font=f_sm)
        write(f"  type: {ztype}", type_color, font=f_sm)
        cost_here = step["costs"].get(step["current"], 0.0)
        write(f"  cost: {cost_here:.2f}", _GOLD, font=f_sm)
        sep()

        # ── Path from start to current ────────────────────────────────────────
        path = step["path_to_current"]
        write("PATH TO CURRENT", _TEXT, font=f_head)
        if path:
            path_str = " → ".join(path)
            # Wrap across lines if too long
            words = path_str.split(" → ")
            line_buf: list[str] = []
            for w in words:
                line_buf.append(w)
                joined = " → ".join(line_buf)
                test_s = _txt(f_sm, joined, _C_PATH)
                if test_s.get_width() > rw - 8:
                    if len(line_buf) > 1:
                        write("  " + " → ".join(line_buf[:-1]), _C_PATH, font=f_sm)
                        line_buf = [line_buf[-1]]
            if line_buf:
                write("  " + " → ".join(line_buf), _C_PATH, font=f_sm)
        else:
            write("  (start)", _DIM, font=f_sm)
        sep()

        # ── Frontier queue (cheapest 6) ───────────────────────────────────────
        frontier = step["frontier"]
        write("FRONTIER", _TEXT, font=f_head)
        write(f"  {len(frontier)} zones pending", _DIM, font=f_sm)
        y += 2
        sorted_front = sorted(frontier.items(), key=lambda kv: kv[1])
        for name, cost in sorted_front[:6]:
            bar_ratio = 1.0 - cost / (max(v for _, v in sorted_front) + 0.001)
            bw = max(1, int((rw - 70) * bar_ratio))
            pygame.draw.rect(surface, (*_GOLD, 60),  # type: ignore[arg-type]
                             pygame.Rect(x + 70, y + 2, bw, 9))
            write(f"  {name[:12]:<12} {cost:.1f}", _GOLD, font=f_sm)
        if len(sorted_front) > 6:
            write(f"  … +{len(sorted_front) - 6} more", _DIM, font=f_sm)
        sep()

        # ── Final path (once end is settled) ─────────────────────────────────
        if step["final_path"]:
            write("SHORTEST PATH FOUND", _C_START, font=f_head)
            fp = step["final_path"]
            write(f"  {len(fp) - 1} hops", _C_START, font=f_sm)
            total_cost = step["costs"].get(fp[-1], 0.0)
            write(f"  total cost: {total_cost:.2f}", _C_START, font=f_sm)
            sep()

        # ── Visited count ─────────────────────────────────────────────────────
        total_zones = len(self.graph.zones)
        visited_n = len(step["visited"])
        write("EXPLORED", _TEXT, font=f_head)
        write(f"  {visited_n} / {total_zones} zones", _DIM, font=f_sm)
        y += 2
        bar(visited_n / max(1, total_zones), rw, 6,
            _C_START if visited_n == total_zones else _C_PRIORITY)
        sep()

        # ── Controls ─────────────────────────────────────────────────────────
        write("CONTROLS", _TEXT, font=f_head)
        y += 2
        controls = [
            ("→ / Space", "next step",  _ACCENT),
            ("←",          "prev step",  _ACCENT),
            ("A",          f"autoplay {'ON' if autoplay else 'OFF'}",
             _GOLD if autoplay else _DIM),
            ("+ / -",      f"speed {self.speed_ms}ms", _DIM),
            ("D",          "exit algorithm view", _DIM),
        ]
        for key, desc, col in controls:
            ks = _txt(f_sm, key, col)
            surface.blit(ks, (x + 4, y))
            ds = _txt(f_sm, desc, _DIM)
            surface.blit(ds, (x + 68, y))
            y += ks.get_height() + 3

        # ── Legend ────────────────────────────────────────────────────────────
        sep()
        write("LEGEND", _TEXT, font=f_head)
        y += 4
        legend = [
            ("settled zone",  (80, 80, 100)),
            ("current zone",  _ACCENT),
            ("frontier zone", _GOLD),
            ("path to here",  _C_PATH),
            ("final path",    _C_START),
        ]
        for lname, lcolor in legend:
            _glow(surface, lcolor, (x + 9, y + 7), 7, layers=1, strength=40)
            pygame.draw.circle(surface, lcolor, (x + 9, y + 7), 6)
            lbl = _txt(f_sm, lname, _DIM)
            surface.blit(lbl, (x + 22, y + 1))
            y += lbl.get_height() + 4
