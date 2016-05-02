from twisted.internet import reactor
from twisted.python import log
from threading import Thread
from envisalink_client_factory import EnvisalinkClientFactory
from alarm_state import AlarmState
import logging

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
                
        self._keypadUpdateCallback = self._defaultCallback
        
        loggingconfig = {'level': 'DEBUG',
                     'format': '%(asctime)s %(levelname)s <%(name)s %(module)s %(funcName)s> %(message)s',
                     'datefmt': '%a, %d %b %Y %H:%M:%S'}

        logging.basicConfig(**loggingconfig)

        # allow Twisted to hook into our logging
        observer = log.PythonLoggingObserver()
        observer.start()
    
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
        
    def _defaultCallback(self, data):
        logging.info("Callback has not been set by client.")

    def start(self):
        logging.info(str.format("Connecting to envisalink on host: {0}, port: {1}", self._host, self._port))
        self._envisalinkClientFactory = EnvisalinkClientFactory(self)
        self._envisalinkConnection = reactor.connectTCP(self._host, self._port, self._envisalinkClientFactory)
        Thread(target=reactor.run, args=(False,)).start()
        
    def stop(self):
        reactor.stop()
        self._envisalinkConnection.disconnect()
        