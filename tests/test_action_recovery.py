import asyncio

import pytest
from evdev import ecodes

from huion_keydial_mini.action_engine import ActionEngine
from huion_keydial_mini.input_events import InputEvent, EventType
from huion_keydial_mini.keybind_manager import KeybindAction
from tests.test_output_ownership import rig


def test_physical_macro_does_not_block_release_and_reset_prevents_later_steps():
    manager, writer = rig()
    manager.keybind_map.update({
        'BUTTON_1': KeybindAction(type='macro', steps=[{'delay_ms': 5000}, {'keys': ['KEY_B']}]),
        'BUTTON_13': KeybindAction(keys=['KEY_LEFTCTRL']),
    })

    async def run():
        entered, resume = asyncio.Event(), asyncio.Event()
        async def sleep(_):
            entered.set()
            await resume.wait()
        engine = ActionEngine(manager, writer, sleep=sleep)
        await engine.execute(InputEvent(EventType.KEY_PRESS, 'BUTTON_13'))
        await engine.execute(InputEvent(EventType.KEY_PRESS, 'BUTTON_1'))
        await entered.wait()
        await engine.execute(InputEvent(EventType.KEY_RELEASE, 'BUTTON_13'))
        assert writer.device.down == set()
        engine.invalidate()
        resume.set()
        await engine.drain()
        assert writer.device.writes == [(ecodes.KEY_LEFTCTRL, 1), (ecodes.KEY_LEFTCTRL, 0)]
    asyncio.run(run())


def test_cancel_resistant_delay_cannot_emit_after_generation_changes():
    manager, writer = rig()
    async def run():
        entered, cancelled, resume = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def sleep(_):
            entered.set()
            try:
                await resume.wait()
            except asyncio.CancelledError:
                cancelled.set()
                await resume.wait()
        engine = ActionEngine(manager, writer, sleep=sleep)
        manager.keybind_map['BUTTON_1'] = KeybindAction(type='macro', steps=[
            {'delay_ms': 100}, {'keys': ['KEY_B']}])
        await engine.execute(InputEvent(EventType.KEY_PRESS, 'BUTTON_1'))
        await entered.wait()
        engine.invalidate()
        await cancelled.wait()
        with pytest.raises(RuntimeError, match='unavailable'):
            await engine.fire(KeybindAction(keys=['KEY_A']))
        resume.set()
        await engine.drain()
        assert writer.device.writes == []
    asyncio.run(run())


def test_eight_macro_limit_and_duplicate_retrigger_have_no_backlog():
    manager, writer = rig()
    async def run():
        resume = asyncio.Event()
        async def sleep(_):
            await resume.wait()
        engine = ActionEngine(manager, writer, sleep=sleep)
        for number in range(1, 10):
            manager.keybind_map[f'BUTTON_{number}'] = KeybindAction(type='macro', steps=[
                {'delay_ms': 100}, {'keys': ['KEY_B']}])
        for number in range(1, 9):
            assert await engine.execute(InputEvent(EventType.KEY_PRESS, f'BUTTON_{number}'))
        assert not await engine.execute(InputEvent(EventType.KEY_PRESS, 'BUTTON_1'))
        assert not await engine.execute(InputEvent(EventType.KEY_PRESS, 'BUTTON_9'))
        with pytest.raises(RuntimeError, match='busy'):
            await engine.fire(KeybindAction(type='macro', steps=[]))
        engine.invalidate()
        resume.set()
        await engine.drain()
        assert writer.device.writes == []
    asyncio.run(run())


def test_reset_cancels_preview_with_non_success_outcome():
    manager, writer = rig()
    async def run():
        entered = asyncio.Event()
        async def sleep(_):
            entered.set()
            await asyncio.Event().wait()
        engine = ActionEngine(manager, writer, sleep=sleep)
        preview = asyncio.create_task(engine.fire(KeybindAction(type='macro', steps=[
            {'delay_ms': 100}, {'keys': ['KEY_B']}])))
        await entered.wait()
        engine.invalidate()
        with pytest.raises(RuntimeError, match='cancelled'):
            await preview
        await engine.drain()
        assert writer.device.writes == []
    asyncio.run(run())


def test_request_cancellation_removes_preview_work():
    manager, writer = rig()
    async def run():
        entered = asyncio.Event()
        async def sleep(_):
            entered.set()
            await asyncio.Event().wait()
        engine = ActionEngine(manager, writer, sleep=sleep)
        preview = asyncio.create_task(engine.fire(KeybindAction(type='macro', steps=[
            {'delay_ms': 100}, {'keys': ['KEY_B']}])))
        await entered.wait()
        preview.cancel()
        with pytest.raises(asyncio.CancelledError):
            await preview
        await engine.drain()
        assert writer.device.writes == []
    asyncio.run(run())


def test_engine_release_bypasses_deleted_binding():
    manager, writer = rig()
    async def run():
        engine = ActionEngine(manager, writer)
        manager.keybind_map['BUTTON_13'] = KeybindAction(keys=['KEY_LEFTCTRL'])
        await engine.execute(InputEvent(EventType.KEY_PRESS, 'BUTTON_13'))
        manager.keybind_map.clear()
        await engine.execute(InputEvent(EventType.KEY_RELEASE, 'BUTTON_13'))
        assert writer.device.down == set()
    asyncio.run(run())
