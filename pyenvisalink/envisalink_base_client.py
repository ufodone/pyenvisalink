import asyncio
import threading
import logging
from pyenvisalink import AlarmState

_LOGGER = logging.getLogger(__name__)

class EnvisalinkClient(asyncio.Protocol):
    """Abstract base class for the envisalink TPI client."""

    def __init__(self, panel):
        self._loggedin = False
        self._alarmPanel = panel
        self._eventLoop = asyncio.get_event_loop()
        self._transport = None
        self._shutdown = False

    def runEventLoop(self):
        """Used to spawn our async event loop in a sub-thread."""
        asyncio.set_event_loop(self._eventLoop)
        self._eventLoop.run_forever()
        self._eventLoop.close()

        _LOGGER.info("Connection shut down.")

    def start(self):
        """Public method for initiating connectivity with the envisalink."""
        self._shutdown = False
        self.connect()
        asyncio.ensure_future(self.keep_alive())

        if self._alarmPanel.zone_timer_interval > 0:
            asyncio.ensure_future(self.periodic_zone_timer_dump())

        workerThread = threading.Thread(target=self.runEventLoop, args=())
        workerThread.start()
    
    def stop(self):
        """Public method for shutting down connectivity with the envisalink."""
        _LOGGER.info("Shutting down Envisalink client connection...")
        self._loggedin = False
        self._shutdown = True
        self._eventLoop.call_soon_threadsafe(self._eventLoop.stop)

    def connect(self):
        """Internal method for making the physical connection."""
        _LOGGER.info(str.format("Started to connect to Envisalink... at {0}:{1}", self._alarmPanel.host, self._alarmPanel.port))
        coro = self._eventLoop.create_connection(lambda: self, self._alarmPanel.host, self._alarmPanel.port)
        asyncio.ensure_future(coro)
        
    def connection_made(self, transport):
        """asyncio callback for a successful connection."""
        _LOGGER.info("Connection Successful!")
        self._transport = transport
        
    def connection_lost(self, exc):
        """asyncio callback for connection lost."""
        self._loggedin = False
        if not self._shutdown:
            _LOGGER.error('The server closed the connection. Reconnecting...')
            self.reconnect(5)

    def reconnect(self, delay):
        """Internal method for reconnecting."""
        self._eventLoop.call_later(delay, self.connect)

    @asyncio.coroutine                         
    def keep_alive(self):
        """Used to periodically send a keepalive message to the envisalink."""
        raise NotImplementedError()

    @asyncio.coroutine
    def periodic_zone_timer_dump(self):
        """Used to periodically get the zone timers to make sure our zones are updated."""
        raise NotImplementedError()
            
    def disconnect(self):
        """Internal method for forcing connection closure if hung."""
        _LOGGER.debug('Closing connection with server for a reconnect...')
        self._transport.close()
            
    def send_data(self, data):
        """Raw data send- just make sure it's encoded properly and logged."""
        _LOGGER.debug(str.format('TX > {0}', data.encode('ascii')))
        self._transport.write((data + '\n').encode('ascii'))

    def send_command(self, code, data):
        """Used to send a properly formatted command to the envisalink"""
        raise NotImplementedError()

    def dump_zone_timers(self):
        """Public method for dumping zone timers."""
        raise NotImplementedError()

    def change_partition(self, partitionNumber):
        """Public method for changing the default partition."""
        raise NotImplementedError()

    def keypresses_to_default_partition(self, keypresses):
        """Public method for sending a key to a particular partition."""
        self.send_data(keypresses)

    def keypresses_to_partition(self, partitionNumber, keypresses):
        """Public method to send a key to the default partition."""
        raise NotImplementedError()

    def arm_stay_partition(self, code, partitionNumber):
        """Public method to arm/stay a partition."""
        raise NotImplementedError()

    def arm_away_partition(self, code, partitionNumber):
        """Public method to arm/away a partition."""
        raise NotImplementedError()

    def arm_max_partition(self, code, partitionNumber):
        """Public method to arm/max a partition."""
        raise NotImplementedError()

    def disarm_partition(self, code, partitionNumber):
        """Public method to disarm a partition."""
        raise NotImplementedError()
    
    def parseHandler(self, rawInput):
        """When the envisalink contacts us- parse out which command and data."""
        raise NotImplementedError()
        
    def data_received(self, data):
        """asyncio callback for any data recieved from the envisalink."""
        if data != '':
            fullData = data.decode('ascii').strip()
            cmd = {}
            result = ''
            _LOGGER.debug('----------------------------------------')
            _LOGGER.debug(str.format('RX < {0}', fullData))
            lines = str.split(fullData, '\n')
            for line in lines:
                cmd = self.parseHandler(line)
            
                try:
                    _LOGGER.debug(str.format('calling handler: {0}', cmd['handler']))
                    handlerFunc = getattr(self, cmd['handler'])
                    result = handlerFunc(cmd['data'])
    
                except AttributeError:
                    _LOGGER.warning(str.format("No handler exists for command: {0}. Skipping.", cmd['handler']))                
            
                try:
                    _LOGGER.debug(str.format('Invoking callback: {0}', cmd['callback']))
                    callbackFunc = getattr(self._alarmPanel, cmd['callback'])
                    callbackFunc(result)
    
                except AttributeError:
                    _LOGGER.warning(str.format("No callback exists for command: {0}. Skipping.", cmd['callback']))                

                _LOGGER.debug('----------------------------------------')
            
    def handle_login(self, data):
        """Handler for when the envisalink challenges for password."""
        raise NotImplementedError()

    def handle_login_success(self, data):
        """Handler for when the envisalink accepts our credentials."""
        self._loggedin = True
        _LOGGER.debug('Password accepted, session created')

    def handle_login_failure(self, data):
        """Handler for when the envisalink rejects our credentials."""
        self._loggedin = False
        _LOGGER.error('Password is incorrect. Server is closing socket connection.')
        self.stop()

    def handle_login_timeout(self, data):
        """Handler for if we fail to send a password in time."""
        self._loggedin = False
        _LOGGER.error('Envisalink timed out waiting for password, whoops that should never happen. Server is closing socket connection')
        self.disconnect()

    def handle_keypad_update(self, data):
        """Handler for when the envisalink wishes to send us a keypad update."""
        raise NotImplementedError()
        
    def handle_poll_response(self, data):
        """When sending our keepalive message, handle the response back."""
        raise NotImplementedError()
        
    def handle_command_response(self, data):
        """When we send any command- this will be called to parse the initial response."""
        raise NotImplementedError()

    def handle_zone_state_change(self, data):
        """Callback for whenever the envisalink reports a zone change."""
        raise NotImplementedError()

    def handle_partition_state_change(self, data):
        """Callback for whenever the envisalink reports a partition change."""
        raise NotImplementedError()

    def handle_realtime_cid_event(self, data):
        """Callback for whenever the envisalink triggers alarm arm/disarm/trigger."""
        raise NotImplementedError()

    def handle_zone_timer_dump(self, data):
        """Callback for zone timer dump response."""
        raise NotImplementedError()
