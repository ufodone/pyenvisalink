class AlarmState:
    """Helper class for alarm state functionality."""

    @staticmethod
    def get_initial_alarm_state(maxZones, maxPartitions):
        """Builds the proper alarm state collection."""

        _alarmState = {'partition': {}, 'zone': {}}

        for i in range(1, maxPartitions + 1):
            _alarmState['partition'][i] = {'status': {'alarm': False, 'alarm_in_memory': False, 'armed_away': False,
                                                      'ac_present': True, 'armed_bypass': False, 'chime': False,
                                                      'armed_zero_entry_delay': False, 'alarm_fire_zone': False,
                                                      'trouble': False, 'bat_trouble': False, 'ready': False, 'fire': False,
                                                      'armed_stay': False, 'alpha': 'N/A', 'beep': False,
                                                      'exit_delay': False, 'entry_delay': False, 'last_disarmed_by_user': '',
                                                      'last_armed_by_user': '' }}
        for j in range (1, maxZones + 1):
            _alarmState['zone'][j] = {'status': {'open': False, 'fault': False, 'alarm': False, 'tamper': False}, 'last_fault': 0}

        return _alarmState
