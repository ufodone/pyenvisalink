import logging
import json
import re
import asyncio
from pyenvisalink import EnvisalinkClient
from pyenvisalink.dsc_envisalinkdefs import *

_LOGGER = logging.getLogger(__name__)

class DSCClient(EnvisalinkClient):
    """Represents a dsc alarm client."""

    def get_checksum(self, code, data):
        """part of each command includes a checksum.  Calculate."""
        return ("%02X" % sum(to_chars(code)+to_chars(data)))[-2:]

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
            code = int(rawInput[:3])
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

    def handle_login(self, data):
        """When the envisalink asks us for our password- send it."""
        self.send_command(evl_Commands['Login'], self._alarmPanel.password) 
        
    def handle_command_response(self, data):
        """Handle the envisalink's initial response to our commands."""
        _LOGGER.debug("DSC ack recieved.")

    def handle_command_response_error(self,data):
        """Handle the case where the DSC passes back a checksum failure."""
        _LOGGER.error("The previous command resulted in a checksum failure.")
			
    def handle_poll_response(self, data):
        """Handle the response to our keepalive messages."""
        self.handle_command_response(data)
