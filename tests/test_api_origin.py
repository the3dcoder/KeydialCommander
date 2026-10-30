import asyncio
from functools import partial

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from huion_keydial_mini.api_server import ApiServer


def run_request(host, origin=None, path='/api/test-fire'):
    api = ApiServer(None, None, None, None, version='test')
    headers = {'Host': host}
    if origin is not None:
        headers['Origin'] = origin
    request = make_mocked_request('POST', path, headers=headers, app=api.app)
    called = []

    async def handler(request):
        called.append(request.path)
        return web.Response(status=200)

    composed = handler
    for middleware in reversed(api.app.middlewares):
        composed = partial(middleware, handler=composed)
    return asyncio.run(composed(request)), called


@pytest.mark.parametrize('origin', ['https://example.com', 'null',
                                  'http://127.0.0.1:9999',
                                  'http://localhost:8137/unexpected',
                                  'http://user@localhost:8137'])
def test_api_rejects_external_or_invalid_browser_origins(origin):
    response, called = run_request('127.0.0.1:8137', origin)
    assert response.status == 403
    assert called == []


@pytest.mark.parametrize('host', ['attacker.example:8137', '127.0.0.1.attacker.example',
                                'user@127.0.0.1:8137'])
def test_api_rejects_nonlocal_host_headers(host):
    response, called = run_request(host)
    assert response.status == 403
    assert called == []


@pytest.mark.parametrize('origin', [None, 'http://127.0.0.1:8137',
                                  'http://localhost:8137',
                                  'http://localhost:5173'])
def test_local_ui_development_and_cli_requests_work(origin):
    response, called = run_request('127.0.0.1:8137', origin)
    assert response.status == 200
    assert called == ['/api/test-fire']


def test_websocket_upgrade_is_subject_to_the_same_origin_check():
    response, called = run_request('127.0.0.1:8137', 'https://example.com', '/api/events')
    assert response.status == 403
    assert called == []
