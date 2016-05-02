MAXPARTITIONS = 8
MAXZONES = 64

class AlarmState:
    @staticmethod
    def get_initial_alarm_state():
        _alarmState = {'partition': {}}
        
        for i in range(1, MAXPARTITIONS + 1):
            _alarmState['partition'][i] = {'status': {'alarm': False, 'alarm_in_memory': False, 'armed_away': False,
                                                      'ac_present': False, 'armed_bypass': False, 'chime': False,
                                                      'armed_zero_entry_delay': False, 'alarm_fire_zone': False,
                                                      'trouble': False, 'ready': False, 'fire': False,
                                                      'armed_stay': False, 'alpha': False, 'beep': False}}
            _alarmState['partition'][i]['zone'] = {}
            for j in range (1, MAXZONES + 1):
                _alarmState['partition'][i]['zone'][j] = {'open': False, 'fault': False, 'alarm': False, 'tamper': False}      
        return _alarmState
    
