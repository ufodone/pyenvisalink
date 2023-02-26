import logging
import time

from alarm_state import AlarmState

log = logging.getLogger(__name__)


class MockServer:
    def __init__(self, num_zones, num_partitions, password, alarm_code):
        self._client_writer = None

        self._password = password
        self._alarm_code = alarm_code
        self._logged_in = False

        self._num_zones = num_zones
        self._num_partitions = num_partitions
        self._alarm_state = AlarmState.get_initial_alarm_state(num_zones, num_partitions)

        self._zone_states = [{"fault": False, "changed": 0.0} for idx in range(num_zones)]

    def connected(self, client_writer):
        self._client_writer = client_writer

    async def disconnected(self):
        # await asyncio.sleep(0.5)
        if self._client_writer:
            self._client_writer.close()
            await self._client_writer.wait_closed()

        self._client_writer = None
        self._logged_in = False

    async def hello(self):
        raise NotImplementedError()

    async def process_command(self, line) -> bool:
        raise NotImplementedError()

    async def disarm(self):
        raise NotImplementedError()

    async def arm_away(self):
        raise NotImplementedError()

    async def arm_stay(self):
        raise NotImplementedError()

    async def write_raw(self, data):
        if self._client_writer:
            self._client_writer.write(data.encode())
            await self._client_writer.drain()

    async def set_zone_state(self, zone: int, faulted: bool):
        self._zone_states[zone - 1].update({"fault": faulted, "changed": time.time()})

    def is_partition_ready(self, partition: int) -> bool:
        # TODO For now assume all zones belong to parition 1
        for status in self._zone_states:
            if status["fault"]:
                return False
        return True

    def zone_info(self) -> str:
        zones = ""
        for idx, faulted in enumerate(self._zone_states, start=1):
            zones += f"{idx:3}: {faulted}\n"

        return zones

    def encode_zone_timers(self) -> str:
        now = time.time()
        zone_ticks = []
        for zone in self._zone_states:
            if zone["fault"]:
                ticks = 0
            else:
                ticks = min(int((now - zone["changed"]) / 5), 0xFFFF)
            zone_ticks.append(ticks)

        timers = ""
        for ticks in zone_ticks:
            timers += f"{0xffff - ticks:04X}"
        return timers
