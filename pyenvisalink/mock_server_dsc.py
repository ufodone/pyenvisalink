import asyncio
import logging

from mock_server import MockServer

ZONE_STATUS_ALARM = "601"
ZONE_STATUS_ALARM_RESTORE = "602"
ZONE_STATUS_TAMPER = "603"
ZONE_STATUS_TAMPER_RESTORE = "604"
ZONE_STATUS_FAULT = "605"
ZONE_STATUS_FAULT_RESTORE = "606"
ZONE_STATUS_OPEN = "609"
ZONE_STATUS_RESTORED = "610"

PARTITION_STATE_READY = "650"
PARTITION_STATE_NOT_READY = "651"

log = logging.getLogger(__name__)


class DscServer(MockServer):
    def __init__(self, num_zones, num_partitions, password, alarm_code):
        super().__init__(num_zones, num_partitions, password, alarm_code)

        self._zone_status = []
        for zone in range(0, num_zones):
            self._zone_status.append(ZONE_STATUS_RESTORED)

        self._arm_modes = {
            "disarmed": -1,
            "away": 0,
            "stay": 1,
            "zero_entry_away": 2,
            "zero_entry_stay": 3,
        }
        self._arm_state = "disarmed"

    async def hello(self):
        await self.send_response(self.encode_command("505", "3"))

    async def process_command(self, line) -> bool:
        cmd, data = self.decode_command(line)

        if cmd is None:
            # Invalid command received
            return False

        success = False
        if cmd == "000":  # Poll
            success = await self.poll()
        elif cmd == "001":  # Status Report
            success = await self.status_report()
        elif cmd == "008":  # Dump Zone Timers
            success = await self.dump_zone_timers()
        elif cmd == "005":  # Network Login
            success = await self.login(data)
        elif cmd == "010":  # Set Time & Date
            success = await self.set_time_and_date()
        elif cmd == "020":  # Command Output Control
            success = await self.command_output_control()
        elif cmd == "030":  # Partition Arm Control
            success = await self.arm_away()
        elif cmd == "031":  # Partition Arm Control - Stay Arm
            success = await self.arm_stay()
        elif cmd == "032":  # Partition Arm Control - Zero Entry Delay
            success = await self.arm_max()
        elif cmd == "040":  # Partition Disarm Control
            success = await self.disarm()
        elif cmd == "060":  # Trigger Panic Alarm
            success = await self.trigger_panic_alarm()
        elif cmd == "071":  # Send Keystroke String
            success = await self.handle_keystroke_sequence()
        elif cmd == "200":  # Send Code
            success = await self.receive_code()
        else:
            log.info(f"Unhandled command ({cmd}); data: {data}")
            return False

        return success

    def get_checksum(self, code, data) -> str:
        checksum = 0
        for ch in code + data:
            checksum = checksum + ord(ch)
        return "%02X" % (checksum & 0xFF)

    def decode_command(self, line) -> (str, str):
        if len(line) < 5:
            return None

        cmd = line[:3]
        data = line[3:-2]
        checksum = line[-2:]
        log.info(f"cmd='{cmd}' data='{data}' checksum='{checksum}'")

        valid_checksum = self.get_checksum(cmd, data)
        if checksum != valid_checksum:
            log.error(f"Invalid checksum ({valid_checksum}) for command: '{line}'")
            return None

        return (cmd, data)

    def encode_command(self, cmd, data) -> str:
        checksum = self.get_checksum(cmd, data)
        return f"{cmd}{data}{checksum}\r\n"

    async def send_response(self, response):
        log.info(f"send: {response}")
        await self.write_raw(response)

    async def dump_zone_timers(self) -> bool:
        response = self.encode_command("500", "008")
        log.info(f"send: {response}")
        await self.send_response(response)

        response = self.encode_command("615", self.encode_zone_timers())
        await self.send_response(response)
        return True

    async def poll(self) -> bool:
        response = self.encode_command("500", "000")
        await self.send_response(response)
        return True

    async def status_report(self) -> bool:
        response = self.encode_command("500", "001")
        await self.send_response(response)

        for zone, status in enumerate(self._zone_status, start=1):
            await self.send_response(self.encode_command(status, "%03d" % zone))

        await self.send_response(self.encode_command("650", "1"))
        # self.send_response(self.encode_command("673", "2"))
        await self.send_response(self.encode_command("841", "1"))
        await self.send_response(self.encode_command("841", "2"))
        await self.send_response(self.encode_command("510", "81"))

        return True

    async def login(self, data) -> bool:
        response = self.encode_command("500", "005")

        if data != self._password:
            log.error(f"Invalid password: {data}")
            response += self.encode_command("505", "0")
            await self.send_response(response)
            return False

        response += self.encode_command("505", "1")

        await self.send_response(response)

        #    response = self.encode_zone_timers()
        #    self.send_response(response)

        return True

    async def set_time_and_date(self) -> bool:
        response = self.encode_command("500", "010")
        await self.send_response(response)
        return True

    async def arm_away(self) -> bool:
        # TODO
        response = self.encode_command("500", "030")
        await self.send_response(response)
        return True

    async def arm_max(self) -> bool:
        # TODO
        response = self.encode_command("500", "032")
        await self.send_response(response)
        return True

    async def entry_delay(self):
        await asyncio.sleep(5.0)
        response = self.encode_command("652", f"1{self._arm_modes['stay']}")
        await self.send_response(response)

    async def arm_stay(self) -> bool:
        response = self.encode_command("500", "031")
        await self.send_response(response)

        # Exit delay in progress
        response = self.encode_command("656", "1")  # Partition 1
        await self.send_response(response)

        asyncio.create_task(self.entry_delay())

        return True

    async def disarm(self) -> bool:
        response = self.encode_command("500", "040")
        await self.send_response(response)

        response = self.encode_command("510", "81")
        await self.send_response(response)

        response = self.encode_command("655", "1")
        await self.send_response(response)
        return True

    async def handle_keystroke_sequence(self) -> bool:
        # TODO
        response = self.encode_command("500", "071")
        await self.send_response(response)
        return True

    async def trigger_panic_alarm(self) -> bool:
        # TODO
        response = self.encode_command("500", "060")
        await self.send_response(response)
        return True

    async def receive_code(self) -> bool:
        # TODO
        response = self.encode_command("500", "200")
        await self.send_response(response)
        return True

    async def command_output_control(self) -> bool:
        # TODO
        response = self.encode_command("500", "020")
        await self.send_response(response)
        return True
