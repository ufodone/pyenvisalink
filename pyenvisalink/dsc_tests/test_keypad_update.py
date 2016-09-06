import logging
import json
import re
from pyenvisalink.dsc_envisalinkdefs import *
from pyenvisalink import AlarmState

_LOGGER = logging.getLogger(__name__)

loggingconfig = {'level': 'DEBUG',
                 'format': '%(asctime)s %(levelname)s <%(name)s %(module)s %(funcName)s> %(message)s',
                 'datefmt': '%a, %d %b %Y %H:%M:%S'}

logging.basicConfig(**loggingconfig)


alarmState = AlarmState.get_initial_alarm_state(64, 8)

def handle_keypad_update(code, data):
    """Handle general- non partition based info"""
    for part in alarmState['partition']:
        alarmState['partition'][part]['status'].update(evl_ResponseTypes[code]['status'])
    _LOGGER.debug(str.format("(All partitions) state has updated: {0}", json.dumps(evl_ResponseTypes[code]['status'])))

_LOGGER.info('Alarm State before:')
print(alarmState['partition'])
handle_keypad_update('803','')
_LOGGER.info('Alarm State after:')
print(alarmState['partition'])
