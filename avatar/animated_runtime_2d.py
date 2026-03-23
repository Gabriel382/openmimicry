
"""Animated 2D character runtime with emotion-aware speaking variants."""

from __future__ import annotations

from pathlib import Path
import json
import time
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw

from avatar.character_pack import CharacterPack, load_character_pack
from avatar.director import build_avatar_response
from backends.simple_json_backend import SimpleJSONBackend, SimpleBackendConfig
from tts.pyttsx3_adapter import Pyttsx3Adapter


class AnimatedAvatar2DRuntime:
    """Tk-based animated character runtime for OpenMimicry 6.5+."""

    def __init__(
        self,
        character_root: Path,
        backend_config: SimpleBackendConfig | None = None,
        enable_tts: bool = True,
    ) -> None:
        self.character_root = character_root
        self.pack: CharacterPack = load_character_pack(character_root)
        self.backend = SimpleJSONBackend(backend_config or SimpleBackendConfig())
        self.tts = Pyttsx3Adapter() if enable_tts else None

        self.root = tk.Tk()
        self.root.title(self.pack.config.window_title)
        self.root.configure(bg="white")
        self.root.geometry("520x760")

        self.current_state = self.pack.config.default_state
        self.current_frame_index = 0
        self.current_frames: list[Path] = []
        self.current_photo = None
        self.current_bubble_photo = None
        self.state_started_at = 0.0
        self.playback_after_id = None
        self.current_bubble_text = ""

        self._build_ui()
        self._set_state(self.pack.config.default_state, bubble_text="Standing by.")
        self._tick_animation()

    def _build_ui(self) -> None:
        self.avatar_frame = tk.Frame(self.root, bg="white")
        self.avatar_frame.pack(fill="both", expand=True, padx=12, pady=12)

        self.canvas = tk.Canvas(
            self.avatar_frame,
            width=480,
            height=500,
            bg="white",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self.json_text = tk.Text(self.root, height=10, wrap="word")
        self.json_text.pack(fill="x", padx=12, pady=(0, 8))

        self.entry_frame = tk.Frame(self.root, bg="white")
        self.entry_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.entry = tk.Entry(self.entry_frame)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _event: self.send_prompt())

        self.send_button = tk.Button(self.entry_frame, text="Send", command=self.send_prompt)
        self.send_button.pack(side="left", padx=(8, 0))

    def _create_default_bubble(self, width: int, height: int) -> ImageTk.PhotoImage:
        image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (4, 4, width - 4, height - 18),
            radius=18,
            fill=(255, 255, 255, 235),
            outline=(30, 30, 30, 255),
            width=2,
        )
        draw.polygon(
            [
                (width // 2 - 12, height - 18),
                (width // 2 + 12, height - 18),
                (width // 2, height - 2),
            ],
            fill=(255, 255, 255, 235),
            outline=(30, 30, 30, 255),
        )
        return ImageTk.PhotoImage(image)

    def _bubble_photo(self) -> ImageTk.PhotoImage:
        bubble_path = self.pack.bubble_image_path()
        if bubble_path is not None:
            image = Image.open(bubble_path).convert("RGBA")
            return ImageTk.PhotoImage(image)
        return self._create_default_bubble(
            self.pack.config.bubble.width,
            self.pack.config.bubble.height,
        )

    def _render(self, bubble_text: str = "") -> None:
        self.canvas.delete("all")
        if not self.current_frames:
            return

        frame_path = self.current_frames[self.current_frame_index % len(self.current_frames)]
        frame_image = Image.open(frame_path).convert("RGBA")
        self.current_photo = ImageTk.PhotoImage(frame_image)
        self.canvas.create_image(240, 280, image=self.current_photo)

        if bubble_text:
            self.current_bubble_photo = self._bubble_photo()
            bx = 240 + self.pack.config.bubble.x_offset
            by = 110 + self.pack.config.bubble.y_offset
            self.canvas.create_image(bx, by, image=self.current_bubble_photo)
            self.canvas.create_text(
                bx,
                by - 10,
                text=bubble_text,
                width=max(120, self.pack.config.bubble.width - 30),
                font=("Arial", 11),
            )

    def _set_state(self, state: str, bubble_text: str = "") -> None:
        if state not in self.pack.config.animations:
            state = self.pack.config.fallback_state

        self.current_state = state
        self.current_frames = self.pack.frame_paths(state)
        self.current_frame_index = 0
        self.state_started_at = time.time()
        self.current_bubble_text = bubble_text
        self._render(bubble_text=bubble_text)

    def _state_should_advance(self) -> bool:
        anim = self.pack.config.animations[self.current_state]
        elapsed_ms = int((time.time() - self.state_started_at) * 1000)

        if anim.playback_mode == "noloop":
            return self.current_frame_index >= len(self.current_frames) - 1

        if anim.playback_mode == "loopduringtime":
            return anim.duration_ms is not None and elapsed_ms >= anim.duration_ms

        if anim.playback_mode == "loopwhiletalk" and self.tts is not None:
            return not self.tts.is_speaking()

        return False

    def _resolve_speaking_variant(self, base_animation: str, has_text: bool) -> str:
        if not has_text:
            return base_animation

        preferred = f"{base_animation}_speaking"
        if preferred in self.pack.config.animations:
            return preferred

        if "speaking" in self.pack.config.animations:
            return "speaking"

        return base_animation if base_animation in self.pack.config.animations else self.pack.config.fallback_state

    def _tick_animation(self) -> None:
        if self.current_frames:
            anim = self.pack.config.animations[self.current_state]
            self.current_frame_index += 1

            if anim.playback_mode in {"loopinfinity", "loopduringtime", "loopwhiletalk"}:
                self.current_frame_index %= max(1, len(self.current_frames))
            elif anim.playback_mode == "noloop":
                self.current_frame_index = min(self.current_frame_index, len(self.current_frames) - 1)

            if self._state_should_advance():
                next_state = self.pack.config.animations[self.current_state].next_state
                if next_state not in self.pack.config.animations:
                    next_state = self.pack.config.default_state
                self._set_state(next_state, bubble_text="")
            else:
                self._render(bubble_text=self.current_bubble_text)

            fps = max(1, anim.fps)
            delay_ms = max(30, int(1000 / fps))
        else:
            delay_ms = 120

        self.playback_after_id = self.root.after(delay_ms, self._tick_animation)

    def send_prompt(self) -> None:
        prompt = self.entry.get().strip()
        if not prompt:
            return

        self.entry.delete(0, "end")
        self._set_state("thinking", bubble_text="Thinking...")

        backend_name, model_text = self.backend.ask(prompt)
        response = build_avatar_response(prompt, model_text, backend_name)

        chosen_animation = self._resolve_speaking_variant(
            response.avatar.animation,
            has_text=bool(response.text.strip()),
        )
        response.avatar.animation = chosen_animation
        response.avatar.state = chosen_animation

        self.json_text.delete("1.0", "end")
        self.json_text.insert("1.0", json.dumps(response.to_dict(), indent=2))

        self._set_state(chosen_animation, bubble_text=response.text)

        anim = self.pack.config.animations.get(chosen_animation)
        if response.text.strip() and anim and anim.playback_mode == "loopwhiletalk" and self.tts is not None:
            self.tts.speak_async(response.text)

    def run(self) -> None:
        self.root.mainloop()
