import asyncio

from huion_keydial_mini.action_engine import ActionEngine
from huion_keydial_mini.keybind_manager import KeybindAction
from huion_keydial_mini.input_events import InputEvent, EventType


class FakeUinput:
    def __init__(self):
        self.sent = []
        self.emitted = []

    async def send_event(self, ev):
        self.sent.append(ev)

    async def emit_keys(self, keys):
        self.emitted.append(list(keys))


class FakeStore:
    def __init__(self, profiles, active):
        self._p, self._a = profiles, active

    def list_profiles(self):
        return self._p

    def get_active(self):
        return self._a


class FakeMgr:
    def __init__(self, action=None, profile_store=None):
        self.action = action
        self.profile_store = profile_store
        self.switched = []

    def get_action(self, aid):
        return self.action

    def switch_profile(self, name):
        self.switched.append(name)


def press(aid="BUTTON_1"):
    return InputEvent(EventType.KEY_PRESS, aid)


def release(aid="BUTTON_1"):
    return InputEvent(EventType.KEY_RELEASE, aid)


def test_keystroke_delegates_to_uinput():
    u = FakeUinput()
    eng = ActionEngine(FakeMgr(KeybindAction(type="keystroke", keys=["KEY_A"])), u)
    ev = press()
    asyncio.run(eng.execute(ev))
    assert u.sent == [ev] and u.emitted == []


def test_macro_runs_steps_and_delays_on_press_only():
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    u = FakeUinput()
    action = KeybindAction(type="macro", steps=[
        {"keys": ["KEY_A"]}, {"delay_ms": 100}, {"keys": ["KEY_B"]}])
    eng = ActionEngine(FakeMgr(action), u, sleep=fake_sleep)
    asyncio.run(eng.execute(press()))
    assert u.emitted == [["KEY_A"], ["KEY_B"]]
    assert slept == [0.1]
    asyncio.run(eng.execute(release()))          # release: no-op
    assert u.emitted == [["KEY_A"], ["KEY_B"]]


def test_command_spawns_argv_no_shell():
    spawned = {}

    async def fake_spawn(*argv, **kw):
        spawned["argv"] = argv
        spawned["kw"] = kw
        return object()

    eng = ActionEngine(FakeMgr(KeybindAction(type="command", argv=["xdg-open", "https://x"])),
                       FakeUinput(), spawn=fake_spawn)
    asyncio.run(eng.execute(press()))
    assert spawned["argv"] == ("xdg-open", "https://x")


def test_profile_switch_named():
    mgr = FakeMgr(KeybindAction(type="profile_switch", profile="Krita"))
    eng = ActionEngine(mgr, FakeUinput())
    asyncio.run(eng.execute(press()))
    assert mgr.switched == ["Krita"]


def test_profile_switch_next_cycles():
    store = FakeStore(["Default", "Krita", "Video"], "Krita")
    mgr = FakeMgr(KeybindAction(type="profile_switch", profile="next"), profile_store=store)
    eng = ActionEngine(mgr, FakeUinput())
    asyncio.run(eng.execute(press()))
    assert mgr.switched == ["Video"]


def test_fire_keystroke_one_off():
    u = FakeUinput()
    eng = ActionEngine(FakeMgr(), u)
    asyncio.run(eng.fire(KeybindAction(type="keystroke", keys=["KEY_F9"])))
    assert u.emitted == [["KEY_F9"]]
