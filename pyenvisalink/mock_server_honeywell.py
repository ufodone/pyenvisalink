import asyncio
import logging
import re
import random

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

    def is_partition_ready(self, partition: int) -> bool:
        for zone in self._zone_status:
            if not zone:
                return False
        return True

    def decode_command(self, line) -> (str, str):
        m = re.search("\^(..),([^\$]*)\$", line)
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

    def encode_zone_timers(self) -> str:
        # return "74FD94FF0000000075C200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        return "0000FEFF0000000071CA0000FDFF000000000000000000000000000000000000ACFC00000000000092D00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

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

    async def keypad_updater(self):
        toggle = False
        while self._logged_in:
            # TODO: Hack to simulate zone faulting periodically
            if random.randint(1, 5) == 1:
                await self.send_server_data("00", "01,0008,07,00,FAULT 07 DEN    MOTION          ")
                await self.send_server_data("00", "01,000C,58,00,ARMED ***AWAY***May Exit Now  58")
            else:
                await self.send_server_data("00", "01,1C08,08,00,****DISARMED****  Ready to Arm  ")

            # Set zones to random states
            zone_info = ""
            HEX = "0123456789ABCDEF"
            if toggle:
                HEX = "F"
            else:
                HEX = "0"
            toggle = not toggle
            try:
                for i in range(0, int(self._num_zones / 4)):
                    zone_info += HEX[random.randrange(len(HEX))]
            except Exception as ex:
                print(ex)

            await self.send_server_data("01", zone_info)
            await asyncio.sleep(10)
