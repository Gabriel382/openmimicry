"""Simple image-based 2D avatar runtime.

This runtime is intentionally minimal:
- loads one image per state from an avatar folder
- shows a speech bubble overlay
- returns to idle after timed states
- can react to runtime/backend events
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import time
import tkinter as tk

try:
    from PIL import Image, ImageTk
except ImportError as exc:
    raise RuntimeError(
        "Pillow is required for the 2D avatar runtime. "
        "Install it with the appropriate project profile."
    ) from exc

from .avatar_pack import AvatarPack
from .event_mapper import state_from_event
from .state_model import AvatarState


@dataclass(slots=True)
class AvatarEvent:
    """Simple runtime event used by the 2D avatar renderer."""

    type: str
    text: str = ""
    source: str = "runtime"


class Avatar2DRuntime:
    """Tkinter-based image avatar runtime."""

    def __init__(
        self,
        avatar_root: str | Path,
        title: str = "OpenMimicry Avatar",
        idle_timeout_ms: int = 2500,
        bubble_enabled: bool | None = None,
        always_on_top: bool = True,
    ) -> None:
        self.avatar_pack = AvatarPack.load(avatar_root)
        self.idle_timeout_ms = idle_timeout_ms
        self.current_state: AvatarState = AvatarState.default()
        self.current_text: str = ""
        self._idle_after_id: Optional[str] = None
        self._images: Dict[AvatarState, ImageTk.PhotoImage] = {}

        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg="white")
        self.root.attributes("-topmost", bool(always_on_top))

        self.canvas = tk.Canvas(
            self.root,
            width=self.avatar_pack.width,
            height=self.avatar_pack.height + 90,
            bg="white",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.bubble_enabled = self.avatar_pack.bubble_enabled if bubble_enabled is None else bubble_enabled

        self._avatar_item = None
        self._bubble_rect = None
        self._bubble_text = None

        self._load_images()
        self._render_full()

    def _load_images(self) -> None:
        """Load all state images into memory."""
        for state in AvatarState:
            image_path = self.avatar_pack.asset_for(state)
            image = Image.open(image_path).convert("RGBA")
            image = image.resize((self.avatar_pack.width, self.avatar_pack.height))
            self._images[state] = ImageTk.PhotoImage(image)

    def _render_full(self) -> None:
        """Render the avatar and optional speech bubble."""
        self.canvas.delete("all")
        self._avatar_item = self.canvas.create_image(
            self.avatar_pack.width // 2,
            self.avatar_pack.height // 2,
            image=self._images[self.current_state],
        )

        if self.bubble_enabled:
            self._draw_bubble(self.current_text)

    def _draw_bubble(self, text: str) -> None:
        """Draw a simple speech bubble under the avatar."""
        x1, y1 = 15, self.avatar_pack.height + 10
        x2, y2 = self.avatar_pack.width - 15, self.avatar_pack.height + 75
        self._bubble_rect = self.canvas.create_round_rect(
            x1, y1, x2, y2,
            radius=18,
            fill="#f4f4f4",
            outline="#cfcfcf",
            width=2,
        )
        bubble_text = text if text else self.current_state.value
        self._bubble_text = self.canvas.create_text(
            self.avatar_pack.width // 2,
            self.avatar_pack.height + 42,
            text=bubble_text,
            width=self.avatar_pack.width - 50,
            font=("Arial", 11),
        )

    def set_state(self, state: AvatarState, text: str = "") -> None:
        """Set the current avatar state and redraw the UI."""
        self.current_state = state
        self.current_text = text
        self._render_full()
        self._schedule_idle_if_needed()

    def _schedule_idle_if_needed(self) -> None:
        """Return transient states back to idle after a timeout."""
        if self._idle_after_id is not None:
            self.root.after_cancel(self._idle_after_id)
            self._idle_after_id = None

        if self.current_state is not AvatarState.IDLE:
            self._idle_after_id = self.root.after(
                self.idle_timeout_ms,
                lambda: self.set_state(AvatarState.IDLE, ""),
            )

    def handle_event(self, event: AvatarEvent) -> None:
        """Translate an external event into a visible avatar state."""
        state = state_from_event(event.type)
        self.set_state(state, event.text)

    def demo_cycle(self) -> None:
        """Run a tiny demo sequence to validate the runtime visually."""
        sequence = [
            (0, AvatarState.IDLE, "Ready."),
            (1200, AvatarState.LISTENING, "Listening..."),
            (2600, AvatarState.THINKING, "Thinking..."),
            (4300, AvatarState.SPEAKING, "Hello from OpenMimicry."),
            (6500, AvatarState.HAPPY, "Done!"),
            (8500, AvatarState.ERROR, "Just a demo error state."),
            (10500, AvatarState.IDLE, "Back to idle."),
        ]
        for delay, state, text in sequence:
            self.root.after(delay, lambda s=state, t=text: self.set_state(s, t))

    def run(self) -> None:
        """Run the Tk main loop."""
        self.root.mainloop()


def _create_round_rect() -> None:
    """Monkey-patch helper for rounded rectangles on Tk canvases."""
    def create_round_rect(self, x1, y1, x2, y2, radius=16, **kwargs):
        points = [
            x1 + radius, y1,
            x1 + radius, y1,
            x2 - radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    if not hasattr(tk.Canvas, "create_round_rect"):
        tk.Canvas.create_round_rect = create_round_rect  # type: ignore[attr-defined]


_create_round_rect()
