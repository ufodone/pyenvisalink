from envisalink_base_client import EnvisalinkClient
from envisalinkdefs import *
import logging
import json

class HoneywellClient(EnvisalinkClient):
        
    def keep_alive(self):
        """Send a keepalive command to reset it's watchdog timer."""
        if self._loggedin:
            self.send_command(evl_Commands['KeepAlive'], '')
            
    def send_command(self, code, data):
        to_send = '^' + code + ',' + data + '$'
        self.send_data(to_send)
        
    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        cmd = {}
        if rawInput[0] in ("%", "^"):
            # keep first sentinel char to tell difference between tpi and
            # Envisalink command responses.  Drop the trailing $ sentinel.
            inputList = rawInput[0:-1].split(',')
            code = inputList[0]
            cmd['data'] = ','.join(inputList[1:])
        else:
            # assume it is login info
            code = rawInput
            cmd['data'] = ''
            
        try:
            cmd['handler'] = "handle_%s" % evl_ResponseTypes[code]['handler']
            cmd['callback'] = "callback_%s" % evl_ResponseTypes[code]['handler']
        except KeyError:
            logging.warning(str.format('No handler defined in config for {0}, skipping...', code))
                
        return cmd
        
    def handle_command_response(self, code):
        responseString = evl_TPI_Response_Codes[code]
        logging.debug("Envisalink response: " + responseString)
        if code != '00':
            logging.error("error sending command to envisalink.  Response was: " + responseString)
            self.logout()
			
    def handle_poll_response(self, data):
        self.handle_command_response(data)
        
    def handle_keypad_update(self, data):
        dataList = data.split(',')
        # make sure data is in format we expect, current TPI seems to send bad data every so ofen
        #TODO: Make this a regex...
        if len(dataList) != 5 or "%" in data:
            logging.error("Data format invalid from Envisalink, ignoring...")
            return

        partitionNumber = int(dataList[0])
        flags = IconLED_Flags()
        flags.asShort = int(dataList[1], 16)
        beep = evl_Virtual_Keypad_How_To_Beep.get(dataList[3], 'unknown')
        alpha = dataList[4]
        logging.debug("Updating our local alarm state...")
        self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update({'alarm': bool(flags.alarm), 'alarm_in_memory': bool(flags.alarm_in_memory), 'armed_away': bool(flags.armed_away),
                                                                   'ac_present': bool(flags.ac_present), 'armed_bypass': bool(flags.bypass), 'chime': bool(flags.chime),
                                                                   'armed_zero_entry_delay': bool(flags.armed_zero_entry_delay), 'alarm_fire_zone': bool(flags.alarm_fire_zone),
                                                                   'trouble': bool(flags.system_trouble), 'ready': bool(flags.ready), 'fire': bool(flags.fire),
                                                                   'armed_stay': bool(flags.armed_stay),
                                                                   'alpha': alpha,
                                                                   'beep': beep,
                                                                   })
        logging.debug(json.dumps(self._alarmPanel.alarm_state['partition'][partitionNumber]['status']))