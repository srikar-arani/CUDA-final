from app.utils import LoopEventListener,Task ,labelForDev
from app.utils.wifi import wifi_connected,internet_connected
import time


class SyncTaskMixin:
    def __init__(self,logger):
        # delay a bit before start.
        super().__init__(delay=self._delay)
        self.logger=logger
    def __repr__(self):
        return f"{self.__class__.__name__}"
    def willRunIn(self):
        "return how many seconds this task will run"
        if self.nextExec:
            return self.nextExec - time.monotonic()
        else:
            return 9999
    
    def task(self):        
        self.nextRun(delay=self._interval)
        try:
            result = self.sync()
            self.logger.moduleStatus.update(result)
        except Exception as e:
            self.logger.error(f'{self}.task error: {e}')
        
class SyncWifiStatus(SyncTaskMixin,Task):
    "check for certain status and update LED"
    _interval = 5 # seconds
    _delay = 3
    _internet_connected = True
    _internet_connected_time = time.monotonic()
    errorCount = 0
    prevStatus = 'error'
    def sync(self):
        main = self.logger.main
        status = 'error' #default state is error.
        if getattr(main,'client',None): # if client module not loaded
            wsstatus = main.client.websocketStatus # websocket can be running or error.
            if wsstatus == 'running':
                wifistatus = main.peripheral.wifi.status # wifi status can be client or ap
                if wifistatus == 'client': # check if wifi is connected if wifi status is client.
                    if time.monotonic() - self._internet_connected_time > 90: # if checked morethan 90 seconds ago;
                        self._internet_connected = internet_connected() 
                        self._internet_connected_time = time.monotonic()
                    if self._internet_connected:                        
                        status = 'client'
                    else:
                        status = 'internet_disconnected'
                        self.logger.debug(f'Internet disconnected while wifi at client mode.')
                elif wifistatus == 'ap':
                    status = 'ap'
                    self._internet_connected_time = time.monotonic()
                    self._internet_connected = True
                else:
                    self.logger.debug(f"SyncWifiStatus: current wifi is {wifistatus}")
            else:
                self.logger.debug(f'SyncWiFiStatus Websocket Status is {wsstatus}')
                status = 'internet_disconnected'

        # cache the status for another 3 intervals before show the error.
        if status == 'error':
            self.errorCount += 1
            if self.errorCount <= 3:
                status = self.prevStatus
        else:
            self.errorCount = 0
            self.prevStatus = status
                 
        return {'wifi':status}

class SyncBTStatus(SyncTaskMixin,Task):
    _interval = 10
    _delay = 10
    def sync(self):
        main = self.logger.main
        status = 'error'
        if getattr(main,'client',None):
            if getattr(main.client,'bluetoothStatus',None):
                status = main.client.bluetoothStatus
        return {'bt':status}

class SyncPicoStatus(SyncTaskMixin,Task):
    _interval = 2
    _delay = 10
    def sync(self):
        main = self.logger.main 
        status = 'error'
        pico = {}
        if getattr(main,'measurement',None):
            pico = main.measurement.getPicoStatus()
            picoStatus = pico.pop('status','Unknown')
            if picoStatus in ['idle','running','waiting','error',]:
                status = picoStatus                
            elif picoStatus == 'done':
                status = 'idle'
            else:
                status = 'error'
            if picoStatus == 'running':
                self._interval = 1
            else:
                self._interval = 2
        return {'pico':status,'measurement':pico}

class SyncHeaterStatus(SyncTaskMixin,Task):
    _interval = 5
    _delay = 10
    def sync(self):
        main = self.logger.main 
        status = 'error'
        if getattr(main,'heating',None):
            status = main.heating.status            
        return {'heater':status}

class ReportStatus(Task):
    def __init__(self, logger):
        super().__init__(delay=5)
        self.logger = logger
    def task(self):
        self.nextRun(delay=1)
        if getattr(self.logger,'main',None):
            if getattr(self.logger.main,'client',None):
                self.logger.main.client.notifyClients(
                    {'status':'ok',
                     'data':self.logger.getModuleStatus(),
                     'action':'status.reportStatus'})


class StatusModule(LoopEventListener):
    def initialize(self, **kwargs):
        ""
        self.moduleStatus = {
            'wifi':'ap',  
            'bt':'running',  
            'pico':'idle',   # pico status can be idle, running, waiting, error
            'heater':'ready',  # heater status can be 'heatingQC', 'error', 'ready'
            'measurement': {}, # measurement status, including remainingTime, started, reason
        }
        self.syncTasks = {
            'wifi':SyncWifiStatus(self,),
            'bt':SyncBTStatus(self,),
            'pico':SyncPicoStatus(self),
            'heater':SyncHeaterStatus(self),
        }
        for t in self.syncTasks.values():
            self.scheduler.addTask(t)

        # report status to websocket clients
        self.scheduler.addTask(ReportStatus(self))
            
    @labelForDev    
    def readerStatus(self):
        """
        return the overall reader status. 
        idle : means reader is OK to run a new test.
        error: means reader is not OK to run a new test.
        running: means reader is running a test
        """
        if self.moduleStatus['heater'] == 'error':
            return 'error'
        if self.moduleStatus['pico'] == 'error':
            return 'error'
        if self.moduleStatus['pico'] == 'idle':
            return 'idle'
        return 'running'

    @labelForDev    
    def hasInternet(self):
        """
        return whether reader have access to internet
        using ping to google.com as a test.
        return True or False
        """
        return self.moduleStatus.get('wifi') == 'client' 
        
    
    @labelForDev
    def getModuleStatus(self):
        """return the status dictionary"""
        self.moduleStatus.update(reader=self.readerStatus())
        return self.moduleStatus

        
