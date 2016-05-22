import logging
import json
import re
import asyncio
from pyenvisalink import EnvisalinkClient
from pyenvisalink.honeywell_envisalinkdefs import *

_LOGGER = logging.getLogger(__name__)

class HoneywellClient(EnvisalinkClient):
    """Represents a honeywell alarm client."""

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

    def send_command(self, code, data):
        """Send a command in the proper honeywell format."""
        to_send = '^' + code + ',' + data + '$'
        self.send_data(to_send)

    def dump_zone_timers(self):
        """Send a command to dump out the zone timers."""
        self.send_command(evl_Commands['DumpZoneTimers'], '')

    def keypresses_to_partition(self, partitionNumber, keypresses):
        """Send keypresses to a particular partition."""
        for char in keypresses:
            self.send_command(evl_Commands['PartitionKeypress'], str.format("{0},{1}", partitionNumber, char))

    def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        self.keypresses_to_partition(partitionNumber, code + '3')

    def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        self.keypresses_to_partition(partitionNumber, code + '2')

    def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        self.keypresses_to_partition(partitionNumber, code + '4')

    def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        self.keypresses_to_partition(partitionNumber, code + '1')

    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        cmd = {}
        parse = re.match('([%\^].+)\$', rawInput)
        if parse and parse.group(1):
            # keep first sentinel char to tell difference between tpi and
            # Envisalink command responses.  Drop the trailing $ sentinel.
            inputList = parse.group(1).split(',')
            code = inputList[0]
            cmd['data'] = ','.join(inputList[1:])
        elif not self._loggedin:
            # assume it is login info
            code = rawInput
            cmd['data'] = ''
        else:
            _LOGGER.error("Unrecognized data recieved from the envisalink. Ignoring.")    

        _LOGGER.debug(str.format("Code:{0} Data:{1}", code, cmd['data']))
        try:
            cmd['handler'] = "handle_%s" % evl_ResponseTypes[code]['handler']
            cmd['callback'] = "callback_%s" % evl_ResponseTypes[code]['handler']
        except KeyError:
            _LOGGER.warning(str.format('No handler defined in config for {0}, skipping...', code))
                
        return cmd

    def convertZoneDump(self, theString):
        """Interpret the zone dump result, and convert to readable times."""
        returnItems = []
        zoneNumber = 1
        # every four characters
        inputItems = re.findall('....', theString)
        for inputItem in inputItems:
            # Swap the couples of every four bytes (little endian to big endian)
            swapedBytes = []
            swapedBytes.insert(0, inputItem[0:2])
            swapedBytes.insert(0, inputItem[2:4])

            # add swapped set of four bytes to our return items, converting from hex to int
            itemHexString = ''.join(swapedBytes)
            itemInt = int(itemHexString, 16)

            # each value is a timer for a zone that ticks down every five seconds from maxint
            MAXINT = 65536
            itemTicks = MAXINT - itemInt
            itemSeconds = itemTicks * 5

            status = ''
            #The envisalink never seems to report back exactly 0 seconds for an open zone.
            #it always seems to be 10-15 seconds.  So anything below 30 seconds will be open.
            #this will of course be augmented with zone/partition events.
            if itemSeconds < 30:
                status = 'open'
            else:
                status = 'closed'

            returnItems.append({'zone': zoneNumber, 'status': status, 'seconds': itemSeconds})
            zoneNumber += 1
        return returnItems

    def handle_login(self, data):
        """When the envisalink asks us for our password- send it."""
        self.send_data(self._alarmPanel.password) 
        
    def handle_command_response(self, data):
        """Handle the envisalink's initial response to our commands."""
        responseString = evl_TPI_Response_Codes[data]
        _LOGGER.debug("Envisalink response: " + responseString)
        if data != '00':
            logging.error("error sending command to envisalink.  Response was: " + responseString)
			
    def handle_poll_response(self, data):
        """Handle the response to our keepalive messages."""
        self.handle_command_response(data)
        
    def handle_keypad_update(self, data):
        """Handle the response to when the envisalink sends keypad updates our way."""
        dataList = data.split(',')
        # make sure data is in format we expect, current TPI seems to send bad data every so ofen
        #TODO: Make this a regex...
        if len(dataList) != 5 or "%" in data:
            _LOGGER.error("Data format invalid from Envisalink, ignoring...")
            return

        partitionNumber = int(dataList[0])
        flags = IconLED_Flags()
        flags.asShort = int(dataList[1], 16)
        beep = evl_Virtual_Keypad_How_To_Beep.get(dataList[3], 'unknown')
        alpha = dataList[4]
        _LOGGER.debug("Updating our local alarm state...")
        self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update({'alarm': bool(flags.alarm), 'alarm_in_memory': bool(flags.alarm_in_memory), 'armed_away': bool(flags.armed_away),
                                                                   'ac_present': bool(flags.ac_present), 'armed_bypass': bool(flags.bypass), 'chime': bool(flags.chime),
                                                                   'armed_zero_entry_delay': bool(flags.armed_zero_entry_delay), 'alarm_fire_zone': bool(flags.alarm_fire_zone),
                                                                   'trouble': bool(flags.system_trouble), 'ready': bool(flags.ready), 'fire': bool(flags.fire),
                                                                   'armed_stay': bool(flags.armed_stay),
                                                                   'alpha': alpha,
                                                                   'beep': beep,
                                                                   })
        _LOGGER.debug(json.dumps(self._alarmPanel.alarm_state['partition'][partitionNumber]['status']))

    def handle_zone_state_change(self, data):
        """Handle when the envisalink sends us a zone change."""
        # Envisalink TPI is inconsistent at generating these
        bigEndianHexString = ''
        # every four characters
        inputItems = re.findall('....', data)
        for inputItem in inputItems:
            # Swap the couples of every four bytes
            # (little endian to big endian)
            swapedBytes = []
            swapedBytes.insert(0, inputItem[0:2])
            swapedBytes.insert(0, inputItem[2:4])

            # add swapped set of four bytes to our return items,
            # converting from hex to int
            bigEndianHexString += ''.join(swapedBytes)

        # convert hex string to 64 bit bitstring TODO: THIS IS 128 for evl4
        if self._alarmPanel.envisalink_version < 4:
            bitfieldString = str(bin(int(bigEndianHexString, 16))[2:].zfill(64))
        else:
            bitfieldString = str(bin(int(bigEndianHexString, 16))[2:].zfill(128))

        # reverse every 16 bits so "lowest" zone is on the left
        zonefieldString = ''
        inputItems = re.findall('.' * 16, bitfieldString)

        for inputItem in inputItems:
            zonefieldString += inputItem[::-1]

        for zoneNumber, zoneBit in enumerate(zonefieldString, start=1):
                self._alarmPanel.alarm_state['zone'][zoneNumber]['status'].update({'open': zoneBit == '1', 'fault': zoneBit == '1'})
                if zoneBit == '1':
                    self._alarmPanel.alarm_state['zone'][zoneNumber]['last_fault'] = 0

                _LOGGER.debug("(zone %i) is %s", zoneNumber, "Open/Faulted" if zoneBit == '1' else "Closed/Not Faulted")

    def handle_partition_state_change(self, data):
        """Handle when the envisalink sends us a partition change."""
        for currentIndex in range(0, 8):
            partitionStateCode = data[currentIndex * 2:(currentIndex * 2) + 2]
            partitionState = evl_Partition_Status_Codes[str(partitionStateCode)]
            partitionNumber = currentIndex + 1
            previouslyArmed = self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].get('armed', False)
            armed = partitionState['name'] in ('ARMED_STAY', 'ARMED_AWAY', 'ARMED_MAX')
            self._alarmPanel.alarm_state.update({'arm': not armed, 'disarm': armed, 'cancel': bool(partitionState['name'] == 'EXIT_ENTRY_DELAY')})
            self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update({'exit_delay': bool(partitionState['name'] == 'EXIT_ENTRY_DELAY' and not previouslyArmed),
                                                                           'entry_delay': bool(partitionState['name'] == 'EXIT_ENTRY_DELAY' and previouslyArmed),
                                                                           'armed': armed,
                                                                           'ready': bool(partitionState['name'] == 'READY' or partitionState['name'] == 'READY_BYPASS')})

            if partitionState['name'] == 'NOT_READY': self._alarmPanel.alarm_state['partition'][partitionNumber]['status'].update({'ready': False})
            _LOGGER.debug('Parition ' + str(partitionNumber) + ' is in state ' + partitionState['name'])
            _LOGGER.debug(json.dumps(self._alarmPanel.alarm_state['partition'][partitionNumber]['status']))

    def handle_realtime_cid_event(self, data):
        """Handle when the envisalink sends us an alarm arm/disarm/trigger."""
        eventTypeInt = int(data[0])
        eventType = evl_CID_Qualifiers[eventTypeInt]
        cidEventInt = int(data[1:4])
        cidEvent = evl_CID_Events[cidEventInt]
        partition = data[4:6]
        zoneOrUser = int(data[6:9])

        _LOGGER.debug('Event Type is ' + eventType)
        _LOGGER.debug('CID Type is ' + cidEvent['type'])
        _LOGGER.debug('CID Description is ' + cidEvent['label'])
        _LOGGER.debug('Partition is ' + partition)
        _LOGGER.debug(cidEvent['type'] + ' value is ' + str(zoneOrUser))
        
        return cidEvent

    def handle_zone_timer_dump(self, data):
        """Handle the zone timer data."""
        zoneInfoArray = self.convertZoneDump(data)
        for zoneNumber, zoneInfo in enumerate(zoneInfoArray, start=1):
            self._alarmPanel.alarm_state['zone'][zoneNumber]['status'].update({'open': zoneInfo['status'] == 'open', 'fault': zoneInfo['status'] == 'open'})
            self._alarmPanel.alarm_state['zone'][zoneNumber]['last_fault'] = zoneInfo['seconds']
            _LOGGER.debug("(zone %i) %s", zoneNumber, zoneInfo['status'])
