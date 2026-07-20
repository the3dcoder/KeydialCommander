"""Embedded Commander API: aiohttp REST + WebSocket, plus static SPA.

Binds 127.0.0.1 only. Reuses ProfileStore/KeybindManager for all mutations
(no duplicate logic) and relays EventBus events over a WebSocket.
"""
import logging
import weakref
from pathlib import Path

from aiohttp import web, WSCloseCode

from . import ipc
from .keymap import SUPPORTED_KEYS

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"
DIST_DIR = WEB_DIR / "dist"


def _index_file() -> Path:
    """The built SPA index if present, else the placeholder."""
    built = DIST_DIR / "index.html"
    return built if built.exists() else (WEB_DIR / "index.html")


def group_keys(names):
    """Group key names into categories for the frontend picker."""
    groups = {"Function": [], "Letters": [], "Numbers": [], "Modifiers": [],
              "Navigation": [], "Media": [], "Mouse": [], "Other": []}
    nav = {"KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT", "KEY_HOME", "KEY_END",
           "KEY_PAGEUP", "KEY_PAGEDOWN", "KEY_INSERT", "KEY_DELETE"}
    media = {"KEY_VOLUMEUP", "KEY_VOLUMEDOWN", "KEY_MUTE", "KEY_PLAYPAUSE",
             "KEY_NEXTSONG", "KEY_PREVIOUSSONG", "KEY_STOPCD"}
    for n in names:
        if n.startswith("BTN_"):
            groups["Mouse"].append(n)
        elif n.startswith("KEY_F") and n[5:].isdigit():
            groups["Function"].append(n)
        elif len(n) == 5 and n[4:].isalpha():
            groups["Letters"].append(n)
        elif len(n) == 5 and n[4:].isdigit():
            groups["Numbers"].append(n)
        elif any(m in n for m in ("CTRL", "SHIFT", "ALT", "META", "CAPSLOCK")):
            groups["Modifiers"].append(n)
        elif n in nav:
            groups["Navigation"].append(n)
        elif n in media:
            groups["Media"].append(n)
        else:
            groups["Other"].append(n)
    return {k: v for k, v in groups.items() if v}


def json_error(message, code="error", status=400):
    return web.json_response({"error": {"code": code, "message": message}}, status=status)


async def _json(request):
    """Parse a JSON body, tolerating an empty body as {}."""
    if not request.can_read_body:
        return {}
    try:
        return await request.json()
    except Exception:
        return {}


