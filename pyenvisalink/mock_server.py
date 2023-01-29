import asyncio
import logging
from alarm_state import AlarmState
log = logging.getLogger(__name__)

class MockServer:

    def __init__(self, num_zones, num_partitions, password):
        self._client_writer = None

        self._password = password
        self._logged_in = False

        self._num_zones = num_zones
        self._num_partitions = num_partitions
        self._alarm_state = AlarmState.get_initial_alarm_state(num_zones, num_partitions)

    def connected(self, client_writer):
        self._client_writer = client_writer

    async def disconnected(self):
        #await asyncio.sleep(0.5)
        if self._client_writer:
            self._client_writer.close()
            await self._client_writer.wait_closed()

        self._client_writer = None
        self._logged_in = False

    async def hello(self):
        raise NotImplementedError()

    async def process_command(self, line) -> bool:
        raise NotImplementedError()

    async def write_raw(self, data):
        self._client_writer.write(data.encode())
        await self._client_writer.drain()
