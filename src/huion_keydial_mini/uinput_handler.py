"""UInput handler for generating Linux input events."""

import asyncio
import logging
from typing import List, Optional, Dict
import evdev
from evdev import UInput, ecodes

from .config import Config
from .keymap import KEY_MAPPING
from .input_events import InputEvent, EventType
from .keybind_manager import KeybindManager, KeybindAction, EventType as BindEventType


logger = logging.getLogger(__name__)


class UInputHandler:
    """Handles creation of virtual input device and event generation."""

    KEY_MAPPING = KEY_MAPPING  # compatibility alias


    def __init__(self, config: Config, keybind_manager: Optional[KeybindManager] = None):
        self.config = config
        self.keybind_manager = keybind_manager
        self.device: Optional[UInput] = None
        self.capabilities = self._build_capabilities()

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
        """Close the virtual device (idempotent)."""
        if self.device is not None:
            try:
                self.device.close()
            except Exception as e:
                logger.warning(f"Error closing uinput device: {e}")
            self.device = None

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
        """Send an input event to the virtual device."""
        if not self.device:
            logger.warning("No virtual device available")
            return

        try:
            # Get the action ID from the event
            action_id = self._get_action_id_from_event(event)
            if not action_id:
                logger.debug(f"No action ID found for event: {event}")
                return

            # Get the keybind action from the manager
            if not self.keybind_manager:
                logger.warning("No keybind manager available")
                return

            action = self.keybind_manager.get_action(action_id)
            if not action:
                logger.debug(f"No binding found for action: {action_id}")
                return

            # Execute the action based on its type
            if action.type in ("keystroke", "keyboard"):
                await self._send_keyboard_action(action, event)
            else:
                logger.warning(f"Unknown action type: {action.type}")

        except Exception as e:
            logger.error(f"Error sending event: {e}")

    def _get_action_id_from_event(self, event: InputEvent) -> Optional[str]:
        if event.key_code != None:
            return event.key_code
        else:
            logger.warning(f"No keycode found for event: {event}")
        return None

    async def _send_keyboard_action(self, action: KeybindAction, event: InputEvent):
        """Send a keyboard action."""
        if not action.keys:
            logger.warning("Keyboard action has no keys defined")
            return

        if not self.device:
            logger.warning("No virtual device available")
            return

        # Determine if this is a press or release
        is_press = event.event_type == EventType.KEY_PRESS

        try:
            if is_press:
                # Press all keys in order
                for key_name in action.keys:
                    key_code = self.KEY_MAPPING.get(key_name)
                    if key_code:
                        self.device.write(evdev.ecodes.EV_KEY, key_code, 1)
                        self.device.syn()
                        logger.debug(f"Pressed key: {key_name}")
                    else:
                        logger.warning(f"Unknown key: {key_name}")
            else:
                # Release all keys in reverse order
                for key_name in reversed(action.keys):
                    key_code = self.KEY_MAPPING.get(key_name)
                    if key_code:
                        self.device.write(evdev.ecodes.EV_KEY, key_code, 0)
                        self.device.syn()
                        logger.debug(f"Released key: {key_name}")
                    else:
                        logger.warning(f"Unknown key: {key_name}")

        except Exception as e:
            logger.error(f"Error sending keyboard action: {e}")

    async def emit_keys(self, keys: List[str]):
        """Tap a chord: press all keys in order, release in reverse. Used by
        macros and test-fire (no binding lookup)."""
        if not self.device or not keys:
            return
        try:
            for name in keys:
                code = self.KEY_MAPPING.get(name)
                if code:
                    self.device.write(evdev.ecodes.EV_KEY, code, 1)
                    self.device.syn()
            for name in reversed(keys):
                code = self.KEY_MAPPING.get(name)
                if code:
                    self.device.write(evdev.ecodes.EV_KEY, code, 0)
                    self.device.syn()
        except Exception as e:
            logger.error(f"Error emitting keys: {e}")

    def get_supported_keys(self) -> List[str]:
        """Get list of supported key names."""
        return list(self.KEY_MAPPING.keys())

    def set_keybind_manager(self, keybind_manager: KeybindManager):
        """Set the keybind manager and rebuild capabilities."""
        self.keybind_manager = keybind_manager
        self.capabilities = self._build_capabilities()
        logger.info("Updated keybind manager and rebuilt capabilities")
