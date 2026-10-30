"""Execute actions with bounded macro tasks and synchronous cancellation boundaries."""
import asyncio
from copy import deepcopy
import logging
from typing import Optional

from .input_events import InputEvent, EventType

logger = logging.getLogger(__name__)


class ActionRejected(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ActionEngine:
    MAX_MACROS = 8

    def __init__(self, keybind_manager, uinput_handler, sleep=None, spawn=None):
        self.keybind_manager = keybind_manager
        self.uinput_handler = uinput_handler
        self._sleep = sleep or asyncio.sleep
        self._spawn = spawn or asyncio.create_subprocess_exec
        self._macros = {}
        self._tasks = set()
        self._task_generations = {}
        self.on_tasks_changed = None
        self.generation = 0
        self.admission = lambda preview: True
        self.busy_count = 0

    @property
    def settled(self):
        return not any(epoch != self.generation and not task.done()
                       for task, epoch in self._task_generations.items())

    def _check(self, generation, preview=False):
        if generation != self.generation:
            raise ActionRejected('cancelled')
        if not self.settled or not self.admission(preview):
            raise ActionRejected('unavailable')

    def invalidate(self, reason='cancelled'):
        """Close the old generation before any async cleanup can suspend."""
        self.generation += 1
        for task in tuple(self._tasks):
            task.cancel()
        self.uinput_handler.release_all()

    async def drain(self):
        tasks = tuple(self._tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _track(self, coroutine, macro_key=None):
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        self._task_generations[task] = self.generation
        if macro_key is not None:
            self._macros[macro_key] = task

        def finished(done):
            self._tasks.discard(done)
            self._task_generations.pop(done, None)
            if self.on_tasks_changed:
                self.on_tasks_changed()
            if macro_key is not None and self._macros.get(macro_key) is done:
                del self._macros[macro_key]
            if not done.cancelled():
                error = done.exception()
                if error and not isinstance(error, ActionRejected):
                    logger.error('Action failed: %s', error)
        task.add_done_callback(finished)
        return task

    def _macro(self, action, token, generation, preview):
        key = (generation, token)
        if key in self._macros and not self._macros[key].done():
            raise ActionRejected('busy')
        if sum(not task.done() for task in self._macros.values()) >= self.MAX_MACROS:
            self.busy_count += 1
            raise ActionRejected('busy')
        return self._track(self._perform(action, generation, preview), key)

    async def execute(self, event: InputEvent, generation=None) -> bool:
        generation = self.generation if generation is None else generation
        self._check(generation)
        # Original owners must release even if their current binding was deleted.
        if event.event_type == EventType.KEY_RELEASE:
            await self.uinput_handler.send_event(event)
            return True
        action = self.keybind_manager.get_action(event.key_code)
        if not action:
            return False
        action = deepcopy(action)
        if action.type in ('keystroke', 'keyboard'):
            await self.uinput_handler.send_event(event)
        elif action.type == 'macro':
            try:
                self._macro(action, event.key_code, generation, False)
            except ActionRejected as error:
                if error.code == 'busy':
                    return False
                raise
        else:
            await self._perform(action, generation, False)
        return True

    async def fire(self, action, token: Optional[str] = None):
        generation = self.generation
        self._check(generation, preview=True)
        action = deepcopy(action)
        # A synchronous profile switch completes by invalidating its own generation.
        if action.type == 'profile_switch':
            await self._perform(action, generation, True)
            return
        if action.type == 'macro':
            task = self._macro(action, token if token is not None else object(),
                               generation, True)
        else:
            task = self._track(self._perform(action, generation, True))
        try:
            await task
            if generation != self.generation:
                raise ActionRejected('cancelled')
        except asyncio.CancelledError:
            # Request cancellation propagates; lifecycle cancellation is an API outcome.
            if generation != self.generation:
                raise ActionRejected('cancelled') from None
            raise

    async def _perform(self, action, generation, preview):
        self._check(generation, preview)
        if action.type in ('keystroke', 'keyboard'):
            await self.uinput_handler.emit_keys(action.keys or [])
        elif action.type == 'macro':
            for step in action.steps or []:
                self._check(generation, preview)
                if 'delay_ms' in step:
                    await self._sleep(step['delay_ms'] / 1000.0)
                elif 'keys' in step:
                    await self.uinput_handler.emit_keys(step['keys'])
        elif action.type == 'command':
            # Await creation only; never own or wait for the child process lifetime.
            await self._spawn(*action.argv, stdout=asyncio.subprocess.DEVNULL,
                              stderr=asyncio.subprocess.DEVNULL)
        elif action.type == 'profile_switch':
            target = self._next_profile() if action.profile == 'next' else action.profile
            if target:
                self.keybind_manager.switch_profile(target)
        else:
            raise ActionRejected('invalid_action')

    def _next_profile(self) -> Optional[str]:
        store = getattr(self.keybind_manager, 'profile_store', None)
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
