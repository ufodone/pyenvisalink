import asyncio
import threading
import logging
from alarm_state import AlarmState

class EnvisalinkClient(asyncio.Protocol):
    def __init__(self, panel):
        # Are we logged in?
        self._loggedin = False
        self._alarmPanel = panel
        self._eventLoop = asyncio.get_event_loop()
        self._transport = None

    def connect(self):
        logging.info(str.format("Started to connect to Envisalink... at {0}:{1}", self._alarmPanel.host, self._alarmPanel.port))
        coro = self._eventLoop.create_connection(lambda: self, self._alarmPanel.host, self._alarmPanel.port)
        asyncio.ensure_future(coro)
        asyncio.ensure_future(self.keep_alive())
        workerThread = threading.Thread(target=self.runEventLoop, args=())
        workerThread.start()
        
    def runEventLoop(self):
        asyncio.set_event_loop(self._eventLoop)
        self._eventLoop.run_forever()

    def connection_made(self, transport):
        logging.info("Connection Successful!")
        self._transport = transport
        #TODO setup the keepalive here?
        
    def connection_lost(self, exc):
        self._loggedin = False
        logging.error('The server closed the connection. Reconnecting...')
        self.reconnect(5)

    def reconnect(self, delay):
        self._eventLoop.call_later(delay, self.connect)

    @asyncio.coroutine                         
    def keep_alive(self):
        raise NotImplementedError()
            
    def disconnect(self):
        logging.debug("Shutting down Envisalink client connection...")
        self._loggedin = False
        self._eventLoop.call_soon_threadsafe(self._eventLoop.stop)
            
    def send_data(self, data):
        """Raw data send- just make sure it's encoded properly and logged."""
        logging.debug(str.format('TX > {0}', data.encode('ascii')))
        self._transport.write((data + '\n').encode('ascii'))

    def send_command(self, code, data):
        raise NotImplementedError()

    def dump_zone_timers(self):
        raise NotImplementedError()

    def change_partition(self, partitionNumber):
        raise NotImplementedError()

    def keypresses_to_default_partition(self, keypresses):
        self.send_data(keypresses)

    def keypresses_to_partition(self, partitionNumber, keypresses):
        raise NotImplementedError()
    
    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        raise NotImplementedError()
        
    def data_received(self, data):
        if data != '':
            cmd = {}
            result = ''
            logging.debug('----------------------------------------')
            logging.debug(str.format('RX < {0}', data.decode('ascii').strip()))
            cmd = self.parseHandler(data.decode('ascii').strip())
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
        logging.debug('Password accepted, session created')

    def handle_login_failure(self, data):
        self._loggedin = False
        logging.error('Password is incorrect. Server is closing socket connection.')

    def handle_login_timeout(self, data):
        self._loggedin = False
        logging.error('Envisalink timed out waiting for password, whoops that should never happen. Server is closing socket connection')

    def handle_keypad_update(self, data):
        raise NotImplementedError()
        
    def handle_poll_response(self, data):
        raise NotImplementedError()
        
    def handle_command_response(self, data):
        raise NotImplementedError()

    def handle_zone_state_change(self, data):
        raise NotImplementedError()

    def handle_partition_state_change(self, data):
        raise NotImplementedError()

    def handle_realtime_cid_event(self, data):
        raise NotImplementedError()

    def handle_zone_timer_dump(self, data):
        raise NotImplementedError()
