import logging

from mock_server_honeywell import ERR_SUCCESS, HoneywellServer

ARM_DELAY = 5

CMD_BYPASS_ZONE = "04"
CMD_UNBYPASS_ZONE = "05"
CMD_STAY_ARM = "08"
CMD_AWAY_ARM = "09"
CMD_INITIAL_STATE_DUMP = "0C"
CMD_HOST_INFO = "0D"
CMD_SET_DOOR_CHIME = "10"
CMD_PANIC_ALARM = "11"
CMD_DISARM = "12"

TPI_CMD_ZONE_BYPASS_STATE = "04"
TPI_CMD_HOST_INFO = "05"

log = logging.getLogger(__name__)


class UnoServer(HoneywellServer):
    def __init__(self, num_zones, num_partitions, password, alarm_code):
        super().__init__(num_zones, num_partitions, password, alarm_code)
        self._include_all_zones_in_update = True

    async def process_command(self, line) -> bool:
        if not self._logged_in:
            return await self.login(line)

        cmd, data = self.decode_command(line)

        if cmd is None:
            # Invalid command received
            return False

        success = False
        if cmd == CMD_BYPASS_ZONE:
            success = await self.bypass_zone(data)
        elif cmd == CMD_UNBYPASS_ZONE:
            success = await self.unbypass_zone(data)
        elif cmd == CMD_STAY_ARM:
            success = await self.stay_arm()
        elif cmd == CMD_AWAY_ARM:
            success = await self.away_arm()
        elif cmd == CMD_INITIAL_STATE_DUMP:
            success = await self.initial_state_dump()
        elif cmd == CMD_HOST_INFO:
            success = await self.host_info()
        elif cmd == CMD_SET_DOOR_CHIME:
            success = await self.set_door_chime()
        elif cmd == CMD_PANIC_ALARM:
            success = await self.panic_alarm()
        elif cmd == CMD_DISARM:
            success = await self.disarm()
        else:
            return await super().process_command(line)

        return success

    async def send_zone_bypass_state_update(self):
        bypassed_zones = []
        for idx in range(self._num_zones):
            if self._zone_states[idx]["bypassed"]:
                bypassed_zones.append(idx)

        zones = [0 for idx in range(int(self._num_zones / 8))]

        for zone in bypassed_zones:
            byte = int(zone / 8)
            bit = zone % 8
            v = zones[byte] | (1 << bit)
            zones[byte] = v

        zone_info = ""
        for idx in zones:
            zone_info += f"{idx:02X}"

        await self.send_server_data(TPI_CMD_ZONE_BYPASS_STATE, zone_info)

    async def bypass_zone(self, data) -> bool:
        log.info("bypass_zone")
        zone = int(data) - 1  # Zero-based
        self._zone_states[zone]["bypassed"] = True
        await self.send_command_response(CMD_BYPASS_ZONE, ERR_SUCCESS)
        await self.send_zone_bypass_state_update()
        return True

    async def unbypass_zone(self, data) -> bool:
        log.info("unbypass_zone")
        zone = int(data) - 1  # Zero-based
        self._zone_states[zone]["bypassed"] = False
        await self.send_command_response(CMD_UNBYPASS_ZONE, ERR_SUCCESS)
        await self.send_zone_bypass_state_update()
        return True

    async def stay_arm(self) -> bool:
        log.info("stay_arm")
        await super().arm_stay()
        await self.send_command_response(CMD_STAY_ARM, ERR_SUCCESS)
        return True

    async def away_arm(self) -> bool:
        log.info("away_arm")
        await super().arm_away()
        await self.send_command_response(CMD_AWAY_ARM, ERR_SUCCESS)
        return True

    async def initial_state_dump(self) -> bool:
        log.info("initial_state_dump")
        await self.send_command_response(CMD_INITIAL_STATE_DUMP, ERR_SUCCESS)
        await self.send_partition_state_update()
        await self.send_zone_state_update(1)
        await self.send_zone_bypass_state_update()
        return True

    async def host_info(self) -> bool:
        log.info("host_info")
        await self.send_command_response(CMD_HOST_INFO, ERR_SUCCESS)
        await self.send_server_data(TPI_CMD_HOST_INFO, "010203040506,UNO,1.2.3.4")
        return True

    async def set_door_chime(self) -> bool:
        # TODO
        log.info("set_door_chime")
        await self.send_command_response(CMD_SET_DOOR_CHIME, ERR_SUCCESS)
        return True

    async def panic_alarm(self) -> bool:
        # TODO
        log.info("panic_alarm")
        await self.send_command_response(CMD_PANIC_ALARM, ERR_SUCCESS)
        return True

    async def disarm(self) -> bool:
        log.info("disarm")
        await super().disarm()
        await self.send_command_response(CMD_DISARM, ERR_SUCCESS)
        return True
