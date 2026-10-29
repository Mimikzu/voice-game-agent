"""Mimikzu voice-to-input controller for Minecraft and Rocket League.

Run start_voice_agent.bat on Windows, or:
    python voice_game_agent.py --profile minecraft

The game must be focused. Press F12 to stop the listener.
"""

from __future__ import annotations

import argparse
import re
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard, mouse


SAMPLE_RATE = 16000
BLOCK_DURATION = 0.1
SILENCE_THRESHOLD = 0.002
SILENCE_HANGOVER = 0.4
MAX_UTTERANCE = 4.0
MAX_HOLD_SECONDS = 2.0
TAP_SECONDS = 0.18
DOUBLE_TAP_GAP = 0.12


@dataclass(frozen=True)
class InputBinding:
    device: str
    key: str


@dataclass(frozen=True)
class Action:
    target: str
    seconds: float
    binding: InputBinding
    repetitions: int = 1
    needs_confirmation: bool = False


GENERIC_BINDINGS = {
    "forward": InputBinding("keyboard", "w"),
    "back": InputBinding("keyboard", "s"),
    "left": InputBinding("keyboard", "a"),
    "right": InputBinding("keyboard", "d"),
    "jump": InputBinding("keyboard", "space"),
    "boost": InputBinding("keyboard", "shift"),
    "powerslide": InputBinding("keyboard", "ctrl"),
    "use": InputBinding("keyboard", "e"),
    "attack": InputBinding("mouse", "left"),
}

MINECRAFT_BINDINGS = {
    "forward": InputBinding("keyboard", "w"),
    "back": InputBinding("keyboard", "s"),
    "left": InputBinding("keyboard", "a"),
    "right": InputBinding("keyboard", "d"),
    "jump": InputBinding("keyboard", "space"),
    "sprint": InputBinding("keyboard", "ctrl"),
    "sneak": InputBinding("keyboard", "shift"),
    "use": InputBinding("mouse", "right"),
    "attack": InputBinding("mouse", "left"),
    "inventory": InputBinding("keyboard", "e"),
}

ROCKET_LEAGUE_BINDINGS = {
    "forward": InputBinding("keyboard", "w"),
    "back": InputBinding("keyboard", "s"),
    "left": InputBinding("keyboard", "a"),
    "right": InputBinding("keyboard", "d"),
    "jump": InputBinding("mouse", "right"),
    "boost": InputBinding("mouse", "left"),
    "powerslide": InputBinding("keyboard", "shift"),
    "ballcam": InputBinding("keyboard", "space"),
}

PROFILES = {
    "generic": GENERIC_BINDINGS,
    "minecraft": MINECRAFT_BINDINGS,
    "rocket-league": ROCKET_LEAGUE_BINDINGS,
}

KEYBOARD_KEYS = {
    "space": keyboard.Key.space,
    "shift": keyboard.Key.shift,
    "ctrl": keyboard.Key.ctrl,
    "alt": keyboard.Key.alt,
}
MOUSE_BUTTONS = {
    "left": mouse.Button.left,
    "right": mouse.Button.right,
}
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
ASR_PROMPTS = {
    "minecraft": (
        "Minecraft game voice commands: jump, forward, backward, left, right, sprint, "
        "sneak, use, place block, right click, attack, mine, inventory, hotbar slot."
    ),
    "rocket-league": (
        "Rocket League game voice commands: jump, double jump, boost, turbo, accelerate, "
        "reverse, steer left, steer right, powerslide, drift, ball cam."
    ),
}

COMMAND_ALIASES = {
    "accelerate": "forward",
    "accelerated": "forward",
    "accelerate forward": "forward",
    "accelerate forwards": "forward",
    "go forward": "forward",
    "forward": "forward",
    "forwards": "forward",
    "reverse": "back",
    "back": "back",
    "back up": "back",
    "go backward": "back",
    "backward": "back",
    "backwards": "back",
    "left": "left",
    "steer left": "left",
    "turn left": "left",
    "right": "right",
    "steer right": "right",
    "turn right": "right",
    "jump": "jump",
    "hop": "jump",
    "double jump": "double_jump",
    "boost": "boost",
    "turbo": "boost",
    "powerslide": "powerslide",
    "power slide": "powerslide",
    "drift": "powerslide",
    "use": "use",
    "place": "use",
    "place block": "use",
    "right click": "right_click",
    "right mouse": "right_click",
    "right mouse button": "right_click",
    "attack": "attack",
    "mine": "attack",
    "break": "attack",
    "left click": "left_click",
    "left mouse": "left_click",
    "sprint": "sprint",
    "run": "sprint",
    "sneak": "sneak",
    "crouch": "sneak",
    "inventory": "inventory",
    "open inventory": "inventory",
    "ball cam": "ballcam",
    "ball camera": "ballcam",
}


