import asyncio
import json

import aiohttp
import pytest

from evdev import ecodes

from huion_keydial_mini.keybind_manager import KeybindAction
from tests.test_recovery_integration import driver
from tests.test_output_ownership import Output


class Request:
    can_read_body = True
    def __init__(self, action):
        self.action = action
    async def json(self):
        return {'action': self.action}


def test_status_distinguishes_connection_readiness_and_uncertain_output(tmp_path, monkeypatch):
    async def run():
        dev, nodes, _, _ = driver(tmp_path, monkeypatch)
        nodes['keyboard'].down = {ecodes.KEY_LEFTCTRL}
        await dev.evdev_source.start()
        response = await dev.api_server._status(None)
        body = json.loads(response.text)
        assert body['device']['connected'] and not body['device']['ready']
        assert body['device']['state'] == 'release_controls'
        assert body['output']['available']
        await dev.stop()
    asyncio.run(run())


def test_preview_unavailable_is_structured_non_success(tmp_path, monkeypatch):
    async def run():
        dev, nodes, _, _ = driver(tmp_path, monkeypatch)
        nodes['keyboard'].down = {ecodes.KEY_LEFTCTRL}
        await dev.evdev_source.start()
        response = await dev.api_server._test_fire(Request({'keys': ['KEY_A']}))
        assert response.status == 503
        assert json.loads(response.text)['error']['code'] == 'unavailable'
        await dev.stop()
    asyncio.run(run())


def test_failed_output_preview_cannot_return_ok(tmp_path, monkeypatch):
    async def run():
        dev, _, _, _ = driver(tmp_path, monkeypatch)
        dev.uinput_handler.device = Output(fail=lambda code, value: value == 1)
        response = await dev.api_server._test_fire(Request({'keys': ['KEY_A']}))
        assert response.status == 503
        body = json.loads((await dev.api_server._status(None)).text)
        assert not body['output']['available']
        assert body['device']['state'] == 'output_unavailable'
        await dev.stop()
    asyncio.run(run())


def test_profile_switch_preview_completes_its_own_boundary(tmp_path, monkeypatch):
    async def run():
        dev, _, _, _ = driver(tmp_path, monkeypatch)
        dev.profile_store.create_profile('Other')
        response = await dev.api_server._test_fire(Request({'type': 'profile_switch', 'profile': 'Other'}))
        assert response.status == 200
        assert dev.profile_store.get_active() == 'Other'
        await dev.stop()
    asyncio.run(run())


def test_aborting_http_preview_cancels_its_macro(tmp_path, monkeypatch):
    async def run():
        dev, _, _, output = driver(tmp_path, monkeypatch)
        entered, cancelled, resume = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def sleep(_):
            entered.set()
            try:
                await resume.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        dev.action_engine._sleep = sleep
        dev.api_server.port = 0
        await dev.api_server.start()
        port = dev.api_server._runner.addresses[0][1]
        try:
            async with aiohttp.ClientSession() as client:
                request = asyncio.create_task(client.post(f'http://127.0.0.1:{port}/api/test-fire',
                    json={'type': 'macro', 'steps': [{'delay_ms': 100}, {'keys': ['KEY_B']}]}))
                await asyncio.wait_for(entered.wait(), 1)
                request.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await request
                await asyncio.wait_for(cancelled.wait(), 1)
                await dev.action_engine.drain()
                resume.set()
                assert output.writes == []
        finally:
            resume.set()
            await dev.stop()
    asyncio.run(run())


def test_invalid_stored_profile_activation_returns_structured_error(tmp_path, monkeypatch):
    async def run():
        dev, _, _, _ = driver(tmp_path, monkeypatch)
        dev.profile_store.create_profile('Broken')
        dev.profile_store.save_binding('BUTTON_1', KeybindAction(type='unknown'), profile='Broken')
        request = Request({})
        request.match_info = {'name': 'Broken'}
        response = await dev.api_server._activate_profile(request)
        assert response.status == 400
        assert dev.profile_store.get_active() == 'Default'
        assert 'error' in json.loads(response.text)
        await dev.stop()
    asyncio.run(run())
