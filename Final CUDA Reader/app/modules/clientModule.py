"""
ClientModule is for communication with client devices via wifi/BLE
"""
from app.utils import LoopEventListener, labelForDev
from app.utils.wifi import WebsocketServer, get_ip
from app.utils.ble import BLEServer, ReaderService, ReaderAdvertisement
import time
from threading import Thread
import json

try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject


# TODO:add authentication to connections.

class ClientModule(LoopEventListener, ):
    def initialize(self, websocketPort, **kwargs):
        self.websocketStatus = 'starting'
        self.websocketIP = get_ip()
        self.websocketPort = websocketPort
        try:
            self.websocketServer = WebsocketServer(ip=self.websocketIP, port=websocketPort, logger=self, )
        except Exception as e:
            self.error(f'Initiate websocket server error:{e}')
            self.websocketStatus = 'error'

        self.bluetoothStatus = 'starting'
        self.bleServer = BLEServer(logger=self)
        self.bleServer.add_service(ReaderService(0))
        self.bleServer.register()
        self.bleAdvertisement = ReaderAdvertisement(index=0, logger=self)
        self.bleAdvertisement.register()
        self.bleThread = Thread(name='bleMainLoop', target=self.bleServer.run, daemon=True)

    @labelForDev
    def getCharacteristicValue(self, characteristic_name: str):
        "Get a bluetooth characteristic value by name"
        return self.bleServer.get_char_value(characteristic_name)

    @labelForDev
    def getWebsocketStatus(self):
        return self.websocketStatus

    @labelForDev
    def websockAddr(self, ):
        "Return websocket server address"
        return self.websocketServer.websocketAddr

    @labelForDev
    def getWebsocketClients(self):
        "return current websocket clients"
        return self.websocketServer.getClients()

    @labelForDev
    def notifyBLEClients(self, jsonData):
        "send a json dictionary to all BLE clients"
        json_dump_status = json.dumps(jsonData['status'], separators=(',', ':'))
        self.bleServer.update_char_value('DeviceStatus', json_dump_status, False)
        json_dump_data = json.dumps(jsonData['data'], separators=(',', ':'))
        self.bleServer.update_char_value('DeviceData', json_dump_data, False)
        json_dump_action = json.dumps(jsonData['action'], separators=(',', ':'))
        self.bleServer.update_char_value('DeviceAction', json_dump_action, True)
        self.logger.debug('<Client> Sending BLE notification: action=' + json_dump_action + '\n'
                          '                                   status=' + json_dump_status + '\n' +
                          '                                   data=' + json_dump_data)
    
    @labelForDev
    def notifyClients(self, jsonData):
        "send a json dictionary to all webSocket clients"
        self.websocketServer.send(jsonData)


    def run(self):
        self.initialize(**self._initialize_kwargs)
        self.register()
        try:
            self.websocketServer.startInLoop(self.main.mainLoop)
        except Exception as e:
            self.logger.error(f"ClientModule.run: start websocket error: {e}")
            self.websocketStatus = 'error'

        try:
            self.bleThread.start()
            self.bluetoothStatus = 'started'
            self.logger.debug(f"Bluetooth started")
        except Exception as e:
            self.bluetoothStatus = 'error'
            self.logger.error(f"ClientModule.run: start bluetooth error: {e}")

    def stop(self):
        self.cleanUp()

    def restartWebsocketServer(self):
        "restart websocket server"

        def restartWs():
            "restart module"
            try:
                time.sleep(1)
                self.websocketServer.stopServer()
                time.sleep(1)
                self.websocketIP = get_ip()
                self.websocketServer = WebsocketServer(ip=self.websocketIP, port=self.websocketPort, logger=self, )
                self.websocketServer.startInLoop(self.main.mainLoop)
                self.debug(f'Restarted ws on {self.websocketServer.websocketAddr}.')
            except Exception as e:
                self.error(f"Restart ws {self.websocketIP}-{self.websocketPort} error : {e}")

        Thread(name='restart WS server', target=restartWs).start()
        self.debug('Websocket Server restarted.')

    def cleanUp(self):
        "clean up"
        try:
            self.websocketServer.stopServer()
            self.debug('Websocket Server stop.')
        except Exception as e:
            self.error(f'Stop websocket server error: {e}')

        """
        to-do: fix cleanup routine
        try:
            self.bleAdvertisement.Release()
            self.bleServer.quit()
        except Exception as e:
            self.error(f"Stop bluetooth server/advertisement error: {e}")
        """

    def messageHandler(self, msg):
        """
        handle message from clients
        msg format: {
            action: moduleName.attr.attr,
            other key:value pairs to pass to actuion function.
        }
        return value format: {
            action: same as msg.
            status: 'error' or 'ok'.
            data: response.
        }
        """
        action = msg.pop('action', None)
        if not action:
            self.error(f"Client Invalid message {msg}")
            return {'status': 'error', 'data': 'Invalid Message', 'action': action}
        target = self.main
        for chain in action.split('.'):
            target = getattr(target, chain.strip(), '__NON_EXISTING_MODULE__')
        try:
            if callable(target):
                try:
                    return {'status': 'ok', 'data': target(**msg), 'action': action}
                except Exception as e:
                    return {'status': 'error', 'data': str(e), 'action': action}
            elif target == '__NON_EXISTING_MODULE__':
                return {'status': 'error', 'data': f"Module {action} doesn't exist.", 'action': action}
            else:
                return {'status': 'ok', 'data': target, 'action': action}
        except Exception as e:
            self.error(f'Message handling error on <{action}>, msg:<{msg}>, error: {e}')
            return {'status': 'error', 'data': str(e), 'action': action}