def _normalize(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    text = re.sub(r"[^\w\s.]", " ", text)
    words = [word for word in text.split() if word not in {"please", "now"}]
    return " ".join(words)


def _make_action(
    target: str,
    seconds: float,
    profile: str,
    repetitions: int = 1,
) -> Action | None:
    binding = PROFILES[profile].get(target)
    if binding is None:
        return None
    return Action(
        target=target,
        seconds=seconds,
        binding=binding,
        repetitions=repetitions,
    )


def _duration_seconds(text: str) -> tuple[str, float] | None:
    match = re.search(
        r"\b(?:for\s+)?(\d+(?:\.\d+)?|"
        + "|".join(NUMBER_WORDS)
        + r")\s*(seconds?|secs?|s|minutes?|mins?|m)\b$",
        text,
    )
    if match is None:
        return None
    amount_text = match.group(1)
    amount = float(amount_text) if amount_text[0].isdigit() else float(NUMBER_WORDS[amount_text])
    unit = match.group(2)
    if unit.startswith("m"):
        amount *= 60
    return text[:match.start()].strip(), min(amount, MAX_HOLD_SECONDS)


def parse_command(transcript: str, profile: str = "generic") -> Action | None:
    text = _normalize(transcript)
    words = text.split()

    slot_match = re.fullmatch(r"(?:(?:switch to )|(?:hotbar ))?slot ([1-9])", text)
    if slot_match:
        if profile != "minecraft":
            return None
        return Action(
            target=f"slot {slot_match.group(1)}",
            seconds=TAP_SECONDS,
            binding=InputBinding("keyboard", slot_match.group(1)),
        )

    repetitions = 1
    if words and len(set(words)) == 1 and words[0] in {"jump", "boost"}:
        # Speech recognition sometimes repeats a short word several times.
        text = words[0]

    hold_requested = any(word in words for word in ("hold", "move"))
    text = re.sub(r"\b(?:hold|move|press|tap|please|now)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    parsed_duration = _duration_seconds(text)
    duration = TAP_SECONDS
    if parsed_duration is not None:
        text, duration = parsed_duration
        hold_requested = True

    target = COMMAND_ALIASES.get(text)
    if target is None:
        return None
    if target in {"right_click", "left_click"}:
        target = "use" if target == "right_click" else "attack"
        if profile == "rocket-league":
            target = "jump" if target == "use" else "boost"
    if target == "double_jump":
        target = "jump"
        repetitions = 2
    if profile == "minecraft" and target in {"boost", "powerslide", "ballcam"}:
        return None
    if profile == "rocket-league" and target in {"use", "attack", "sprint", "sneak", "inventory"}:
        return None
    if hold_requested and parsed_duration is None:
        duration = 1.0
    if target == "boost" and not hold_requested:
        duration = 0.8
        hold_requested = True
    return _make_action(target, duration if hold_requested else TAP_SECONDS, profile, repetitions)


def _resolve_button(binding: InputBinding) -> keyboard.Key | keyboard.KeyCode | mouse.Button:
    if binding.device == "mouse":
        return MOUSE_BUTTONS[binding.key]
    if binding.key in KEYBOARD_KEYS:
        return KEYBOARD_KEYS[binding.key]
    return keyboard.KeyCode.from_char(binding.key)


def execute_action(
    action: Action,
    keyboard_controller: keyboard.Controller,
    mouse_controller: mouse.Controller,
    stop_event: threading.Event,
) -> None:
    if action.needs_confirmation:
        try:
            answer = input(f"Confirm '{action.target}' action? Type yes to allow: ").strip().casefold()
        except EOFError:
            print("No console confirmation available; action cancelled.")
            return
        if answer != "yes":
            print("Action cancelled.")
            return

    controller = mouse_controller if action.binding.device == "mouse" else keyboard_controller
    button = _resolve_button(action.binding)
    for repetition in range(action.repetitions):
        controller.press(button)
        try:
            end_time = time.monotonic() + action.seconds
            while time.monotonic() < end_time and not stop_event.is_set():
                time.sleep(max(0.0, min(0.02, end_time - time.monotonic())))
        finally:
            controller.release(button)
        if repetition + 1 < action.repetitions and not stop_event.is_set():
            time.sleep(DOUBLE_TAP_GAP)


def listen(model: WhisperModel, model_size: str, profile: str, silence_threshold: float) -> None:
    keyboard_controller = keyboard.Controller()
    mouse_controller = mouse.Controller()
    stop_event = threading.Event()

    def on_key_press(key: keyboard.Key | keyboard.KeyCode) -> bool | None:
        if key == keyboard.Key.f12:
            print("\nEmergency stop requested.")
            stop_event.set()
            return False
        return None

    hotkey_listener = keyboard.Listener(on_press=on_key_press)
    hotkey_listener.start()

    block_size = int(SAMPLE_RATE * BLOCK_DURATION)
    pre_roll: deque[np.ndarray] = deque(maxlen=1)
    utterance: list[np.ndarray] = []
    speaking = False
    silence_time = 0.0
    speech_time = 0.0

    def process_utterance() -> None:
        nonlocal utterance, speaking, silence_time, speech_time
        if not utterance:
            return
        segments, _ = model.transcribe(
            np.concatenate(utterance),
            language="en",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=ASR_PROMPTS.get(profile),
        )
        accepted = [
            segment.text.strip()
            for segment in segments
            if segment.no_speech_prob < 0.6 and segment.avg_logprob > -1.0
        ]
        transcript = " ".join(part for part in accepted if part).strip()
        if transcript:
            print(f"Heard: {transcript}")
            action = parse_command(transcript, profile)
            if action is None:
                print("No matching command for this profile; no input sent.")
            else:
                execute_action(action, keyboard_controller, mouse_controller, stop_event)
                print(f"Action: {action.target}")
        utterance = []
        speaking = False
        silence_time = 0.0
        speech_time = 0.0

    bindings = ", ".join(
        f"{action}={binding.device} {binding.key}"
        for action, binding in PROFILES[profile].items()
    )
    print(f"Profile controls: {bindings}")
    print(
        f"Listening with local Whisper '{model_size}' using the '{profile}' profile. "
        "Focus the game; press F12 to stop."
    )
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=block_size,
        ) as stream:
            while not stop_event.is_set():
                block, overflowed = stream.read(block_size)
                if overflowed:
                    print("Warning: microphone input overflowed; some audio may be missing.")
                block = block.flatten()
                volume = float(np.sqrt(np.mean(block**2)))

                if volume >= silence_threshold:
                    if not speaking:
                        utterance.extend(pre_roll)
                        speaking = True
                    utterance.append(block)
                    speech_time += BLOCK_DURATION
                    silence_time = 0.0
                elif speaking:
                    utterance.append(block)
                    speech_time += BLOCK_DURATION
                    silence_time += BLOCK_DURATION
                    if silence_time >= SILENCE_HANGOVER:
                        process_utterance()
                else:
                    pre_roll.append(block)

                if speaking and speech_time >= MAX_UTTERANCE:
                    process_utterance()
    finally:
        stop_event.set()
        hotkey_listener.stop()
    print("Stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Control allowlisted game inputs with local voice recognition."
    )
    parser.add_argument(
        "--model",
        default="tiny",
        help="Faster-Whisper model size. tiny is fastest; small may be more accurate.",
    )
    parser.add_argument("--device", default="cpu", help="Whisper device, such as cpu or cuda.")
    parser.add_argument("--compute-type", default="int8", help="Whisper compute type (default: int8).")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="generic")
    parser.add_argument(
        "--silence-threshold",
        type=float,
        default=SILENCE_THRESHOLD,
        help="Microphone RMS threshold for speech detection; raise it if game audio triggers commands.",
    )
    args = parser.parse_args()

    if args.silence_threshold <= 0:
        parser.error("--silence-threshold must be greater than zero")

    print(f"Mimikzu Voice Game Agent: loading local '{args.model}' speech model.")
    print("The first run may download model files.")
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    listen(model, args.model, args.profile, args.silence_threshold)


if __name__ == "__main__":
    main()
