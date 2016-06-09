import logging
import json
import re
import asyncio
from pyenvisalink import EnvisalinkClient
from pyenvisalink.dsc_envisalinkdefs import *

_LOGGER = logging.getLogger(__name__)

class DSCClient(EnvisalinkClient):
    """Represents a dsc alarm client."""

    def to_chars(string):
        chars = []
        for char in string:
            chars.append(ord(char))
        return chars

    def get_checksum(self, code, data):
        """part of each command includes a checksum.  Calculate."""
        return ("%02X" % sum(self.to_chars(code)+self.to_chars(data)))[-2:]

    def send_command(self, code, data):
        """Send a command in the proper honeywell format."""
        to_send = code + data + self.get_checksum(code, data)
        self.send_data(to_send)

    def dump_zone_timers(self):
        """Send a command to dump out the zone timers."""
        self.send_command(evl_Commands['DumpZoneTimers'], '')

    @asyncio.coroutine        
    def keep_alive(self):
        """Send a keepalive command to reset it's watchdog timer."""
        while not self._shutdown:
            if self._loggedin:
                self.send_command(evl_Commands['KeepAlive'], '')
            yield from asyncio.sleep(self._alarmPanel.keepalive_interval)

    @asyncio.coroutine
    def periodic_zone_timer_dump(self):
        """Used to periodically get the zone timers to make sure our zones are updated."""
        while not self._shutdown:
            if self._loggedin:
                self.dump_zone_timers()
            yield from asyncio.sleep(self._alarmPanel.zone_timer_interval)

    def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        self.send_command(evl_Commands['ArmStay'], str(partitionNumber) + str(code))

    def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        self.send_command(evl_Commands['ArmAway'], str(partitionNumber) + str(code))

    def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        self.send_command(evl_Commands['ArmMax'], str(partitionNumber) + str(code))

    def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        self.send_command(evl_Commands['Disarm'], str(partitionNumber) + str(code))

    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        cmd = {}
        if rawInput != '':
            code = rawInput[:3]
            cmd['code'] = code
            cmd['data'] = rawInput[3:][:-2]
            
            try:
                #Interpret the login command further to see what our handler is.
                if evl_ResponseTypes[code]['handler'] == 'login':
                    if cmd['data'] == '3':
                      handler = 'login'
                    elif cmd['data'] == '2':
                      handler = 'login_timeout'
                    elif cmd['data'] == '1':
                      handler = 'login_success'
                    elif cmd['data'] == '0':
                      handler = 'login_failure'

                    cmd['handler'] = "handle_%s" % handler
                    cmd['callback'] = "callback_%s" % handler

                else:
                    cmd['handler'] = "handle_%s" % evl_ResponseTypes[code]['handler']
                    cmd['callback'] = "callback_%s" % evl_ResponseTypes[code]['handler']
            except KeyError:
                _LOGGER.warning(str.format('No handler defined in config for {0}, skipping...', code))
                
        return cmd

    def handle_login(self, code, data):
        """When the envisalink asks us for our password- send it."""
        self.send_command(evl_Commands['Login'], self._alarmPanel.password) 
        
    def handle_command_response(self, code, data):
        """Handle the envisalink's initial response to our commands."""
        _LOGGER.debug("DSC ack recieved.")

    def handle_command_response_error(self, code, data):
        """Handle the case where the DSC passes back a checksum failure."""
        _LOGGER.error("The previous command resulted in a checksum failure.")
			
    def handle_poll_response(self, code, data):
        """Handle the response to our keepalive messages."""
        self.handle_command_response(code, data)

    def handle_zone_state_change(self, code, data):
        """Handle when the envisalink sends us a zone change."""
        """Event 601-610."""
        parse = re.match('^[0-9]{4}$', data)
        if parse:
            partitionNumber = data[0]
            zoneNumber = int(data[1:3])
            self._alarmPanel.alarm_state['zone'][zoneNumber]['status'].update(evl_ResponseTypes[code]['status'])
            _LOGGER.debug(str.format("(zone {0}) state has updated: {1}", zoneNumber, json.dumps(evl_ResponseTypes[code]['status'])))
            return zoneNumber
        else:
            _LOGGER.error("Invalid data has been passed in the zone update.")

    def handle_partition_state_change(self, code, data):
        """Handle when the envisalink sends us a partition change."""
        """Event 650-674, 652 is an exception, because 2 bytes are passed for partition and zone type."""
        if code == '652':
            parse = re.match('^[0-9]{2}$', data)
            if parse:
                partitionNumber = data[0]
                armType = evl_ArmModes[data[1]]['name']
                self._alarmPanel.alarm_state['partition'][partitionNumber]['status']['alpha'] = armType
                _LOGGER.debug(str.format("(partition {0}) state has updated: {1}", partitionNumber, armType))
                return partitionNumber
            else:
                _LOGGER.error("Invalid data has been passed when arming the alarm.") 
        else:
            parse = re.match('^[0-9]$', data)
            if parse:
                partitionNumber = data[0]
                self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update(evl_ResponseTypes[code]['status'])
                _LOGGER.debug(str.format("(partition {0}) state has updated: {1}", partitionNumber, json.dumps(evl_ResponseTypes[code]['status'])))
                return partitionNumber
            else:
                _LOGGER.error("Invalid data has been passed in the parition update.")
