import logging
from twisted.internet.task import LoopingCall
from twisted.internet.protocol import ReconnectingClientFactory
from honeywell_client import HoneywellClient

class EnvisalinkClientFactory(ReconnectingClientFactory):

    def __init__(self, panel):
      self._alarmPanel = panel
      
    def buildProtocol(self, addr):
        logging.debug("%s connection estblished to %s:%s", addr.type, addr.host, addr.port)
        logging.debug("resetting connection delay")
        self.resetDelay()
        if self._alarmPanel.panel_type == 'HONEYWELL':
            logging.info("Panel is Honeywell type- using Honeywell client.")
            self.envisalinkClient = HoneywellClient(self._alarmPanel)
        else:
            logging.info("Panel is DSC type- using DSC client.")
            
        # check on the state of the envisalink connection repeatedly
        self._currentLoopingCall = LoopingCall(self.envisalinkClient.keep_alive)
        self._currentLoopingCall.start(self._alarmPanel.keepalive_interval)
        return self.envisalinkClient

    def startedConnecting(self, connector):
        logging.debug("Started to connect to Envisalink...")

    def clientConnectionLost(self, connector, reason):
        logging.debug('Lost connection to Envisalink.  Reason: %s', str(reason))
        if hasattr(self, "_currentLoopingCall"):
            try:
                self._currentLoopingCall.stop()
            except:
                logging.error("Error trying to stop looping call, ignoring...")
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.debug('Connection failed to Envisalink. Reason: %s', str(reason))
        if hasattr(self, "_currentLoopingCall"):
            try:
                self._currentLoopingCall.stop()
            except:
                logging.error("Error trying to stop looping call, ignoring...")
        ReconnectingClientFactory.clientConnectionFailed(self, connector,
                                                         reason)