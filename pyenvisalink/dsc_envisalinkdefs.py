## Alarm Server
## Supporting Envisalink 2DS/3
##
## This code is under the terms of the GPL v3 license.

evl_Commands = {
    'KeepAlive' : '000',
    'DumpZoneTimers' : '008',
    'PartitionKeypress' : '071',
    'Disarm' : '040',
    'ArmStay' : '031',
    'ArmAway' : '030',
    'ArmMax' : '032',
    'Login' : '005'
}

evl_ResponseTypes = {
    '505' :  {'name' : 'Login Prompt', 'description' : 'Sent During Session Login Only.', 'handler' : 'login'},
    '615' : {'name' : 'Envisalink Zone Timer Dump', 'description' : 'This command contains the raw zone timers used inside the Envisalink. The dump is a 256 character packed HEX string representing 64 UINT16 (little endian) zone timers. Zone timers count down from 0xFFFF (zone is open) to 0x0000 (zone is closed too long ago to remember). Each ''tick'' of the zone time is actually 5 seconds so a zone timer of 0xFFFE means ''5 seconds ago''. Remember, the zone timers are LITTLE ENDIAN so the above example would be transmitted as FEFF.', 'handler' : 'zone_timer_dump'},
    '500' : {'type' : 'envisalink', 'name': 'Poll', 'description' : 'Envisalink poll', 'handler' : 'poll_response'},
    '501' : {'type' : 'envisalink', 'name': 'Checksum', 'description' : 'Checksum failure', 'handler' : 'command_response_error'},
}
