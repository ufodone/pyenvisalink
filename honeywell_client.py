import logging
import json
import re
import asyncio
from envisalink_base_client import EnvisalinkClient
from envisalinkdefs import *

class HoneywellClient(EnvisalinkClient):

    @asyncio.coroutine        
    def keep_alive(self):
        """Send a keepalive command to reset it's watchdog timer."""
        while True:
            if self._loggedin:
                self.send_command(evl_Commands['KeepAlive'], '')
            yield from asyncio.sleep(self._alarmPanel.keepalive_interval)
            
    def send_command(self, code, data):
        to_send = '^' + code + ',' + data + '$'
        self.send_data(to_send)

    def dump_zone_timers(self):
        self.send_command(evl_Commands['DumpZoneTimers'], '')

    def keypresses_to_partition(self, partitionNumber, keypresses):
        for char in keypresses:
            self.send_command(evl_Commands['PartitionKeypress'], str.format("{0},{1}", partitionNumber, char))
        
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

    def convertZoneDump(self, theString):

        returnItems = []
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

            #itemLastClosed = self.humanTimeAgo(timedelta(seconds=itemSeconds))
            status = ''
            if itemHexString == "FFFF":
                itemLastClosed = "Currently Open"
                status = 'open'
            if itemHexString == "0000":
                itemLastClosed = "Last Closed longer ago than I can remember"
                status = 'closed'
            else:
                itemLastClosed = str.format("Last Closed {0} seconds ago.", itemSeconds)
                status = 'closed'

            returnItems.append({'message': str(itemLastClosed), 'status': status, 'seconds': itemSeconds})
        return returnItems

        
    def handle_command_response(self, data):
        responseString = evl_TPI_Response_Codes[data]
        logging.debug("Envisalink response: " + responseString)
        if data != '00':
            logging.error("error sending command to envisalink.  Response was: " + responseString)
			
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

    def handle_zone_state_change(self, data):
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
                logging.debug("(zone %i) is %s", zoneNumber, "Open/Faulted" if zoneBit == '1' else "Closed/Not Faulted")

    def handle_partition_state_change(self, data):
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

            if partitionState['name'] == 'NOT_READY': ALARMSTATE['partition'][partitionNumber]['status'].update({'ready': False})
            logging.debug('Parition ' + str(partitionNumber) + ' is in state ' + partitionState['name'])
            logging.debug(json.dumps(self._alarmPanel.alarm_state))

    def handle_realtime_cid_event(self, data):
        eventTypeInt = int(data[0])
        eventType = evl_CID_Qualifiers[eventTypeInt]
        cidEventInt = int(data[1:4])
        cidEvent = evl_CID_Events[cidEventInt]
        partition = data[4:6]
        zoneOrUser = int(data[6:9])

        logging.debug('Event Type is ' + eventType)
        logging.debug('CID Type is ' + cidEvent['type'])
        logging.debug('CID Description is ' + cidEvent['label'])
        logging.debug('Partition is ' + partition)
        logging.debug(cidEvent['type'] + ' value is ' + str(zoneOrUser))
        
        return cidEvent

    def handle_zone_timer_dump(self, data):
        zoneInfoArray = self.convertZoneDump(data)
        for zoneNumber, zoneInfo in enumerate(zoneInfoArray, start=1):
            self._alarmPanel.alarm_state['zone'][zoneNumber]['lastfault'] = zoneInfo['message']
            self._alarmPanel.alarm_state['zone'][zoneNumber]['timerValue'] = zoneInfo['seconds']
            logging.debug("(zone %i) %s", zoneNumber, zoneInfo['message'])
