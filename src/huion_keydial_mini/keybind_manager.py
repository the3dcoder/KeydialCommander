#!/usr/bin/env python3
"""Keybind manager for Huion Keydial Mini with runtime control via Unix socket."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .config import Config


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Legacy binding-type enum (kept for backward compatibility)."""
    KEYBOARD = "keyboard"


# Canonical action types + legacy alias
ACTION_TYPES = ("keystroke", "macro", "command", "profile_switch")
_TYPE_ALIASES = {"keyboard": "keystroke"}


@dataclass
class KeybindAction:
    """Represents a keybind action (keystroke / macro / command / profile_switch)."""
    type: Any = "keystroke"          # str; an EventType enum is accepted and normalized
    keys: Optional[List[str]] = None
    description: Optional[str] = None
    sticky: bool = False
    steps: Optional[List[Dict[str, Any]]] = None   # macro
    argv: Optional[List[str]] = None               # command
    profile: Optional[str] = None                  # profile_switch

    def __post_init__(self):
        t = self.type
        if isinstance(t, EventType):
            t = t.value
        self.type = _TYPE_ALIASES.get(str(t), str(t))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary. keys/sticky/description kept for CLI compatibility."""
        d: Dict[str, Any] = {
            'type': self.type,
            'keys': self.keys,
            'description': self.description,
            'sticky': self.sticky,
        }
        if self.steps is not None:
            d['steps'] = self.steps
        if self.argv is not None:
            d['argv'] = self.argv
        if self.profile is not None:
            d['profile'] = self.profile
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeybindAction':
        """Create from dictionary."""
        return cls(
            type=data.get('type', 'keystroke'),
            keys=data.get('keys'),
            description=data.get('description'),
            sticky=data.get('sticky', False),
            steps=data.get('steps'),
            argv=data.get('argv'),
            profile=data.get('profile'),
        )


class KeybindManager:
    """Manages in-memory keybind mappings with Unix socket control interface."""

    def __init__(self, config: Config, socket_path: Optional[str] = None,
                 profile_store=None, event_bus=None):
        self.config = config
        self.socket_path = socket_path or self._get_default_socket_path()
        self.profile_store = profile_store
        self.event_bus = event_bus
        self.keybind_map: Dict[str, KeybindAction] = {}
        self.server: Optional[asyncio.Server] = None
        if self.profile_store is not None:
            self.keybind_map = self.profile_store.load_bindings()
            logger.info("Loaded %d bindings from profile %r",
                        len(self.keybind_map), self.profile_store.get_active())
        else:
            self._load_initial_bindings()  # legacy in-memory mode

    def switch_profile(self, name: str) -> None:
        """Switch the active profile and reload the binding map."""
        if self.profile_store is None:
            raise RuntimeError("No profile store attached")
        self.profile_store.set_active(name)
        self.keybind_map = self.profile_store.load_bindings()
        if self.event_bus is not None:
            self.event_bus.publish({"type": "profile_changed", "name": name})
        logger.info("Switched to profile %r (%d bindings)", name, len(self.keybind_map))

    def reload_bindings(self) -> None:
        """Reload the live binding map from the active profile on disk."""
        if self.profile_store is not None:
            self.keybind_map = self.profile_store.load_bindings()
            self._publish_bindings_changed()

    def _publish_bindings_changed(self):
        if self.event_bus is not None and self.profile_store is not None:
            self.event_bus.publish({"type": "bindings_changed",
                                    "profile": self.profile_store.get_active()})

    def _get_default_socket_path(self) -> str:
        """Get default socket path for user-level service."""
        from . import ipc
        return ipc.socket_path()

    def _load_initial_bindings(self):
        """Load initial keybindings from config."""

        def handle_key_mapping(mappings: Dict[str, str], sticky: bool = False):
            for action_id, key in mappings.items():
                # Type validation: both key and value must be strings
                if not isinstance(action_id, str):
                    logger.warning(f"Config: Action ID must be a string, ignoring: {action_id}")
                    continue
                if not isinstance(key, str) or not key:
                    logger.warning(f"Config: Key mapping must be a non-empty string, ignoring: {action_id} -> {key}")
                    continue

                normalized_action_id = self._validate_and_normalize_action_id(action_id)
                if normalized_action_id:
                    self.keybind_map[normalized_action_id] = KeybindAction(
                        type=EventType.KEYBOARD,
                        keys=[k.strip() for k in key.split('+')],
                        description=f"{normalized_action_id} -> {key}",
                        sticky=sticky
                    )

        # Load key mappings
        handle_key_mapping(self.config.key_mappings)
        handle_key_mapping(self.config.sticky_key_mappings, sticky=True)

        # Load dial settings
        dial_settings = self.config.dial_settings
        if dial_settings.get('DIAL_CW'):
            self.keybind_map['DIAL_CW'] = KeybindAction(
                type=EventType.KEYBOARD,
                keys=[dial_settings['DIAL_CW']],
                description="Dial clockwise -> " + dial_settings['DIAL_CW']
            )

        if dial_settings.get('DIAL_CCW'):
            self.keybind_map['DIAL_CCW'] = KeybindAction(
                type=EventType.KEYBOARD,
                keys=[dial_settings['DIAL_CCW']],
                description="Dial counterclockwise -> " + dial_settings['DIAL_CCW']
            )

        if dial_settings.get('DIAL_CLICK'):
            self.keybind_map['DIAL_CLICK'] = KeybindAction(
                type=EventType.KEYBOARD,
                keys=[dial_settings['DIAL_CLICK']],
                description="Dial click -> " + dial_settings['DIAL_CLICK']
            )

        logger.info(f"Loaded {len(self.keybind_map)} initial keybindings")

    def _validate_and_normalize_action_id(self, action_id: str) -> Optional[str]:
        """Validate and normalize an action ID from config file."""
        valid_buttons = [
            'BUTTON_1', 'BUTTON_2', 'BUTTON_3', 'BUTTON_4',
            'BUTTON_5', 'BUTTON_6', 'BUTTON_7', 'BUTTON_8',
            'BUTTON_9', 'BUTTON_10', 'BUTTON_11', 'BUTTON_12',
            'BUTTON_13', 'BUTTON_14', 'BUTTON_15', 'BUTTON_16',
            'BUTTON_17', 'BUTTON_18'
        ]
        valid_dial_actions = ['DIAL_CW', 'DIAL_CCW', 'DIAL_CLICK']

        # Check if it's a valid action_id
        if action_id in valid_dial_actions:
            # Valid dial action
            return action_id
        elif action_id in valid_buttons:
            # Valid individual button
            return action_id
        elif '+' in action_id:
            # Check if it's a valid combo
            combo_buttons = [b.strip() for b in action_id.split('+')]

            if len(combo_buttons) < 2:
                logger.warning(f"Config: Button combinations must include at least 2 buttons, ignoring: {action_id}")
                return None

            # Check for duplicate buttons
            if len(combo_buttons) != len(set(combo_buttons)):
                logger.warning(f"Config: Button combinations cannot contain duplicate buttons, ignoring: {action_id}")
                return None

            for button in combo_buttons:
                if button not in valid_buttons:
                    logger.warning(f"Config: Invalid button name '{button}' in combination '{action_id}', ignoring")
                    return None

            # Normalize combo format (sorted for consistency)
            sorted_buttons = sorted(combo_buttons)
            return "+".join(sorted_buttons)
        else:
            logger.warning(f"Config: Invalid action ID '{action_id}', ignoring")
            return None

    async def start_socket_server(self):
        """Start the Unix socket server for control interface."""
        try:
            # Remove existing socket file if it exists
            socket_path = Path(self.socket_path)
            if socket_path.exists():
                socket_path.unlink()

            self.server = await asyncio.start_unix_server(
                self._handle_client,
                path=self.socket_path
            )
            import os
            os.chmod(self.socket_path, 0o600)

            logger.info(f"Started control socket server at {self.socket_path}")

        except Exception as e:
            logger.error(f"Failed to start socket server: {e}")
            raise

    async def stop_socket_server(self):
        """Stop the Unix socket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

            # Remove socket file
            socket_path = Path(self.socket_path)
            if socket_path.exists():
                socket_path.unlink()

            logger.info("Stopped control socket server")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a control-socket connection: newline-framed JSON, many commands."""
        from . import ipc
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ConnectionResetError, asyncio.IncompleteReadError):
                    break
                if not line:
                    break                     # client closed
                if len(line) > ipc.MAX_LINE:
                    await self._reply(writer, {'status': 'error',
                                               'message': 'Command too large'})
                    break
                try:
                    command = json.loads(line.decode('utf-8'))
                except json.JSONDecodeError:
                    await self._reply(writer, {'status': 'error',
                                               'message': 'Invalid JSON'})
                    continue
                response = await self._process_command(command)
                streamed = await self._maybe_stream(command, response, reader, writer)
                if streamed:
                    break                     # subscribe_events owns the connection
                await self._reply(writer, response)
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _reply(self, writer: asyncio.StreamWriter, response: Dict[str, Any]):
        from . import ipc
        response.setdefault('v', ipc.PROTOCOL_VERSION)
        writer.write((json.dumps(response) + '\n').encode('utf-8'))
        await writer.drain()

    async def _maybe_stream(self, command, response, reader, writer) -> bool:
        """subscribe_events switches this connection into a one-way event stream."""
        if command.get('command') != 'subscribe_events':
            return False
        if self.event_bus is None:
            await self._reply(writer, {'status': 'error',
                                       'message': 'Events unavailable'})
            return True
        await self._reply(writer, {'status': 'success', 'message': 'subscribed'})
        queue = self.event_bus.subscribe()
        # Watch for client EOF so the stream (and server shutdown) can't deadlock
        eof_task = asyncio.ensure_future(reader.read())
        get_task = None
        try:
            while True:
                get_task = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait(
                    {get_task, eof_task}, return_when=asyncio.FIRST_COMPLETED)
                if eof_task in done:
                    break
                event = get_task.result()
                writer.write((json.dumps(event) + '\n').encode('utf-8'))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            for task in (get_task, eof_task):
                if task is not None and not task.done():
                    task.cancel()
            self.event_bus.unsubscribe(queue)
        return True

    async def _process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Process a control command."""
        from .profile_store import ProfileError
        from .validation import ValidationError
        cmd_type = command.get('command')

        try:
            if cmd_type == 'get_bindings':
                return await self._cmd_get_bindings()
            elif cmd_type == 'set_binding':
                return await self._cmd_set_binding(command)
            elif cmd_type == 'remove_binding':
                return await self._cmd_remove_binding(command)
            elif cmd_type == 'clear_all':
                return await self._cmd_clear_all()
            elif cmd_type == 'list_actions':
                return await self._cmd_list_actions()
            elif cmd_type == 'subscribe_events':
                # Actual reply + streaming handled by _maybe_stream on this connection
                return {'status': 'success', 'message': 'subscribed'}
            elif cmd_type == 'list_profiles':
                if self.profile_store is None:
                    return {'status': 'error', 'message': 'Profiles unavailable'}
                return {'status': 'success',
                        'profiles': self.profile_store.list_profiles(),
                        'active': self.profile_store.get_active()}
            elif cmd_type == 'switch_profile':
                self.switch_profile(str(command.get('name')))
                return {'status': 'success', 'message': 'Switched profile'}
            elif cmd_type == 'create_profile':
                if self.profile_store is None:
                    return {'status': 'error', 'message': 'Profiles unavailable'}
                self.profile_store.create_profile(str(command.get('name')),
                                                  command.get('clone_from'))
                return {'status': 'success', 'message': 'Profile created'}
            elif cmd_type == 'delete_profile':
                if self.profile_store is None:
                    return {'status': 'error', 'message': 'Profiles unavailable'}
                self.profile_store.delete_profile(str(command.get('name')))
                return {'status': 'success', 'message': 'Profile deleted'}
            else:
                return {'status': 'error', 'message': f'Unknown command: {cmd_type}'}
        except (ProfileError, ValidationError, RuntimeError) as e:
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            logger.error(f"Error processing command {cmd_type}: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _cmd_get_bindings(self) -> Dict[str, Any]:
        """Get all current keybindings."""
        bindings = {}
        for action_id, action in self.keybind_map.items():
            bindings[action_id] = action.to_dict()

        return {
            'status': 'success',
            'bindings': bindings
        }

    async def _cmd_set_binding(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Set a keybinding (validated, persisted when a profile store is attached)."""
        from .validation import normalize_action_id, validate_keys, ValidationError
        action_id = command.get('action_id')
        action_data = command.get('action')

        if not action_id or not action_data:
            return {'status': 'error', 'message': 'Missing action_id or action'}

        try:
            action_id = normalize_action_id(str(action_id))
            action = KeybindAction.from_dict(action_data)
            action.keys = validate_keys(action.keys or [])
        except (ValidationError, KeyError, ValueError) as e:
            return {'status': 'error', 'message': f'Invalid binding: {e}'}

        self.keybind_map[action_id] = action
        if self.profile_store is not None:
            self.profile_store.save_binding(action_id, action)
        self._publish_bindings_changed()

        logger.info(f"Set binding {action_id}: {action.description}")
        return {
            'status': 'success',
            'message': f'Binding {action_id} updated'
        }

    async def _cmd_remove_binding(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Remove a keybinding."""
        action_id = command.get('action_id')

        if not action_id:
            return {'status': 'error', 'message': 'Missing action_id'}

        if action_id in self.keybind_map:
            del self.keybind_map[action_id]
            if self.profile_store is not None:
                self.profile_store.remove_binding(action_id)
            self._publish_bindings_changed()
            logger.info(f"Removed binding {action_id}")
            return {
                'status': 'success',
                'message': f'Binding {action_id} removed'
            }
        else:
            return {
                'status': 'error',
                'message': f'Binding {action_id} not found'
            }

    async def _cmd_clear_all(self) -> Dict[str, Any]:
        """Clear all keybindings."""
        count = len(self.keybind_map)
        self.keybind_map.clear()
        if self.profile_store is not None:
            self.profile_store.clear_bindings()
        self._publish_bindings_changed()
        logger.info(f"Cleared all {count} bindings")
        return {
            'status': 'success',
            'message': f'Cleared {count} bindings'
        }

    async def _cmd_list_actions(self) -> Dict[str, Any]:
        """List available action IDs."""
        return {
            'status': 'success',
            'actions': list(self.keybind_map.keys())
        }

    def get_action(self, action_id: str) -> Optional[KeybindAction]:
        """Get a keybind action by ID."""
        return self.keybind_map.get(action_id)

    def set_action(self, action_id: str, action: KeybindAction):
        """Set a keybind action."""
        self.keybind_map[action_id] = action
        logger.info(f"Set binding {action_id}: {action.description}")

    def remove_action(self, action_id: str) -> bool:
        """Remove a keybind action."""
        if action_id in self.keybind_map:
            del self.keybind_map[action_id]
            logger.info(f"Removed binding {action_id}")
            return True
        return False

    def get_all_actions(self) -> Dict[str, KeybindAction]:
        """Get all current keybind actions."""
        return self.keybind_map.copy()

    def has_combo_mapping(self, combo_id: str) -> bool:
        """Check if a combo mapping exists."""
        return combo_id in self.keybind_map

    def is_combo_action(self, action_id: str) -> bool:
        """Check if an action ID represents a combo (contains '+')."""
        return '+' in action_id

    def set_combo_action(self, buttons: List[str], keys: List[str], description: Optional[str] = None):
        """Set a combo action from a list of buttons and target keys."""
        # Generate combo ID by sorting button names
        sorted_buttons = sorted(buttons)
        combo_id = "+".join(sorted_buttons)

        action = KeybindAction(
            type=EventType.KEYBOARD,
            keys=keys,
            description=description or f"Combo {combo_id} -> {'+'.join(keys)}"
        )

        self.set_action(combo_id, action)
        return combo_id

    def get_combo_mappings(self) -> Dict[str, KeybindAction]:
        """Get all combo mappings (action IDs containing '+')."""
        return {
            action_id: action
            for action_id, action in self.keybind_map.items()
            if self.is_combo_action(action_id)
        }

    def get_individual_mappings(self) -> Dict[str, KeybindAction]:
        """Get all individual button mappings (action IDs not containing '+')."""
        return {
            action_id: action
            for action_id, action in self.keybind_map.items()
            if not self.is_combo_action(action_id)
        }


# Client-side functions for keydialctl
async def send_command(socket_path: str, command: Dict[str, Any],
                       timeout: float = 5.0) -> Dict[str, Any]:
    """Send one framed command; always returns a response dict, never raises."""
    try:
        async def _do():
            reader, writer = await asyncio.open_unix_connection(socket_path)
            try:
                writer.write((json.dumps(command) + '\n').encode('utf-8'))
                await writer.drain()
                line = await reader.readline()
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            if not line:
                return {'status': 'error', 'message': 'No response from service'}
            return json.loads(line.decode('utf-8'))
        return await asyncio.wait_for(_do(), timeout=timeout)
    except asyncio.TimeoutError:
        return {'status': 'error', 'message': 'Timeout waiting for service (%.1fs)' % timeout}
    except FileNotFoundError:
        return {'status': 'error', 'message': 'Service not running (socket not found)'}
    except ConnectionRefusedError:
        return {'status': 'error', 'message': 'Service not running (connection refused)'}
    except json.JSONDecodeError as e:
        return {'status': 'error', 'message': f'Invalid response from service: {e}'}
    except Exception as e:
        return {'status': 'error', 'message': f'Communication error: {e}'}
