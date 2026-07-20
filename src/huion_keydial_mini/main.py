"""Main entry point for the Huion Keydial Mini driver."""

import asyncio
import logging
import signal
import sys
from typing import Optional

import click

from .device import HuionKeydialMini
from .config import Config


logger = logging.getLogger(__name__)


class DriverManager:
    """Manages the driver lifecycle."""

    def __init__(self, config: Config):
        self.config = config
        self.device: Optional[HuionKeydialMini] = None
        self._shutdown = asyncio.Event()

    async def start(self):
        """Start the driver."""
        logger.info("Starting Huion Keydial Mini driver...")

        try:
            # Initialize the device
            self.device = HuionKeydialMini(self.config)

            # Set up signal handlers
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGINT, signal.SIGTERM]:
                loop.add_signal_handler(sig, self._signal_handler)

            # Start the device
            await self.device.start()

            logger.info("Driver started successfully")

            # Wait until a shutdown signal arrives (no polling)
            await self._shutdown.wait()

        except Exception as e:
            logger.error(f"Failed to start driver: {e}")
            raise
        finally:
            await self.stop()

    def _signal_handler(self):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._shutdown.set()

    async def stop(self):
        """Stop the driver."""
        logger.info("Stopping driver...")

        if self.device:
            await self.device.stop()
            self.device = None

        logger.info("Driver stopped")


@click.command()
@click.option('--config', '-c',
              type=click.Path(exists=True),
              help='Path to configuration file')
@click.option('--device-address', '-d',
              help='Bluetooth MAC address of the device')
@click.option('--log-level', '-l',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              default='INFO',
              help='Set the logging level')
def main(config: Optional[str], device_address: Optional[str], log_level: str):
    """Huion Keydial Mini driver main entry point."""

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Load configuration
        app_config = Config.load(config, device_address)

        # Start the driver
        manager = DriverManager(app_config)
        asyncio.run(manager.start())

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Driver failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
