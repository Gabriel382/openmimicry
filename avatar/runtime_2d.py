
"""Simple image-based 2D runtime with config-driven state mapping."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from PIL import Image, ImageTk

from avatar.avatar_pack import LoadedAvatarPack
from avatar.pack_loader import load_named_avatar_pack


class Avatar2DRuntime:
    """Minimal Tk runtime for image-based avatars."""

    def __init__(self, packs_root: Path, pack_name: str) -> None:
        """Initialize runtime and load the selected avatar pack."""
        self.packs_root = packs_root
        self.pack_name = pack_name
        self.pack: LoadedAvatarPack = load_named_avatar_pack(packs_root, pack_name)

        self.root = tk.Tk()
        self.root.title("OpenMimicry Avatar Demo")
        self.root.configure(bg="white")

        self.state_label = tk.Label(self.root, text="state: idle", bg="white")
        self.state_label.pack()

        self.speech_label = tk.Label(
            self.root,
            text="",
            bg="white",
            wraplength=320,
            justify="center",
        )
        self.speech_label.pack(pady=(0, 8))

        self.image_label = tk.Label(self.root, bg="white")
        self.image_label.pack()

        self.current_state = self.pack.config.default_state
        self.current_image_ref = None
        self.after_id = None

        self.set_state(self.current_state)

    def _load_image(self, state: str) -> ImageTk.PhotoImage:
        """Load the image for a state, using fallback rules."""
        asset_path = self.pack.resolve_asset_path(state)
        if asset_path is None:
            raise FileNotFoundError(
                f"No asset found for state '{state}' and no valid fallback asset."
            )

        image = Image.open(asset_path).convert("RGBA")
        return ImageTk.PhotoImage(image)

    def set_state(self, state: str) -> None:
        """Switch runtime to a new state."""
        state_config = self.pack.get_state_config(state)
        if state_config is None:
            state = self.pack.get_fallback_state()
            state_config = self.pack.get_state_config(state)

        if state_config is None:
            raise ValueError("No valid state config found, including fallback.")

        self.current_state = state
        self.state_label.configure(text=f"state: {state}")

        self.current_image_ref = self._load_image(state)
        self.image_label.configure(image=self.current_image_ref)

        speech = state_config.speech_bubble_text or ""
        self.speech_label.configure(text=speech)

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if state != self.pack.config.default_state and state_config.duration_ms:
            self.after_id = self.root.after(
                state_config.duration_ms,
                lambda: self.set_state(self.pack.config.default_state),
            )

    def run(self) -> None:
        """Start the Tk event loop."""
        self.root.mainloop()
