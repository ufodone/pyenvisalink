import logging
from pyenvisalink import HoneywellClient
from pyenvisalink import AlarmState

class EnvisalinkAlarmPanel:
        
    def __init__(self, host, port=4025, panelType='HONEYWELL',
                 envisalinkVersion=3, userName='user', password='user',
                 keepAliveInterval=30):
        self._host = host
        self._port = port
        self._panelType = panelType
        self._evlVersion = envisalinkVersion
        self._username = userName
        self._password = password
        self._keepAliveInterval = keepAliveInterval
        self._maxPartitions = 8
        if envisalinkVersion < 4:
            self._maxZones = 64
        else:
            self._maxZones = 128
        self._alarmState = AlarmState.get_initial_alarm_state(self._maxZones, self._maxPartitions)
        self._client = None
        
        self._loginSuccessCallback = self._defaultCallback
        self._loginFailureCallback = self._defaultCallback
        self._loginTimeoutCallback = self._defaultCallback
        self._keypadUpdateCallback = self._defaultCallback
        self._zoneStateChangeCallback = self._defaultCallback
        self._paritionStateChangeCallback = self._defaultCallback
        self._cidEventCallback = self._defaultCallback
        self._zoneTimerCallback = self._defaultCallback

        
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
    def envisalink_version(self):
        return self._evlVersion
        
    @property
    def keepalive_interval(self):
        return self._keepAliveInterval
    
    @property
    def alarm_state(self):
        return self._alarmState
        
    @property
    def callback_login_success(self):
        return self._loginSuccessCallback

    @property
    def callback_login_failure(self):
        return self._loginFailureCallback

    @property
    def callback_login_timeout(self):
        return self._loginTimeoutCallback

    @property
    def callback_keypad_update(self):
        return self._keypadUpdateCallback

    @property
    def callback_zone_state_change(self):
        return self._zoneStateChangeCallback

    @property
    def callback_partition_state_change(self):
        return self._paritionStateChangeCallback

    @property
    def callback_realtime_cid_event(self):
        return self._cidEventCallback

    @property
    def callback_zone_timer_dump(self):
        return self._zoneTimerCallback
        
    def _defaultCallback(self, data):
        logging.info("Callback has not been set by client.")	    

    def start(self):
        logging.info(str.format("Connecting to envisalink on host: {0}, port: {1}", self._host, self._port))
        if self._panelType == 'HONEYWELL':
            self._client = HoneywellClient(self)
            
        self._client.start()
        
    def stop(self):
        logging.info("Disconnecting from the envisalink...")
        if self._client:
            self._client.stop()

    def dump_zone_timers(self):
        self._client.dump_zone_timers()

    def change_partition(self, partitionNumber):
        self._client.change_partition(partitionNumber)

    def keypresses_to_default_partition(self, keypresses):
        self._client.keypresses_to_default_partition(keypresses)

    def keypresses_to_partition(self, partitionNumber, keypresses):
        self._client.keypresses_to_partition(partitionNumber, keypresses)
