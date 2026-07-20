"""Executes bound actions by type.

- keystroke: delegated to UInputHandler.send_event (press/release from the
  grabbed event stream).
- macro / command / profile_switch: fired once on KEY_PRESS.

Subprocess launch uses create_subprocess_exec (argv, NO shell). Macro delays
use an injectable sleep so tests run on a fake clock.
"""
import asyncio
import logging
from typing import Optional

from .input_events import InputEvent, EventType

logger = logging.getLogger(__name__)


class ActionEngine:
    def __init__(self, keybind_manager, uinput_handler, sleep=None, spawn=None):
        self.keybind_manager = keybind_manager
        self.uinput_handler = uinput_handler
        self._sleep = sleep or asyncio.sleep
        self._spawn = spawn or asyncio.create_subprocess_exec
        self._running_macros = set()

    async def execute(self, event: InputEvent) -> None:
        action = self.keybind_manager.get_action(event.key_code)
        if not action:
            return
        if action.type in ("keystroke", "keyboard"):
            await self.uinput_handler.send_event(event)
            return
        # macro / command / profile_switch fire once, on press
        if event.event_type != EventType.KEY_PRESS:
            return
        await self.fire(action, token=event.key_code)

    async def fire(self, action, token: Optional[str] = None) -> None:
        """Execute a one-off action object (used by execute() and /api/test-fire)."""
        atype = action.type
        if atype in ("keystroke", "keyboard"):
            await self.uinput_handler.emit_keys(action.keys or [])
        elif atype == "macro":
            key = token if token is not None else id(action)
            if key in self._running_macros:
                return                      # ignore re-trigger while running
            self._running_macros.add(key)
            try:
                await self._run_macro(action)
            finally:
                self._running_macros.discard(key)
        elif atype == "command":
            await self._run_command(action)
        elif atype == "profile_switch":
            self._switch_profile(action)
        else:
            logger.warning("Unknown action type: %r", atype)

    async def _run_macro(self, action) -> None:
        for step in action.steps or []:
            if "delay_ms" in step:
                await self._sleep(step["delay_ms"] / 1000.0)
            elif "keys" in step:
                await self.uinput_handler.emit_keys(step["keys"])

    async def _run_command(self, action) -> None:
        try:
            proc = await self._spawn(
                *action.argv,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            logger.info("Launched command: %s", " ".join(action.argv))
            return proc                     # detached: not awaited
        except Exception as e:
            logger.error("Command failed (%s): %s", action.argv, e)

    def _switch_profile(self, action) -> None:
        target = action.profile
        if target == "next":
            target = self._next_profile()
        if target:
            self.keybind_manager.switch_profile(target)

    def _next_profile(self) -> Optional[str]:
        store = getattr(self.keybind_manager, "profile_store", None)
        if not store:
            return None
        profiles = store.list_profiles()
        if not profiles:
            return None
        try:
            idx = profiles.index(store.get_active())
        except ValueError:
            idx = -1
        return profiles[(idx + 1) % len(profiles)]
