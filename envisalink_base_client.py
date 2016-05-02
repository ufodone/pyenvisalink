from twisted.protocols.basic import LineOnlyReceiver
from datetime import datetime
from datetime import timedelta
from alarm_state import AlarmState
import logging

class EnvisalinkClient(LineOnlyReceiver):
    def __init__(self, panel):
        # Are we logged in?
        self._loggedin = False
        self._alarmPanel = panel

    def keep_alive(self):
        """Todo- make this abstract"""
        raise NotImplementedError()
            
    def logout(self):
        logging.debug("Resetting Envisalink client connection...")
        self._loggedin = False
        if hasattr(self, 'transport'):
            self.transport.loseConnection()
            
    def send_data(self, data):
        """Raw data send- just make sure it's encoded properly and logged."""
        logging.debug(str.format('TX > {0}', data.encode('ascii')))
        self.sendLine(data.encode('ascii'))
    
    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        raise NotImplementedError()
        
    def lineReceived(self, input):
        if input != '':
            cmd = {}
            logging.debug('----------------------------------------')
            logging.debug(str.format('RX < {0}', input.decode('ascii')))
            cmd = self.parseHandler(input.decode('ascii'))
            try:
                logging.debug(str.format('calling handler: {0}', cmd['handler']))
                handlerFunc = getattr(self, cmd['handler'])
                result = handlerFunc(cmd['data'])
    
            except AttributeError:
                logging.warning(str.format("No handler exists for command: {0}. Skipping.", cmd['handler']))                
            
            try:
                logging.debug(str.format('Invoking callback: {0}', cmd['callback']))
                callbackFunc = getattr(self._alarmPanel, cmd['callback'])
                callbackFunc(result)
    
            except AttributeError:
                logging.warning(str.format("No callback exists for command: {0}. Skipping.", cmd['callback']))                

            logging.debug('----------------------------------------')
            
    def handle_login(self, data):
        """TODO: Make abstract"""
        self.send_data('user')

    def handle_login_success(self, data):
        self._loggedin = True
        logging.info('Password accepted, session created')

    def handle_login_failure(self, data):
        logging.error('Password is incorrect. Server is closing socket connection.')

    def handle_login_timeout(self, data):
        logging.error('Envisalink timed out waiting for password, whoops that should never happen. Server is closing socket connection')

    def handle_keypad_update(self, data):
        raise NotImplementedError()
        
    def handle_poll_response(self, data):
        raise NotImplementedError()
        
    def handle_command_response(self, code):
        raise NotImplementedError()