class ApiServer:
    def __init__(self, keybind_manager, profile_store, event_bus, action_engine,
                 version, host="127.0.0.1", port=8137):
        self.keybind_manager = keybind_manager
        self.profile_store = profile_store
        self.event_bus = event_bus
        self.action_engine = action_engine
        self.version = version
        self.host = host
        self.port = port
        self.device_connected = False
        self.bound_port = None
        self._runner = None
        self.app = self._build_app()

    def set_device_connected(self, connected):
        self.device_connected = bool(connected)

    # -- routing ------------------------------------------------------------
    def _build_app(self):
        app = web.Application()
        app["websockets"] = weakref.WeakSet()   # open /api/events sockets
        app.on_shutdown.append(self._on_shutdown)
        r = app.router
        r.add_get("/api/status", self._status)
        r.add_get("/api/keys", self._keys)
        self._add_routes(r)                     # extended in later tasks
        r.add_get("/", self._index)
        if (DIST_DIR / "assets").is_dir():      # serve built JS/CSS
            r.add_static("/assets", DIST_DIR / "assets")
        r.add_get("/{tail:.*}", self._spa_fallback)
        return app

    async def _on_shutdown(self, app):
        """Close open WebSockets so shutdown doesn't block on connected clients."""
        for ws in set(app["websockets"]):
            try:
                await ws.close(code=WSCloseCode.GOING_AWAY, message=b"server shutdown")
            except Exception:
                pass

    def _add_routes(self, router):
        router.add_get("/api/profiles", self._list_profiles)
        router.add_post("/api/profiles", self._create_profile)
        router.add_put("/api/profiles/{name}", self._rename_profile)
        router.add_delete("/api/profiles/{name}", self._delete_profile)
        router.add_post("/api/profiles/{name}/activate", self._activate_profile)
        router.add_get("/api/profiles/{name}/bindings", self._get_bindings)
        router.add_put("/api/profiles/{name}/bindings/{action_id}", self._put_binding)
        router.add_delete("/api/profiles/{name}/bindings/{action_id}", self._delete_binding)
        router.add_put("/api/profiles/{name}/settings", self._put_settings)
        router.add_get("/api/profiles/{name}/export", self._export_profile)
        router.add_post("/api/profiles/import", self._import_profile)
        router.add_post("/api/test-fire", self._test_fire)
        router.add_get("/api/events", self._events)

    def _refresh_if_active(self, profile_name):
        """Reload the live binding map if an edit touched the active profile."""
        if self.keybind_manager and profile_name == self.profile_store.get_active():
            self.keybind_manager.reload_bindings()

    # -- profile CRUD -------------------------------------------------------
    async def _list_profiles(self, request):
        active = self.profile_store.get_active()
        out = []
        for name in self.profile_store.list_profiles():
            out.append({"name": name,
                        "binding_count": len(self.profile_store.load_bindings(name)),
                        "active": name == active})
        return web.json_response(out)

    async def _create_profile(self, request):
        from .profile_store import ProfileError
        data = await _json(request)
        try:
            self.profile_store.create_profile(str(data.get("name")), data.get("clone_from"))
        except ProfileError as e:
            return json_error(str(e))
        return web.json_response({"status": "ok"})

    async def _rename_profile(self, request):
        from .profile_store import ProfileError
        data = await _json(request)
        name = request.match_info["name"]
        try:
            self.profile_store.rename_profile(name, str(data.get("new_name")))
        except ProfileError as e:
            return json_error(str(e))
        self._refresh_if_active(str(data.get("new_name")))
        return web.json_response({"status": "ok"})

    async def _delete_profile(self, request):
        from .profile_store import ProfileError
        try:
            self.profile_store.delete_profile(request.match_info["name"])
        except ProfileError as e:
            return json_error(str(e))
        return web.json_response({"status": "ok"})

    async def _activate_profile(self, request):
        from .profile_store import ProfileError
        name = request.match_info["name"]
        try:
            if self.keybind_manager:
                self.keybind_manager.switch_profile(name)
            else:
                self.profile_store.set_active(name)
        except ProfileError as e:
            return json_error(str(e))
        return web.json_response({"status": "ok"})

    # -- bindings -----------------------------------------------------------
    async def _get_bindings(self, request):
        from .profile_store import ProfileError
        name = request.match_info["name"]
        try:
            bindings = self.profile_store.load_bindings(name)
            sensitivity = self.profile_store.get_dial_sensitivity(name)
        except ProfileError as e:
            return json_error(str(e), code="not_found", status=404)
        return web.json_response({
            "bindings": {aid: a.to_dict() for aid, a in bindings.items()},
            "dial_sensitivity": sensitivity,
        })

    async def _put_binding(self, request):
        from .profile_store import ProfileError
        from .validation import normalize_action_id, validate_action, ValidationError
        from .keybind_manager import KeybindAction
        name = request.match_info["name"]
        data = await _json(request)
        try:
            aid = normalize_action_id(request.match_info["action_id"])
            action = validate_action(data)
            self.profile_store.save_binding(aid, KeybindAction.from_dict(action), profile=name)
        except (ValidationError, ProfileError) as e:
            return json_error(str(e))
        self._refresh_if_active(name)
        return web.json_response({"status": "ok"})

    async def _delete_binding(self, request):
        from .profile_store import ProfileError
        from .validation import normalize_action_id, ValidationError
        name = request.match_info["name"]
        try:
            aid = normalize_action_id(request.match_info["action_id"])
            self.profile_store.remove_binding(aid, profile=name)
        except (ValidationError, ProfileError) as e:
            return json_error(str(e))
        self._refresh_if_active(name)
        return web.json_response({"status": "ok"})

    async def _put_settings(self, request):
        from .profile_store import ProfileError
        name = request.match_info["name"]
        data = await _json(request)
        try:
            self.profile_store.set_dial_sensitivity(float(data.get("dial_sensitivity", 1.0)), name)
        except (ProfileError, TypeError, ValueError) as e:
            return json_error(str(e))
        self._refresh_if_active(name)
        return web.json_response({"status": "ok"})

    async def _export_profile(self, request):
        from .profile_store import ProfileError
        name = request.match_info["name"]
        try:
            text = self.profile_store.export_profile(name)
        except ProfileError as e:
            return json_error(str(e), code="not_found", status=404)
        return web.Response(text=text, content_type="application/x-yaml",
                            headers={"Content-Disposition": 'attachment; filename="%s.yaml"' % name})

    async def _import_profile(self, request):
        from .profile_store import ProfileError
        data = await _json(request)
        try:
            self.profile_store.import_profile(str(data.get("yaml", "")), str(data.get("name")))
        except ProfileError as e:
            return json_error(str(e))
        return web.json_response({"status": "ok"})

    # -- test-fire + events -------------------------------------------------
    async def _test_fire(self, request):
        from .validation import validate_action, ValidationError
        from .keybind_manager import KeybindAction
        data = await _json(request)
        action_data = data.get("action", data)     # accept {action:{...}} or bare
        try:
            validated = validate_action(action_data)
        except ValidationError as e:
            return json_error(str(e))
        if self.action_engine:
            await self.action_engine.fire(KeybindAction.from_dict(validated))
        return web.json_response({"status": "ok"})

    async def _events(self, request):
        import asyncio
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        if self.event_bus is None:
            await ws.close()
            return ws
        request.app["websockets"].add(ws)       # so shutdown can close it
        queue = self.event_bus.subscribe()

        async def pump():
            while True:
                event = await queue.get()
                await ws.send_json(event)

        pump_task = asyncio.ensure_future(pump())
        try:
            async for _msg in ws:               # exits when the client (or server) closes
                pass
        finally:
            pump_task.cancel()
            self.event_bus.unsubscribe(queue)
            request.app["websockets"].discard(ws)
        return ws

    # -- basic handlers -----------------------------------------------------
    async def _status(self, request):
        return web.json_response({
            "device": {"connected": self.device_connected},
            "service": {"version": self.version},
            "active_profile": self.profile_store.get_active(),
        })

    async def _keys(self, request):
        return web.json_response({"groups": group_keys(SUPPORTED_KEYS),
                                  "all": list(SUPPORTED_KEYS)})

    async def _index(self, request):
        return web.FileResponse(_index_file())

    async def _spa_fallback(self, request):
        if request.path.startswith("/api/"):
            return json_error("Not found", code="not_found", status=404)
        # Serve a real built asset if it exists (e.g. /vite.svg), else SPA index
        candidate = DIST_DIR / request.path.lstrip("/")
        if candidate.is_file() and DIST_DIR in candidate.resolve().parents:
            return web.FileResponse(candidate)
        return web.FileResponse(_index_file())

    # -- lifecycle ----------------------------------------------------------
    async def start(self):
        # Short graceful window: closing WebSockets (on_shutdown) should be instant,
        # but never let cleanup block the daemon's shutdown for long.
        self._runner = web.AppRunner(self.app, shutdown_timeout=3.0)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        self.bound_port = self.port
        try:
            (ipc.runtime_dir() / "port").write_text(str(self.bound_port))
        except Exception as e:
            logger.warning("Could not write port file: %s", e)
        logger.info("Commander API on http://%s:%d", self.host, self.bound_port)
        return self.bound_port

    async def stop(self):
        if self._runner:
            import asyncio
            try:
                await asyncio.wait_for(self._runner.cleanup(), timeout=5.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("API cleanup did not finish cleanly: %s", e)
            self._runner = None
        try:
            (ipc.runtime_dir() / "port").unlink()
        except Exception:
            pass
