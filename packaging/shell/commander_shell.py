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
            except ValueError:
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


def main():
    url = daemon_url()
    if not run_window(url):
        print("Falling back to the default browser: %s" % url)
        webbrowser.open(url)


if __name__ == "__main__":
    main()
