"""A 2D camera mapping world cells to screen pixels with pan and zoom.

``zoom`` is expressed as *pixels per cell*. ``cam_x``/``cam_y`` are the world
cell coordinates aligned with the top-left corner of the viewport (floats, so
panning stays smooth at any zoom).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Camera:
    world_w: int
    world_h: int
    screen_w: int
    screen_h: int
    zoom: float = 4.0
    cam_x: float = 0.0
    cam_y: float = 0.0

    min_zoom: float = 0.5
    max_zoom: float = 40.0

    def __post_init__(self) -> None:
        self.fit_to_screen()

    # --- Coordinate conversions -------------------------------------------

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (wx - self.cam_x) * self.zoom, (wy - self.cam_y) * self.zoom

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return self.cam_x + sx / self.zoom, self.cam_y + sy / self.zoom

    # --- Movement ----------------------------------------------------------

    def pan_pixels(self, dx: float, dy: float) -> None:
        """Pan the view by a screen-space delta in pixels."""
        self.cam_x -= dx / self.zoom
        self.cam_y -= dy / self.zoom
        self._clamp()

    def zoom_at(self, factor: float, sx: float, sy: float) -> None:
        """Multiply zoom by ``factor`` while keeping the cell under (sx, sy) fixed."""
        before_wx, before_wy = self.screen_to_world(sx, sy)
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        after_wx, after_wy = self.screen_to_world(sx, sy)
        # Shift the camera so the anchor point stays under the cursor.
        self.cam_x += before_wx - after_wx
        self.cam_y += before_wy - after_wy
        self._clamp()

    def fit_to_screen(self) -> None:
        """Zoom and centre so the whole world is visible."""
        self.zoom = min(self.screen_w / self.world_w, self.screen_h / self.world_h)
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom))
        self.cam_x = (self.world_w - self.screen_w / self.zoom) / 2
        self.cam_y = (self.world_h - self.screen_h / self.zoom) / 2
        self._clamp()

    def resize(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._clamp()

    # --- Visibility --------------------------------------------------------

    def visible_cell_rect(self) -> tuple[int, int, int, int]:
        """Return the inclusive-exclusive cell range ``(x0, y0, x1, y1)`` on screen."""
        x0 = max(0, int(self.cam_x))
        y0 = max(0, int(self.cam_y))
        x1 = min(self.world_w, int(self.cam_x + self.screen_w / self.zoom) + 1)
        y1 = min(self.world_h, int(self.cam_y + self.screen_h / self.zoom) + 1)
        return x0, y0, x1, y1

    def _clamp(self) -> None:
        """Keep the camera from drifting too far off the world edges."""
        view_w = self.screen_w / self.zoom
        view_h = self.screen_h / self.zoom

        # If the world is smaller than the viewport, centre it; otherwise clamp.
        if view_w >= self.world_w:
            self.cam_x = (self.world_w - view_w) / 2
        else:
            self.cam_x = max(0.0, min(self.world_w - view_w, self.cam_x))

        if view_h >= self.world_h:
            self.cam_y = (self.world_h - view_h) / 2
        else:
            self.cam_y = max(0.0, min(self.world_h - view_h, self.cam_y))
