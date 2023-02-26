import asyncio
import logging
import re

from honeywell_envisalinkdefs import IconLED_Bitfield
from mock_server import MockServer

ARM_DELAY = 5

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
    def __init__(self, num_zones, num_partitions, password, alarm_code):
        super().__init__(num_zones, num_partitions, password, alarm_code)

        self._keypad_task = None
        self._keypad_zone_index = 0
        self._keystroke_buffers = []
        for partition in range(num_partitions):
            self._keystroke_buffers.append("")

        self._keystroke_cmds = {
            f"{alarm_code}1": self.disarm,
            f"{alarm_code}2": self.arm_away,
            f"{alarm_code}3": self.arm_stay,
            f"{alarm_code}4": self.arm_max,
            f"{alarm_code}7": self.arm_night,
            f"{alarm_code}33": self.arm_night,
            f"{alarm_code}A": self.panic_fire,
            f"{alarm_code}B": self.panic_ambulance,
            f"{alarm_code}C": self.panic_police,
        }

        self._led_state = IconLED_Bitfield()
        self._led_state.alarm = 0
        self._led_state.alarm_in_memory = 0
        self._led_state.armed_away = 0
        self._led_state.ac_present = 1
        self._led_state.bypass = 0
        self._led_state.chime = 0
        self._led_state.not_used1 = 0
        self._led_state.armed_zero_entry_delay = 0
        self._led_state.alarm_fire_zone = 0
        self._led_state.system_trouble = 0
        self._led_state.not_used2 = 1
        self._led_state.not_used3 = 1
        self._led_state.ready = 1
        self._led_state.fire = 0
        self._led_state.low_battery = 0
        self._led_state.armed_stay = 0

        self._arm_countdown = 0
        self._keypad_task_event = asyncio.Event()

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
            success = await self.handle_keystroke_sequence(data)
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

    async def handle_keystroke_sequence(self, data) -> bool:
        await self.send_command_response(CMD_KEYPRESS_TO_PARTITION, ERR_SUCCESS)

        data_arr = data.split(",")
        partition = int(data_arr[0])
        key = data_arr[1]
        self._keystroke_buffers[partition] += key

        action = self._keystroke_cmds.get(self._keystroke_buffers[partition])
        if action:
            await action()
            self._keystroke_buffers[partition] = ""

        return True

    def build_keypad_string(self, line1: str, line2: str) -> str:
        return f"{line1:<16}{line2:<16}"

    def build_keypad_zone_fault_string(self, zone: int) -> str:
        return self.build_keypad_string(f"FAULT {zone:02} Zone {zone}", " ")

    async def send_partition_state_update(self):
        # TODO: Only handles partition 1
        part_info = "01" if self._led_state.ready else "00"
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
        await super().set_zone_state(zone, faulted)

        is_ready = self.is_partition_ready(1)
        if self._led_state.ready != is_ready:
            self._led_state.ready = is_ready
            if is_ready:
                self._led_state.not_used2 = 1
                self._led_state.not_used3 = 1
            else:
                self._led_state.not_used2 = 0
                self._led_state.not_used3 = 0

            # Send a partition update if its state has changed
            await self.send_partition_state_update()

        await self.send_zone_state_update(zone)

        if faulted:
            await self.send_keypad_update_for_faulted_zone(zone)
            self._keypad_zone_index = 0
        elif self._led_state.ready:
            self._keypad_zone_index = 0
            await self.send_server_data(
                "00", f"01,{self._led_state},08,00,****DISARMED****  Ready to Arm  "
            )

    async def send_keypad_update_for_faulted_zone(self, zone: int):
        await self.send_server_data(
            "00", f"01,{self._led_state},{zone:02},00,{self.build_keypad_zone_fault_string(zone)}"
        )

    def get_next_faulted_zone(self) -> int:
        for idx in range(self._num_zones):
            zone = self._keypad_zone_index
            self._keypad_zone_index = (self._keypad_zone_index + 1) % self._num_zones
            if self._zone_states[zone]["fault"]:
                return zone
        return -1

    def get_armed_message(self) -> str:
        if self._led_state.armed_stay:
            return "ARMED ***STAY***"
        if self._led_state.armed_away:
            return "ARMED ***AWAY***"
        return "***UNKN***"

    def get_arming_message(self) -> str:
        return f"{self.get_armed_message()}May Exit Now {self._arm_countdown:03}"

    async def keypad_updater(self):
        while self._logged_in:
            if self._led_state.ready:
                await self.send_server_data(
                    "00", f"01,{self._led_state},08,00,****DISARMED****  Ready to Arm  "
                )
            elif self._arm_countdown > 0:
                await self.send_server_data(
                    "00",
                    (
                        f"01,{self._led_state},{self._arm_countdown:02},00,"
                        f"{self.get_arming_message()}"
                    ),
                )

            elif (
                self._led_state.armed_away
                or self._led_state.armed_stay
                or self._led_state.armed_zero_entry_delay
            ):
                await self.send_server_data(
                    "00", f"01,{self._led_state},08,00,{self.get_armed_message()}                "
                )
            else:
                faulted_zone = self.get_next_faulted_zone()
                if faulted_zone >= 0:
                    await self.send_keypad_update_for_faulted_zone(faulted_zone + 1)

            delay = 5
            if self._arm_countdown > 0:
                self._arm_countdown -= 1
                delay = 1
                if self._arm_countdown == 0:
                    self._led_state.not_used2 = 1
                    self._led_state.not_used3 = 1
            try:
                await asyncio.wait_for(self._keypad_task_event.wait(), timeout=delay)
                self._keypad_task_event.clear()
            except asyncio.exceptions.TimeoutError:
                pass

    async def arm_stay(self):
        log.info("arm_stay")
        self._arm_countdown = ARM_DELAY
        self._led_state.ready = 0
        self._led_state.armed_stay = 1
        self._led_state.not_used2 = 0
        self._led_state.not_used3 = 0
        self._keypad_task_event.set()
        return True

    async def arm_away(self):
        log.info("arm_away")
        self._arm_countdown = ARM_DELAY
        self._led_state.ready = 0
        self._led_state.armed_away = 1
        self._led_state.not_used2 = 0
        self._led_state.not_used3 = 0
        self._keypad_task_event.set()
        return True

    async def arm_max(self):
        # TODO
        return True

    async def arm_night(self):
        # TODO
        return True

    async def disarm(self):
        self._led_state.ready = 1
        self._led_state.armed_away = 0
        self._led_state.armed_stay = 0
        self._led_state.not_used2 = 1
        self._led_state.not_used3 = 1
        self._keypad_task_event.set()
        return True

    async def panic_fire(self):
        # TODO
        return True

    async def panic_ambulance(self):
        # TODO
        return True

    async def panic_police(self):
        # TODO
        return True
