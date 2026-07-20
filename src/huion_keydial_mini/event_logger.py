#!/usr/bin/env python3
"""Live evdev monitor for the Huion Keydial Mini.

Grabs the device's evdev nodes and prints each decoded action ID as you press
buttons / turn the dial. Replaces the old vendor-frame logger. Useful for
confirming the physical-to-action mapping and debugging bindings.

Run:  python -m huion_keydial_mini.event_logger
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime

from .config import Config
from .input_translator import InputTranslator
from .input_events import EventType


def setup_clean_logging():
    logging.getLogger('evdev').setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


async def _run():
    from .evdev_source import EvdevSource, default_discover

    count = {"n": 0}

    async def on_event(ev):
        count["n"] += 1
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        action = "PRESS" if ev.event_type == EventType.KEY_PRESS else "RELEASE"
        print(f"[{ts}] #{count['n']:03d} {action:<7} {ev.key_code}", flush=True)

    if not default_discover():
        print("No Keydial device found. Is it connected and is the 70- udev "
              "rule installed (for event-node access)?", file=sys.stderr)
        return

    source = EvdevSource(on_event=on_event, translator=InputTranslator())
    await source.start()
    print("=== Keydial event monitor — press buttons / turn dial (Ctrl+C to stop) ===",
          flush=True)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await source.stop()


def main():
    parser = argparse.ArgumentParser(description="Live evdev monitor for the Keydial Mini")
    parser.add_argument('--config', '-c', default=None, help='Config file path (unused; reserved)')
    parser.parse_args()
    setup_clean_logging()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    main()
