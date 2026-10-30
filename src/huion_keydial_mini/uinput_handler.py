"""UInput handler for generating Linux input events."""

import asyncio
import logging
from typing import List, Optional, Dict
import evdev
from evdev import UInput, ecodes

from .config import Config
from .keymap import KEY_MAPPING
from .input_events import InputEvent, EventType
from .keybind_manager import KeybindManager


logger = logging.getLogger(__name__)


class OutputUnavailable(RuntimeError):
    """The output endpoint is unavailable or its state is uncertain."""


class UInputHandler:
    """Handles creation of virtual input device and event generation."""

    KEY_MAPPING = KEY_MAPPING  # compatibility alias


    def __init__(self, config: Config, keybind_manager: Optional[KeybindManager] = None):
        self.config = config
        self.keybind_manager = keybind_manager
        self.device: Optional[UInput] = None
        self.capabilities = self._build_capabilities()
        self._activations = {}
        self._owners = {}
        self._possibly_down = set()
        self.failed = False
        self.cleanup_confirmed = True
        self.on_fault = None

    async def start(self, retries: int = 10, delay: float = 0.5) -> None:
        """Create the virtual device without blocking the event loop (audit H6)."""
        loop = asyncio.get_event_loop()
        last_error = None
        for attempt in range(retries):
            try:
                self.device = await loop.run_in_executor(
                    None, lambda: UInput(events=self.capabilities,
                                         name=self.config.uinput_device_name))
                logger.info(f"Opened uinput device '{self.config.uinput_device_name}'")
                return
            except Exception as e:
                last_error = e
                logger.info(f"uinput not ready (attempt {attempt + 1}/{retries}): {e}")
                await asyncio.sleep(delay)
        raise RuntimeError(f"Could not open uinput device after {retries} attempts: {last_error}")

    def close(self) -> None:
        """Release owned output before retiring the endpoint; safe to repeat."""
        try:
            self.release_all()
        except OutputUnavailable:
            pass
        self._close_endpoint()

    def _close_endpoint(self):
        device, self.device = self.device, None
        if device is not None:
            try:
                device.close()
            except Exception:
                self.cleanup_confirmed = False
                logger.exception("Error closing uinput endpoint")

    def _fault(self, error):
        if self.failed:
            return
        self.failed = True
        self.cleanup_confirmed = True
        # Include uncertain writes: a write or SYN can fail after taking effect.
        for code in list(self._possibly_down):
            try:
                self.device.write(ecodes.EV_KEY, code, 0)
                self.device.syn()
            except Exception:
                self.cleanup_confirmed = False
        self._activations.clear()
        self._owners.clear()
        self._possibly_down.clear()
        self._close_endpoint()
        if self.on_fault:
            self.on_fault(error)

    def acquire(self, owner, keys):
        """Acquire concrete keys for an activation without disturbing other owners."""
        if self.failed or self.device is None:
            raise OutputUnavailable("Output unavailable")
        if owner in self._activations:
            return
        codes = tuple(dict.fromkeys(self.KEY_MAPPING[name] for name in keys
                                    if name in self.KEY_MAPPING))
        self._activations[owner] = codes
        try:
            for code in codes:
                owners = self._owners.setdefault(code, set())
                if not owners:
                    self._possibly_down.add(code)
                    self.device.write(ecodes.EV_KEY, code, 1)
                    self.device.syn()
                owners.add(owner)
        except Exception as error:
            self._fault(error)
            raise OutputUnavailable("Output unavailable") from error

    def release(self, owner):
        """Release the activation's original keys, independent of current bindings."""
        codes = self._activations.pop(owner, ())
        try:
            for code in reversed(codes):
                owners = self._owners[code]
                owners.discard(owner)
                if not owners:
                    self.device.write(ecodes.EV_KEY, code, 0)
                    self.device.syn()
                    self._possibly_down.discard(code)
                    del self._owners[code]
        except Exception as error:
            self._fault(error)
            raise OutputUnavailable("Output unavailable") from error

    def release_all(self):
        for owner in list(self._activations):
            self.release(owner)

    def _build_capabilities(self) -> Dict:
        """Build device capabilities based on configuration and keybind manager."""
        capabilities = {
            evdev.ecodes.EV_KEY: [],
            # Add mouse relative events for scroll and movement
            evdev.ecodes.EV_REL: [evdev.ecodes.REL_X, evdev.ecodes.REL_Y, evdev.ecodes.REL_WHEEL, evdev.ecodes.REL_HWHEEL],
        }

        # Add all possible keys that might be used
        for key_name in self.KEY_MAPPING.keys():
            key_code = self.KEY_MAPPING.get(key_name)
            if key_code and key_code not in capabilities[evdev.ecodes.EV_KEY]:
                capabilities[evdev.ecodes.EV_KEY].append(key_code)

        # Add keys from keybind manager if available
        if self.keybind_manager:
            for action in self.keybind_manager.get_all_actions().values():
                if action.keys:
                    for key_name in action.keys:
                        key_code = self.KEY_MAPPING.get(key_name)
                        if key_code and key_code not in capabilities[evdev.ecodes.EV_KEY]:
                            capabilities[evdev.ecodes.EV_KEY].append(key_code)

        return capabilities

    async def send_event(self, event: InputEvent):
        owner = ("binding", event.key_code)
        # Release must precede the mutable binding lookup, even after deletion.
        if event.event_type == EventType.KEY_RELEASE:
            self.release(owner)
            return
        action = (self.keybind_manager.get_action(event.key_code)
                  if self.keybind_manager else None)
        if action and action.type in ("keystroke", "keyboard"):
            self.acquire(owner, action.keys or [])

    async def emit_keys(self, keys: List[str]):
        """A tap owns its keys for this atomic, non-suspending output operation."""
        owner = object()
        self.acquire(owner, keys)
        self.release(owner)

    def get_supported_keys(self) -> List[str]:
        """Get list of supported key names."""
        return list(self.KEY_MAPPING.keys())

    def set_keybind_manager(self, keybind_manager: KeybindManager):
        """Set the keybind manager and rebuild capabilities."""
        self.keybind_manager = keybind_manager
        self.capabilities = self._build_capabilities()
        logger.info("Updated keybind manager and rebuilt capabilities")
