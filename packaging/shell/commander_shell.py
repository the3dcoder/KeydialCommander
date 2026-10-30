#!/usr/bin/env python3
"""Keydial Commander desktop shell — a GTK3 + WebKit2 window over the local UI.

Runs under the SYSTEM python3 (which provides the `gi` bindings + WebKit2-4.1);
the driver's venv does not have `gi`. Reads the daemon's port from
$XDG_RUNTIME_DIR/huion-keydial-mini/port (fallback 8137) and shows the SPA.

No tray icon — this host has no AppIndicator typelib. Window-only, as designed.
Fallback: if GTK/WebKit are unavailable, open the URL in the default browser.
"""
import os
import sys
import webbrowser
from pathlib import Path


def daemon_url() -> str:
    port = 8137
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        pf = Path(base) / "huion-keydial-mini" / "port"
        if pf.exists():
            try:
                port = int(pf.read_text().strip())
                if not 1 <= port <= 65535:
                    port = 8137
            except (OSError, ValueError):
                pass
    return "http://127.0.0.1:%d/" % port


def run_window(url: str) -> bool:
    """Try to open a GTK WebKit window. Returns False if unavailable."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, WebKit2
    except (ImportError, ValueError) as e:
        print("GTK/WebKit unavailable (%s)" % e, file=sys.stderr)
        return False

    win = Gtk.Window(title="Keydial Commander")
    win.set_default_size(1120, 740)
    win.connect("destroy", Gtk.main_quit)
    view = WebKit2.WebView()
    view.load_uri(url)
    win.add(view)
    win.show_all()
    Gtk.main()
    return True


def startup_error(message):
    print(message, file=sys.stderr)
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        if not Gtk.init_check()[0]:
            return
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE,
                                   text="Commander could not complete the service action")
        dialog.format_secondary_text(str(message))
        dialog.run()
        dialog.destroy()
    except (ImportError, ValueError):
        pass


def main():
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser(description=__doc__)
        action = parser.add_mutually_exclusive_group()
        action.add_argument('--start-service', action='store_true', help='Start remapping, then open the window')
        action.add_argument('--stop-service', action='store_true', help='Stop remapping and exit')
        args = parser.parse_args()
        if args.start_service or args.stop_service:
            from service_startup import StartupError, start_service, stop_service
            from importlib.metadata import version
            try:
                if args.stop_service:
                    stop_service()
                    return 0
                url = start_service(version('huion-keydial-mini-driver'))
            except StartupError as error:
                startup_error(str(error))
                return 1
            if not run_window(url):
                webbrowser.open(url)
            return 0
    url = daemon_url()
    if not run_window(url):
        print("Falling back to the default browser: %s" % url)
        webbrowser.open(url)


if __name__ == "__main__":
    sys.exit(main())
