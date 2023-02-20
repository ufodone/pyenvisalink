import asyncio
import logging
import re

from mock_server import MockServer

CMD_KEYSTROKE = "key"
CMD_POLL = "00"
CMD_CHANGE_DEFAULT_PARTITION = "01"
CMD_DUMP_ZONE_TIMERS = "02"
CMD_KEYPRESS_TO_PARTITION = "03"

ERR_SUCCESS = "00"
ERR_CMD_IN_PROGRESS = "01"
ERR_UNKNOWN_CMD = "02"
ERR_SYNTAX = "03"
ERR_RECV_BUF_OVERFLOW = "04"
ERR_RECV_STATE_MACHINE_TIMEOUT = "05"

log = logging.getLogger(__name__)


class HoneywellServer(MockServer):
    def __init__(self, num_zones, num_partitions, password):
        super().__init__(num_zones, num_partitions, password)

        self._keypad_task = None
        self._keypad_zone_index = 0

    async def disconnected(self):
        if self._keypad_task:
            self._keypad_task.cancel()
            self._keypad_task = None

        await super().disconnected()

    async def hello(self):
        await self.send_response("Login:")

    async def process_command(self, line) -> bool:
        if not self._logged_in:
            return await self.login(line)

        cmd, data = self.decode_command(line)

        if cmd is None:
            # Invalid command received
            return False

        success = False
        if cmd == CMD_POLL:  # Poll
            success = await self.poll()
        elif cmd == CMD_CHANGE_DEFAULT_PARTITION:  # Change Default Partition
            success = await self.change_default_partition()
        elif cmd == CMD_DUMP_ZONE_TIMERS:  # Dump Zone Timers
            success = await self.dump_zone_timers()
        elif cmd == CMD_KEYPRESS_TO_PARTITION:  # Keypress to specific partition
            success = await self.handle_keystroke_sequence()
        else:
            log.info(f"Unhandled command ({cmd}); data: {data}")
            return False

        return success

    def decode_command(self, line) -> (str, str):
        m = re.search(r"\^(..),([^\$]*)\$", line)
        if m:
            cmd = m.group(1)
            data = None
            if m.lastindex == 2:
                data = m.group(2)
        else:
            # Keystroke
            cmd = CMD_KEYSTROKE
            data = line

        log.info(f"cmd='{cmd}' data='{data}'")
        return (cmd, data)

    def encode_command(self, cmd, data) -> str:
        return f"{cmd}{data}\r\n"

    async def send_command_response(self, cmd, error):
        await self.send_response(f"^{cmd},{error}$")

    async def send_server_data(self, cmd, data):
        await self.send_response(f"%{cmd},{data}$")

    async def send_response(self, response):
        log.info(f"send: {response}")
        await self.write_raw(f"{response}\r\n")

    async def dump_zone_timers(self) -> bool:
        await self.send_command_response(CMD_DUMP_ZONE_TIMERS, ERR_SUCCESS)

        await self.send_server_data("FF", self.encode_zone_timers())
        return True

    async def poll(self) -> bool:
        await self.send_command_response(CMD_POLL, ERR_SUCCESS)
        return True

    async def change_default_partition(self, data) -> bool:
        await self.send_command_response(CMD_CHANGE_DEFAULT_PARTITION, ERR_SUCCESS)
        return True

    async def login(self, data) -> bool:
        if data != self._password:
            log.error(f"Invalid password: {data}")
            await self.send_response("FAILED")
            return False

        self._logged_in = True
        await self.send_response("OK")

        ###
        #        self.send_response(f"OK\r\n%FF,{self.encode_zone_timers()}$\r\n")
        ####

        # Start task to send Virtual Keypad Updates
        self._keypad_task = asyncio.create_task(self.keypad_updater(), name="keypad_updater")
        return True

    async def handle_keystroke_sequence(self) -> bool:
        # TODO
        await self.send_command_response(CMD_KEYPRESS_TO_PARTITION, ERR_SUCCESS)
        return True

    def build_keypad_string(self, line1: str, line2: str) -> str:
        return f"{line1:<16}{line2:<16}"

    def build_keypad_zone_fault_string(self, zone: int) -> str:
        return self.build_keypad_string(f"FAULT {zone:02} Zone {zone}", " ")

    async def send_partition_state_update(self):
        # TODO: Only handles partition 1
        part_info = "01" if self.is_partition_ready(1) else "00"
        if self._num_partitions > 1:
            part_info += "00" * self._num_partitions
        await self.send_server_data("02", part_info)

    async def send_zone_state_update(self, start_zone: int):
        zone = start_zone - 1  # Adjust back to 0-indexed zone number
        faulted_zones = []
        for idx in range(self._num_zones):
            if self._zone_states[zone]["fault"]:
                faulted_zones.append(zone)
                if len(faulted_zones) == 4:
                    # Simulate the EVL only seeming to include 4 zones in the updates
                    break
            zone = (zone + 1) % self._num_zones

        zones = [0 for idx in range(int(self._num_zones / 8))]

        for zone in faulted_zones:
            byte = int(zone / 8)
            bit = zone % 8
            v = zones[byte] | (1 << bit)
            zones[byte] = v

        zone_info = ""
        for idx in zones:
            zone_info += f"{idx:02X}"

        await self.send_server_data("01", zone_info)

    async def set_zone_state(self, zone: int, faulted: bool):
        is_ready = self.is_partition_ready(1)

        await super().set_zone_state(zone, faulted)

        if is_ready != self.is_partition_ready(1):
            # Send a partition update if its state has changed
            await self.send_partition_state_update()

        await self.send_zone_state_update(zone)

        if faulted:
            await self.send_keypad_update_for_faulted_zone(zone)
            self._keypad_zone_index = 0
        elif self.is_partition_ready(1):
            self._keypad_zone_index = 0
            await self.send_server_data("00", "01,1C08,08,00,****DISARMED****  Ready to Arm  ")

    async def send_keypad_update_for_faulted_zone(self, zone: int):
        await self.send_server_data(
            "00", f"01,0008,{zone:02},00,{self.build_keypad_zone_fault_string(zone)}"
        )

    def get_next_faulted_zone(self) -> int:
        for idx in range(self._num_zones):
            zone = self._keypad_zone_index
            self._keypad_zone_index = (self._keypad_zone_index + 1) % self._num_zones
            if self._zone_states[zone]["fault"]:
                return zone
        return -1

    async def keypad_updater(self):
        while self._logged_in:
            if self.is_partition_ready(1):
                await self.send_server_data("00", "01,1C08,08,00,****DISARMED****  Ready to Arm  ")
            else:
                faulted_zone = self.get_next_faulted_zone()
                if faulted_zone >= 0:
                    await self.send_keypad_update_for_faulted_zone(faulted_zone + 1)

            await asyncio.sleep(5)
