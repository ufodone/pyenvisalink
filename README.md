This project is an attempt at creating a pure, raw python3 library for interfacing with the envisalink line of alarm products.  In particular the envisalink EVL3 and EVL4.  This project leverages the asyncio library, providing full asynchronous communication with the envisalink board.  All that must be done is call the proper constructor with connectivity/credentials, and provide callbacks for any events you wish to be notified of. 

Also, an attempt will be made at merging the two APIs that are available for the Envisalink alarm interfaces (DSC and Honeywell).  While the APIs are quite a bit different, a base functionality is common between them, and thus an abstraction can be made. We'll see how that works in practice ;).

This project was originally a fork of the [Envisalink 2DS/3 Alarm Server for Honeywell or Ademco Vista Security Systems](https://github.com/MattTW/HoneyAlarmServer) - Matt's focus was much more of an "all-in-one" approach, where my aim is to just provide a python API that can be used within something else. While our codebases are now a bit seperate due to my use of a different asynchronous library, his examples and logic were invaluable!

I'm currently working on integrating it with the [Home Assistant](https://home-assistant.io) project. [Project Page](https://github.com/home-assistant/home-assistant)

This is still beta software, and requires python 3.4+.  So far it has only been tested with an Envisalink 3 and Honeywell Vista 20p panel.

### my changes (crackers8199)
- added entry/exit delays to all arm/disarm actions
- make sure armed_zero_entry_delay is cleared on any disarm action or arming without *9
