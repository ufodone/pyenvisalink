import logging
from honeywell_client import HoneywellClient
from alarm_state import AlarmState

class EnvisalinkAlarmPanel:
        
    def __init__(self, host, port=4025, panelType='HONEYWELL', 
                 userName='user', password='user', keepAliveInterval=30):
        self._host = host
        self._port = port
        self._panelType = panelType
        self._username = userName
        self._password = password
        self._keepAliveInterval = keepAliveInterval
        self._alarmState = AlarmState.get_initial_alarm_state()
        self._client = None
        
        self._loginSuccessCallback = self._defaultCallback
        self._keypadUpdateCallback = self._defaultCallback
        
        loggingconfig = {'level': 'DEBUG',
                     'format': '%(asctime)s %(levelname)s <%(name)s %(module)s %(funcName)s> %(message)s',
                     'datefmt': '%a, %d %b %Y %H:%M:%S'}

        logging.basicConfig(**loggingconfig)
    
    @property
    def host(self):
        return self._host
        
    @ property
    def port(self):
        return self._port
        
    @property
    def user_name(self):
        return self._username
        
    @property
    def password(self):
        return self._password
        
    @property
    def panel_type(self):
        return self._panelType
        
    @property
    def keepalive_interval(self):
        return self._keepAliveInterval
    
    @property
    def alarm_state(self):
        return self._alarmState
        
    @property
    def callback_keypad_update(self):
        return self._keypadUpdateCallback
        
    @property
    def callback_login_success(self):
        return self._loginSuccessCallback
        
    def _defaultCallback(self, data):
        logging.info("Callback has not been set by client.")	    

    def start(self):
        logging.info(str.format("Connecting to envisalink on host: {0}, port: {1}", self._host, self._port))
        if self._panelType == 'HONEYWELL':
            self._client = HoneywellClient(self)
            
        self._client.connect()
        
    def stop(self):
        logging.info("Disconnecting from the envisalink...")
        self._client.disconnect()