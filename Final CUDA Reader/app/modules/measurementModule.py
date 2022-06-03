from app.utils import LoopEventListener, Task, labelForDev
import time
from threading import Thread
from datetime import datetime
import sys
from app.utils.picoLibrary import M355
from app.setup.install import  SYSTEM_ID,SYSTEM_SERIAL

# NOTE
# How setup uart on pin.
# sudo raspi-config => Interfaceing Options => Serial
# => disable login shell, enable serial interface
# then run ls -l /tty/serial*
# lrwxrwxrwx 1 root root 5 Jul 24 02: 40 / dev/serial0 -> ttyS0
# lrwxrwxrwx 1 root root 7 Jul 24 02: 40 / dev/serial1 -> ttyAMA0
# this means can use miniUART on GPIO14,15
# might switch PL011 to ttyS0

# BUG: Serial Proxy calling serial port function <readline> error
# this happened when installing a new setup.
# however, it disappeared after I disable login shell from sudo raspi-config.
# the problem still exist, when a new scan starts.


# controls whether the monitor tasks will trigger measurement stop.
WILL_STOP_ON_FLUID_FILL = False
WILL_STOP_ON_TEMPERATURE = False
WILL_STOP_ON_CIHP_INSERTION = True


class FluidFillTask(Task):
    _FLUID_FILL_THRESHOLD = 5

    def __init__(self, main, pstat, logger, channel):
        ""
        super().__init__(delay=3)
        self.channel = channel
        self.pstat = pstat
        self.interval = 120  # set fluid fill check interval to 120 seconds.
        self.logger = logger
        self.main = main
        self.fluidFillFailure = 0

    def getRemainingTime(self):
        # the remaining time is synced with chip
        task = self.logger.measurementTask.get(self.channel, None)
        if task:
            return task.getRemainingTime()
        else:
            return 0

    def task(self):
        remainingTime = self.getRemainingTime()
        if remainingTime <= self.interval:
            self.done()
            return
        self.nextRun(delay=self.interval)

        data = self.pstat.fluidFillValue(self.channel)
        ts = time.monotonic()
        self.main.dataProcess.appendFluidFill(self.channel, ts, data)

        # TODO
        # should we abort the run if fluid fill failed during the testing?
        if data < self.pstat.FLUID_FILL_THREASHOLD:
            self.fluidFillFailure += 1
            # self.main.client.notifyClients({'status': 'ok', 'action': f"Fluid Fill Error - {self.channel}",
            #                                 'data': f"Value: {data:.5f}uA. Count: {self.fluidFillFailure} / {self._FLUID_FILL_THRESHOLD}"})

            # never stop due to fluid fill.
            if (not self.logger.devMode) and self.fluidFillFailure >= self._FLUID_FILL_THRESHOLD and WILL_STOP_ON_FLUID_FILL:
                self.logger.measurementTask[self.channel].done(
                    reason='fluidFillError')


class MonitorTaskMixin():
    def getRemainingTime(self):
        if getattr(self, '_RunningMeasurementTask', 'NonExisting') == 'NonExisting':
            self._RunningMeasurementTask = self.logger.measurementTask
        if self._RunningMeasurementTask:
            return max(i.getRemainingTime() for i in self._RunningMeasurementTask.values())
        return 0

    def stopMeasurementTask(self, reason):
        for t in self.logger.measurementTask.values():
            t.done(reason=reason)
            # change reason to abort for other tasks.
            reason = "abort"

# TODO
# May find when running chips, sometimes chip insertion detection will fail
# but obviously chip is inserted.


class ChipInsertionTask(MonitorTaskMixin, Task):
    _CHIP_INSERTION_THRESHOLD = 2

    def __init__(self, main, pstat, logger):
        ""
        super().__init__(delay=6)
        self.pstat = pstat
        self.interval = 60
        self.main = main
        self.insertionFailure = 0
        self.logger = logger

    def task(self):
        remainingTime = self.getRemainingTime()
        if remainingTime <= self.interval:
            self.done()
            return
        self.nextRun(delay=self.interval)
        try:
            chipInserted = self.pstat.chipInserted()
        except Exception as e:
            chipInserted = 0
        
        ts = time.monotonic()
        self.main.dataProcess.appendChipInsertion(ts, int(chipInserted))

        if not chipInserted:
            self.insertionFailure += 1
            self.main.client.notifyBLEClients({'status': 'ok',
                                            'action': "measurementModel.detectedNoChip",
                                            'data': f"Count: {self.insertionFailure} / {self._CHIP_INSERTION_THRESHOLD}"})
            self.logger.info('Chip insertion detected chip not inserted.')
            if (not self.logger.devMode) and self.insertionFailure >= self._CHIP_INSERTION_THRESHOLD and WILL_STOP_ON_CIHP_INSERTION:
                self.stopMeasurementTask(reason='ChipNotInserted')


class RecordTemperatureTask(MonitorTaskMixin, Task):
    # threshold that will trigger stop if abnormal temperature detected more than this time.
    _ABNORMAL_TEMP_THRESHOLD = 5

    # default alarming delta T to 5 degree off.
    def __init__(self, main, pstat, logger, deltaT=5):
        ""
        super().__init__(delay=10)
        self.pstat = pstat
        self.interval = 60
        self.logger = logger
        self.main = main
        self.deltaT = deltaT
        self.abnormalTemps = []

    def task(self):
        remainingTime = self.getRemainingTime()
        if remainingTime <= self.interval:
            self.done()
            return
        self.nextRun(delay=self.interval)

        temp = self.main.heating.getCurrentTemp()
        ts = time.monotonic()
        self.main.dataProcess.appendTemperature(ts, temp)

        # if the temperature is too off, abort?
        #if abs(self.main.heating.getGoalTemp()-temp) > self.deltaT:
        #    self.abnormalTemps.append(int(temp))
        #    self.logger.info(
        #        f'Detected abnormal temperature: {temp:.1f} degC.')
        #    if (not self.logger.devMode) and (len(self.abnormalTemps) >= self._ABNORMAL_TEMP_THREASHOLD) and WILL_STOP_ON_TEMPERATURE:
        #        self.stopMeasurementTask(
        #            reason=f'AbnormalTemperatures:{",".join(self.abnormalTemps)}')


class CovidTask(Task):
    def __init__(self, main, pstat, logger, channel, ):
        """
        method: name of the method
        """
        super().__init__(delay=0.05)
        self.channel = channel
        self.pstat = pstat
        self.interval = self.pstat.getInterval(channel)
        self.logger = logger
        self.main = main
        self.lastFit = None

    def __repr__(self):
        return f"CovidTask<{self.channel}><avg:{self.avgTime:.2f}s><next{(self.nextExec-time.monotonic()):.2f}s>, "

    def getRemainingTime(self):
        if self.status == 'done':
            return 0

        return self.pstat.getRemainingTime(self.startTime,
                                           channel=self.channel,
                                           isRunning=(self.status == "running"))

    def task(self):
        " run measurement,set its nextExec to a time "
        remainingTime = self.getRemainingTime()
        if remainingTime <= 0:
            self.done('end')
            return
        self.nextRun(delay=self.interval)

        # add .1 second stop before each covid Task
        time.sleep(0.1)

        attempt = 0
        while attempt < 3:
            attempt += 1
            try:
                voltage, amp,*other = self.pstat.measure(self.channel, self.lastFit)
                assert (len(amp) > 0), f'Amp length = {len(amp)}'

                self.lastFit = self.main.dataProcess.appendData(channel=self.channel,
                                                                timeStamp=time.monotonic(), voltage=voltage, amp=amp,other=other)

                self.logger.debug(
                    f"Measurement on {self.channel}, remaining time {remainingTime:.3f}s.")
                return
            except Exception as e:
                self.logger.error(
                    f"CovidTask.task error on {self.channel}, attempt = {attempt}, Error: {e}")

        # if still didn't success after 3 attempts, stop.
        self.logger.critical(
            f"CovidTask Failed after 3 attempts. remaining time: {remainingTime:.3f}s.")
        self.cancelRun()
        self.done(reason='picoScanError')
        return

    def done(self, reason='abort'):
        "mark this task as None in logger."
        self.status = 'done'
        self.stopReason = reason

        if all(i.status == 'done' for i in self.logger.measurementTask.values()):
            # check if all scan tasks are done normally.
            normalStop = all(
                i.stopReason == 'end' for i in self.logger.measurementTask.values())
            if normalStop:
                self.main.dataProcess.endScan()
            else:
                stopReasons = ';'.join(
                    f"{c}-{t.stopReason}" for c, t in self.logger.measurementTask.items())
                self.main.dataProcess.abortScan(reason=stopReasons)

            # stop heating automatically
            self.main.heating.stopTempControl()
            # reset measurementTask in logger when all is done.
            self.logger.measurementTask = {}


class FibrinogenTask(Task):
    def __init__(self, main, pstat, logger, channel, ):
        """
        method: name of the method
        """
        super().__init__(delay=0.05)
        self.channel = channel
        self.pstat = pstat
        self.interval = self.pstat.getInterval(channel)
        self.logger = logger
        self.main = main
        self.lastFit = None
        self._runCount = 0

    def __repr__(self):
        return f"FibrinogenTask<{self.channel}><avg:{self.avgTime:.2f}s><next{(self.nextExec-time.monotonic()):.2f}s>, "

    def getRemainingTime(self):
        if self.status == 'done':
            return 0

        return self.pstat.getRemainingTime(self.startTime,
                                           channel=self.channel,
                                           isRunning=(self.status == "running"))

    def task(self):
        " run measurement,set its nextExec to a time "

        # wait 30 seconds before measuring
        remainingTime = self.getRemainingTime()
        self.nextRun(delay=self.interval)
        if remainingTime > 0:
            return
        
        # measure a total of 5 times
        if self._runCount > 4:
            self.done('end')
            return

        # add .001 second stop before each fibrinogen Task
        time.sleep(0.001)

        attempt = 0
        while attempt < 3:
            attempt += 1
            try:
                voltage, amp,*other = self.pstat.measure(self.channel, self.lastFit)
                assert (len(amp) > 0), f'Amp length = {len(amp)}'

                # use all but the first test (0)
                if self._runCount != 0:
                    self.lastFit = self.main.dataProcess.appendData(channel=self.channel,
                                                                    timeStamp=time.monotonic(), voltage=voltage, amp=amp,other=other)

                self.logger.debug(
                    f"Measurement on {self.channel}, measurement number: {self._runCount}.")
                
                self._runCount += 1
                return
            except Exception as e:
                self.logger.error(
                    f"FibrinogenTask.task error on {self.channel}, attempt = {attempt}, Error: {e}")

        # if still didn't success after 3 attempts, stop.
        self.logger.critical(
            f"FibrinogenTask Failed after 3 attempts. Measurement number: {self._runCount}.")
        self.cancelRun()
        self.done(reason='picoScanError')
        return

    def done(self, reason='abort'):
        "mark this task as None in logger."
        self.status = 'done'
        self.stopReason = reason

        if all(i.status == 'done' for i in self.logger.measurementTask.values()):
            # check if all scan tasks are done normally.
            normalStop = all(
                i.stopReason == 'end' for i in self.logger.measurementTask.values())
            if normalStop:
                self.main.dataProcess.endScan()
            else:
                stopReasons = ';'.join(
                    f"{c}-{t.stopReason}" for c, t in self.logger.measurementTask.items())
                self.main.dataProcess.abortScan(reason=stopReasons)
            # stop heating automatically (not needed in fibrinogen task)
            # self.main.heating.stopTempControl()
            # reset measurementTask in logger when all is done.
            self.logger.measurementTask = {}


class UpdatePicoStatusTask(Task):
    """This is for update pico status, so that other threads will not call pico functions.
    This task run forever.
    this is no longer used. Instead, we use the StartMeasurementTask to monitor.
    """

    def __init__(self, logger):
        super().__init__(delay=5)
        self.logger = logger
        self.interval = 2  # update every 2 seconds

    def task(self):
        self.nextRun(delay=self.interval)
        try:
            if not self.logger.measurementTask:
                if self.logger.picoConnected:
                    self.logger.picoStatus = 'idle'
                else:
                    self.logger.picoStatus = 'error'
            else:
                tasks = list(self.logger.measurementTask.values())
                if tasks:
                    self.logger.picoStatus = getattr(
                        tasks[0], 'status', 'unknown')

                    if self.logger.picoStatus == 'running':
                        self.logger._testStarted_ = True
        except Exception as e:
            self.logger.critical(f'UpdatePicoStatusTask.task error: {e}')
            self.logger.picoStatus = 'error'


class PostPicoStatusTask(Task):
    """
    This is for posting pico status to cloud. Run every 3 minutes.
    """

    def __init__(self, logger):
        super().__init__(delay=0.1)
        self.logger = logger
        self.interval = 180  # update every 3 minutes

    def task(self):
        self.nextRun(delay=self.interval)        
        userId = self.logger.main.config.get('userId')
        if userId:
            reader = self.logger.getPicoStatus()
            reader['id'] = self.logger.main.getSystemID()            
            self.logger.main.cloud.post('/updateStatus',json={"userId":userId,"reader":reader})
            


class StartMeasurementTask(Task):
    "monitor chip insertion and pico status."
    _max_idle_time = 3 * 60

    def __init__(self, master):
        super().__init__(delay=0.1)
        self.interval = 2
        self.master = master
        self.pstat = master.pstat     
        # measureStarted is set to False only in here.  
        # when a chip is not inserted, it is set to False.
        self.measureStarted = True 
        self.idleTime = -60 # give additional 60 seconds at start before stopping heating by idle state.
        self.unstagedChipInserted = False # used to track if user inserted a chip that is not staged
        self.startUpChipInserted = True

    def mainModuleRdy(self):
        return getattr(self.master,'main',None)

    def peripheralModuleRdy(self):
        "check if peripheral module is ready"
        return self.mainModuleRdy() and getattr(self.master.main,'peripheral',None)
    
    def clientModuleRdy(self):
        "check if client module is ready"
        return self.mainModuleRdy() and getattr(self.master.main, 'client', None)

    def heatingModuleRdy(self):
        return self.mainModuleRdy() and getattr(self.master.main,'heating',None) and self.master.main.heating.status == 'ready'
            
    def task(self):
        self.nextRun(delay=self.interval)
        self.idleTime += self.interval
        

        # if measurement already started, return without anythin.
        if self.master.measurementTask:
            self.idleTime = 0
            tasks = list(self.master.measurementTask.values())
            if tasks:
                self.master.picoStatus = getattr(
                    tasks[0], 'status', 'unknown')
                if self.master.picoStatus == 'running':
                    self.master._testStarted_ = True
            return
        elif self.master.measurementTask:
            self.idleTime = 0
            tasks = list(self.master.measurementTask.values())
            if tasks:
                self.master.picoStatus = getattr(
                    tasks[0], 'status', 'unknown')
                if self.master.picoStatus == 'running':
                    self.master._testStarted_ = True
            return

        try:
            chipInserted = self.pstat.chipInserted()
            if self.pstat.isConnected:
                self.master.picoStatus = 'idle'
            else:
                self.master.picoStatus = 'error'
        except:
            # also make this task Update Pico status
            self.master.picoStatus = 'error'
            return

        # when covid task is not running, 
        # if idle for more than 15min, stop heating.
        if self.idleTime > self._max_idle_time:
            self.idleTime = 0
            if not self.master.devMode:
                self.master.main.heating.stopTempControl()

        # if chip not insrted, reset measureStarted.
        if not chipInserted:
            self.startUpChipInserted = False
            # we clear the LED status whenever chip is removed. 
            if self.measureStarted:                
                self.measureStarted = False
                if self.peripheralModuleRdy():
                    self.master.main.peripheral.sendMsgToLED('clear')
                if self.clientModuleRdy():
                    self.master.main.client.notifyBLEClients({'status': 'ok',
                                                              'action': 'measurement.chipRemoved',
                                                              'data': ''})        
            return
        
        # if chip inserted, and reader never see chip not inserted state, 
        # this means user left the chip in reader during boot up.
        if self.startUpChipInserted:            
            if self.peripheralModuleRdy():
                self.startUpChipInserted = False
                self.master.main.peripheral.sendMsgToLED('chip-inserted-on-start')
            return
        
        
        
        #if not self.heatingModuleRdy():
            # if heating module is not passed QC: then don't start test.
        #    return

        if not self.peripheralModuleRdy():
            # if peripheral module is not ready, return
            return

        if not self.clientModuleRdy():
            return
                
        # if chip is inserted, and already have chip not inserted previously     
        # then we wait for 3 seconds before starting test.   
        if chipInserted and (not self.measureStarted):            
            for i in range(6):
                time.sleep(0.5)
                chipInserted = self.pstat.chipInserted()
                if not chipInserted:
                    # cancel the task if chip is removed.
                    return

            # update chip insertion characteristic with chip type
            #self.master.main.client.updateCharacteristicAndNotify("DeviceStatusesAsJSON", str(self.pstat.chipType()))

            self.idleTime = 0
            self.measureStarted = True
            self.master.main.peripheral.sendMsgToLED('startNewMeasure')
            id = self.master.main.cloud.getPendingTestId()
            # TODO / FIXME: need to notify the user that no internet connection is available.

            if self.pstat.chipType() == 7:
                self.master.main.client.notifyBLEClients({'status': 'ok',
                                                        'action': 'measurement.covid.beginningTest',
                                                        'data': ''})
            else:
                self.master.main.client.notifyBLEClients({'status': 'ok',
                                                          'action': 'measurement.fibrinogen.beginningTest',
                                                          'data': ''})
            
            self.master.startMeasure(
                meta={'name': f"Test On {datetime.now().strftime('%Y%m%d-%H:%M')}",                   
                'deviceId': SYSTEM_ID,
                'deviceSerial': SYSTEM_SERIAL,
                'deviceDataId': id,
                'chipType': self.pstat.chipType()
                })
            return


class MeasurementModule(LoopEventListener):
    """
    Running Pico measurement. 
    Usually, should use measurement.startMeasure to start measurement. see method desc for details.
    """

    def initialize(self, picoPort,demoMode=False, **kwargs):
        
        self.pstat = M355(picoPort, logger=self)
        self.pstat.initialize()
    
        # load settings
        self.pstat.loadSettings()

        self.measurementTask = {}

        # devMode will bypass temperature and other checks.
        self.devMode = (sys.argv[-1] == '-dev')

        # demoMode will speed up the measurement. to 5 minutes.
        self.demoMode = demoMode
        if self.demoMode:
            # don't use devMode even in demoMode.
            # self.devMode = True
            self.debug('RUNNING in demo mode, scan last 5minutes results are random.')

        if self.pstat.isConnected:
            self.picoStatus = 'idle'
        else:
            self.picoStatus = 'error'
        # waitReason to to hold status when checking.
        self.waitReason = None

        # update pico status task
        # self.scheduler.addTask(UpdatePicoStatusTask(logger=self))

        # update pico status as well as start measruement automatically.
        self.startMeasurementTask = StartMeasurementTask(master=self)
        self.scheduler.addTask(self.startMeasurementTask)

        #self.scheduler.addTask(PostPicoStatusTask(self))

        self._testStarted_ = False
        self._picoStop = False

    @labelForDev
    def toggleDemoMode(self,):
        """
        turn on or off the demo mode. return the current demo mode state
        In Demo Mode, the measurement will run for 5 minutes.
        The fluid fill and scan signal check are still normal.
        The test result will be cycling through Positive, Negative, Invalid, Error
        """
        self.demoMode = not self.demoMode
        state = 'ON' if self.demoMode else 'OFF'
        self.debug(f'Turned Demo mode to {state}')
        self.main.peripheral.sendMsgToLED(f'demoMode-{state}')
        return f"The Demo Mode is {state}"

    @property
    def picoConnected(self):
        return self.pstat.isConnected

    def cleanUp(self):
        "stop measurement and flush serial port"
        self.stopPico()
        self.pstat.close()

    @labelForDev
    def setDevMode(self, devMode: bool = False):
        "set measurement to devMode to skip chip insertion and fluid check."
        self.devMode = devMode
        return f'Set Pico DevMode {"ON" if devMode else "OFF"}.'

    @labelForDev
    def getPicoMethod(self, method: str = None,):
        """
        get the current pico method settings,
        if method name is given, only send this method back.
        otherwise send all available methods settings. 
        """
        return self.pstat.getMethod(method)

    @labelForDev
    def setPicoMethod(self, method: str, settings: dict, ):
        """Set pico settings
        method: the name to save,
        settings: the settings dictionary to update. 
        Note: using method level update. So a new method with same name will overwrite old method.  
        """
        return self.pstat.setMethod(method, settings)

    @labelForDev
    def deletePicoMethod(self, method: str,):
        """
        delete method in pico settings
        method: the name to delete
        """
        return self.pstat.deleteMethod(method)
    
    @labelForDev
    def switchPicoMethod(self,method:str):
        """
        change the current pico method to a new given method.
        if the covid task is running, this will change the running task method to the new method.
        Note: no new channel will be added to scheduler during this select.
        So if you start the test with a method that only scan C1, then switch to a method
        that scan both C1 and C2, then C2 will not be added.
        EXPERIMENTAL: this is not fully tested. 
        """
        self.pstat.selectMethod(method)
        if self.measurementTask:
            for channel, task in self.measurementTask.items():
                task.interval = task.pstat.getInterval(channel)
                task.lastFit = None
                task.nextRun(delay=1)
                self.scheduler.reschedule()
        return f"Selected pico method to {method}"

    @labelForDev
    def stopPico(self,):
        "Cancel the current running measurement task."
        self._picoStop = True
        if self.measurementTask:
            # FIXME
            # potential risk in calling this function from another thread.
            for t in self.measurementTask.values():
                self.scheduler.cancelTask(t)

            # self.measurementTask = {}
            self.debug('Stopped Pico.')
            # self.main.dataProcess.abortScan()

    @labelForDev
    def getPicoStatus(self,):
        """Return pico task status
        status can be:
            'waiting' : waiting for temperature control to reach goal temp. 
            'running' : measturement is ongoing. 
            'done' : measurement is done. this status won't last, will immediately change to 'idle'.
            'idle' : is idle.
            'chiptype' : chip type currently inserted
            'error' : pico is not corrected connected.
        """
        return {'status': self.picoStatus,
                'remainingTime': max((i.getRemainingTime() for i in self.measurementTask.values() if i), default=0),
                'started': self._testStarted_,
                'reason': self.waitReason}

    @labelForDev
    def chipType(self,):
        """
        return type of chip inserted
        returns 0 for no chip, 6 for fibrinogen, 7 for covid
        """
        return self.pstat.chipType()

    @labelForDev
    def chipInserted(self,):
        """
        return whether chip is inserted.
        True or False
        """
        return self.pstat.chipInserted()

    @labelForDev
    def resetTestStarted(self,):
        """
        set __testStarted to False.
        """
        self._testStarted_ = False
        return 'resetTestStarted'

    @labelForDev
    def fluidFillValue(self, channel: str):
        """
        return the fluidFill detection value in uA.
        channel is C1 - C4.
        """
        return self.pstat.fluidFillValue(channel)

    @labelForDev
    def ResistorChipQC(self,):
        '''
        Run board QC with the resistor QC board.
        '''
        if self.measurementTask:
            return 'Cannot QC. Test is running.'
        self.measurementTask = {1:0}
        time.sleep(1)
        res = self.pstat.resistorChipCheck()
        self.measurementTask = {}

        # if QC passed, disable the devPage.
        if res:
            return f"Resistor QC FAIL: {res}"
        else:
            # disable devPage
            self.main.httpServer.disableHttpDevPage()
            return "Resistor QC PASS"
    
    @labelForDev
    def getVersion(self,):
        "Return the version of the M355 firmware."
        return self.pstat.version
                
    def terminateMeasure(self,reason):
        "terminate all measurement tests, still save the result, the result is sent to LED for display"
        for t in self.measurementTask.values():
            t.done(reason=reason)        
        self.waitReason = None


    def abortMeasure(self,):
        "abort all measurement tests, don't save the result."        
        self.waitReason = None
        self.picoStatus = 'idle'
        self.measurementTask = {}
        self.main.heating.stopTempControl()


    def scanQC(self,fitres):
        """
        determine if a fitting result is acceptable or not
        return True if OK, return False if not OK.
        """
        fx = fitres.get('fx')
        fy = fitres.get('fy')
        pc = fitres.get('pc',0)
        pv = fitres.get('pv')
        err = fitres.get('err',1)
        if pc>2 and pc<70 and err<=0.2:
            return True
        return False
        
    def picoInterupt(self,):
        """
        return True if pico has been interupted.
        """
        if self._picoStop or (not self.measurementTask):
            self.waitReason = None
            return True
        else:
            return False
    
    def createTestRecord(self,meta,pwd):
        "create a test record, for later store result."
        idx = self.main.dataStore.addIndex(meta, pwd)
        self.main.dataProcess.startScan(idx,meta)

    def stopOnChipNotInserted(self):
        """
        return True if chip is not inserted.
        return False if chip is inserted, or if devMode is ON.
        if chip is not inserted, then stop the test, without saving the result.
        """
        if not self.pstat.chipInserted():
            self.waitReason = 'Chip not inserted.'                    
            if self.devMode:
                self.waitReason = 'DevMode Bypass Chip insertion.'
                time.sleep(5)
            else:                        
                # self.main.peripheral.sendMsgToLED('testError')
                self.error(f'startMeasure Stop On Chip not Inserted: {self.waitReason}')
                # if found chip is not inserted, reset the reader.
                self.abortMeasure()                        
                return True
        return False


    @labelForDev
    def startMeasure(self, meta: dict, method: str = 'autoSelect',  pwd: str = "", **kwargs):
        """
        Start measurement with 'autoSelect' pico method. 
        autoSelect means reader will decide which method to use, depends on fluid fill status.
        if 2 channel has fluid fill, will use default-2channel, if 4 channel has fluid fill, will use default - 4channel.
        meta : meta info; see dataStore.addIndex for details.
        method : method name to run. 
        deltaT: temperature difference tolerance before start measure.
        pwd: a string password used to encrypt the data. White space will be trimmed from ends.

        The measurement happens in the following steps: 
            1. meta is added to dataStore, by dataStore.addIndex(meta). This creates a record with meta info. 
            2. Measrument task is initiated. Wait for temperature to reach set goal and tolerance, pico status change to 'waiting'. 
            3. Measrument started. pico status change to 'running'. 
            4. During measurement, each data point is added to dataProcess.appendData() 
            5. When measurement ended, pico status change to 'done' then 'idle'. 
            6. dataProcess.endScan() is called. this will trigger 'positive/negative' call and store the raw data and result in dataStore module.
            7. if exception happens during measurement, or measurement.stopPico is called, dataProcess.abortScan is called. This will dump raw data to dataStore and mark result as 'abort'.
        """
        def covidMeasure():
            "start covid measure"

            self._testStarted_ = True
            self._picoStop = False
            if self.startMeasurementTask:
                self.startMeasurementTask.measureStarted = True

            self.picoStatus = 'waiting'

            # decide the pico method to use by fluid fill status
            # in the future, should use 
            methodToUse = method
            if self.demoMode:
                methodToUse = 'demoFast'
            elif method == 'autoSelect':                
                v1 = self.pstat.fluidFillValue('C2')
                v2 = self.pstat.fluidFillValue('C3')
                if (v1 > self.pstat.FLUID_FILL_THREASHOLD) and (v2 > self.pstat.FLUID_FILL_THREASHOLD):
                    methodToUse = 'covid-4channel'
                else:
                    methodToUse = 'covid-2channel'

            # set the method on pstat
            self.pstat.selectMethod(methodToUse)

            channels = self.pstat.getChannels()

            for c in channels:
                # initialize measurement tasks
                t = CovidTask(main=self.main, pstat=self.pstat,
                              logger=self, channel=c)
                self.measurementTask[c] = t

            fluidFillTasks = []
            for c in channels:
                # initialzie fluid fill task
                ft = FluidFillTask(
                    main=self.main, pstat=self.pstat, logger=self, channel=c)
                fluidFillTasks.append(ft)

            # initialize temperature monitor task
            tmTask = RecordTemperatureTask(
                main=self.main, pstat=self.pstat, logger=self,)

            # chip insertion task
            chipInsertTask = ChipInsertionTask(
                main=self.main, pstat=self.pstat, logger=self,)

            # check chip insertion and fluid fill
            startTimer = time.monotonic()
            
            # if the check failed after 5 minutes, will cancel the test.
            while True:
                # if the tasked is stopped in other thread, stop the test.
                if self.picoInterupt():  
                    return
                
                # if after 30 seconds, all the problems are not resolved,
                # display test error to LED.
                if time.monotonic() - startTimer > 30:
                    self.main.peripheral.sendMsgToLED('testError')
                    self.main.client.notifyBLEClients({'status': 'ok',
                                                       'action': 'measurement.covid.testError',
                                                       'data': {'type': 'covid'}})


                # if has been in the checking loop for more than 5 minutes,
                # break out the checking loop and create a error result
                if time.monotonic() - startTimer > 300:                            
                    break
                
                
                # first check chip insertion
                if self.stopOnChipNotInserted():
                    return
                

                # then check fluid fill                
                fluidfill = self.pstat.fluidFill()
                if fluidfill:
                    self.waitReason = 'No Fluid Fill in ' + ','.join(fluidfill)                    
                    if self.devMode:
                        self.waitReason = 'DevMode Bypass Fluid Fill.'
                        self.main.peripheral.sendMsgToLED('testError')
                        time.sleep(5)
                    else:                        
                        # self.main.peripheral.sendMsgToLED('testError')
                        self.debug(f'startMeasure QC error: {self.waitReason}')
                        time.sleep(3)
                        continue 

                
                # then check whether signal is normal.
                if not self.devMode:
                    abnormalScanChannels = []
                    for channel,t in self.measurementTask.items():
                        v,a,*o = self.pstat.measure(t.channel,lastFit = t.lastFit)
                        fitres = self.main.dataProcess.fitPeak(v,a)
                        t.lastFit = fitres
                        if not self.scanQC(fitres):
                            abnormalScanChannels.append(channel)
                    if abnormalScanChannels:                        
                        self.waitReason = f'{",".join(abnormalScanChannels)} signal abnormal'                        
                        # self.main.peripheral.sendMsgToLED('testError')
                        self.debug(f'startMeasure QC error: {self.waitReason}')
                        time.sleep(2)                        
                        continue                
                break

            if self.picoInterupt():
                return

            # if the check didn't pass in 5minutes, need to give an error test result. 
            if time.monotonic() - startTimer > 300:
                # create test record
                self.createTestRecord(meta,pwd)
                self.terminateMeasure(reason=self.waitReason)
                self.error('startMeasure timeout: failed QC after 300seconds')
                return
            
            # clear LED error before start heating.
            self.main.peripheral.sendMsgToLED('clear')
            startTimer = time.monotonic()
            # check temperature
            goalTemp = self.main.heating.getGoalTemp()
            self.waitReason = f"Wait for Heating to {goalTemp}"
            self.main.client.notifyBLEClients({'status': 'ok',
                                               'action': 'measurement.covid.startedHeating',
                                               'data': {'goalTemp': f"{goalTemp}"}})
            #while (not self.main.heating.temperatureReady):
            #    # check temperature every 3 seconds
            #    time.sleep(3)
            #    # if chip is remove during this period, or stopped Pico in other thread, stop the test without saving.
            #    if self.picoInterupt() or self.stopOnChipNotInserted():
            #        return
            #    
            #    if self.devMode:
            #        # don't wait if in dev mode.
            #        self.waitReason = 'DevMode Bypass Heating.'
            #        startTimer = time.monotonic() - 60
            #        time.sleep(5)
            #        break
            #    
            #    # if temperature is not reached after 5 minutes, stop the test, and record the result.
            #    if time.monotonic() - startTimer >300: 
            #        self.createTestRecord(meta,pwd)
            #        self.terminateMeasure(reason=self.waitReason)
            #        return
            
            # if the 60 seconds is not exhausted, then wait at least the remaining time.
            remainTime = 60 + startTimer - time.monotonic()
            while remainTime > 0:
                time.sleep(3)
                if self.picoInterupt() or self.stopOnChipNotInserted():
                    return                
                remainTime -= 3
            
            # finally create the test record here.
            self.createTestRecord(meta,pwd)
            # start the task
            for t in self.measurementTask.values():
                self.scheduler.addTask(t)

            for t in fluidFillTasks:
                self.scheduler.addTask(t)

            self.scheduler.addTask(tmTask)

            # Don't check chip insertion once started.
            # TODO do we need chip insertion?
            self.scheduler.addTask(chipInsertTask)
            self.waitReason = None

            self.picoStatus = 'running'
            self.main.client.notifyBLEClients({'status': 'ok',
                                               'action': 'measurement.covid.testStartedSuccessfully',
                                               'data': ''})                                      
            return
        
        def fibrinogenMeasure():
            "start fibrinogen measure"
            self._testStarted_ = True
            self._picoStop = False
            if self.startMeasurementTask:
                self.startMeasurementTask.measureStarted = True

            self.picoStatus = 'waiting'

            # assume 2 channel method to check fluid fill on start
            self.pstat.selectMethod('fibrinogen-2channel')

            # make sure fluid is not already in the chip
            if len(self.pstat.fluidFill()) == 0:
                self.main.peripheral.sendMsgToLED('testError')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                       'action': 'measurement.fibrinogen.fluidPrefillError',
                                                       'data': ', '.join(self.pstat.fluidFill())})
                return

            channels = self.pstat.getChannels()

            for c in channels:
                # initialize measurement tasks
                t = FibrinogenTask(main=self.main, pstat=self.pstat,
                              logger=self, channel=c)
                self.measurementTask[c] = t

            fluidFillTasks = []
            for c in channels:
                # initialzie fluid fill task
                ft = FluidFillTask(
                    main=self.main, pstat=self.pstat, logger=self, channel=c)
                fluidFillTasks.append(ft)
            
            # removed temp monitering task, since it is not needed for fibrinogen

            # chip insertion task
            chipInsertTask = ChipInsertionTask(
                main=self.main, pstat=self.pstat, logger=self,)

            # check chip insertion and fluid fill
            startTimer = time.monotonic()

            # if the check failed after 5 minutes, will cancel the test.
            while True:
                # if the tasked is stopped in other thread, stop the test.
                if self.picoInterupt():  
                    return
                
                # if after 30 seconds, all the problems are not resolved,
                # display test error to LED.
                #if time.monotonic() - startTimer > 30:
                #    self.main.peripheral.sendMsgToLED('testError')


                # if has been in the checking loop for more than 5 minutes,
                # break out the checking loop and create a error result
                if time.monotonic() - startTimer > 300:                            
                    break
                
                
                # first check chip insertion
                if self.stopOnChipNotInserted():
                    return
                

                # then check fluid fill                
                fluidfill = self.pstat.fluidFill()
                if fluidfill:
                    self.waitReason = 'No Fluid Fill in ' + ','.join(fluidfill)                    
                    if self.devMode:
                        self.waitReason = 'DevMode Bypass Fluid Fill.'
                        self.main.peripheral.sendMsgToLED('testError')
                        time.sleep(5)
                    else:                        
                        # self.main.peripheral.sendMsgToLED('testError')
                        self.debug(f'startMeasure QC error: {self.waitReason}')
                        self.main.client.notifyBLEClients({'status': 'ok',
                                                            'action': 'measurement.fibrinogen.fluidFillError',
                                                            'data': ''})
                        time.sleep(0.1)
                        continue
                else:
                    break

                
                # then check whether signal is normal.
                if not self.devMode:
                    abnormalScanChannels = []
                    for channel,t in self.measurementTask.items():
                        v,a,*o = self.pstat.measure(t.channel,lastFit = t.lastFit)
                        fitres = self.main.dataProcess.fitPeak(v,a)
                        t.lastFit = fitres
                        if not self.scanQC(fitres):
                            abnormalScanChannels.append(channel)
                    if abnormalScanChannels:                        
                        self.waitReason = f'{",".join(abnormalScanChannels)} signal abnormal'                        
                        # self.main.peripheral.sendMsgToLED('testError')
                        self.debug(f'startMeasure QC error: {self.waitReason}')
                        time.sleep(2)                        
                        continue                
                break

            if self.picoInterupt():
                return

            # if the check didn't pass in 5minutes, need to give an error test result. 
            if time.monotonic() - startTimer > 300:
                # create test record
                self.createTestRecord(meta,pwd)
                self.terminateMeasure(reason=self.waitReason)
                self.error('startMeasure timeout: failed QC after 300seconds')
                return
            
            # decide the pico method to use by fluid fill status
            # this was moved to after fluid fill is detected, since the chip should not have fluid on insertion for fibrinogen
            methodToUse = method
            if self.demoMode:
                methodToUse = 'demoFast'
            elif method == 'autoSelect':                
                v1 = self.pstat.fluidFillValue('C2')
                v2 = self.pstat.fluidFillValue('C3')
                if (v1 > self.pstat.FLUID_FILL_THREASHOLD) and (v2 > self.pstat.FLUID_FILL_THREASHOLD):
                    methodToUse = 'fibrinogen-4channel'
                else:
                    methodToUse = 'fibrinogen-2channel'

            # set the method on pstat
            self.pstat.selectMethod(methodToUse)

            # removed part that waits 60 seconds before starting, since fibrinogen starts immediately after fluid fill
            
            # finally create the test record here.
            self.createTestRecord(meta,pwd)
            self.main.client.notifyBLEClients({'status': 'ok',
                                               'action': 'measurement.fibrinogen.testStartedSuccessfully',
                                               'data': ''})
            # start the task
            for t in self.measurementTask.values():
                self.scheduler.addTask(t)

            for t in fluidFillTasks:
                self.scheduler.addTask(t)

            # Don't check chip insertion once started.
            # TODO do we need chip insertion?
            self.scheduler.addTask(chipInsertTask)
            self.waitReason = None

            self.picoStatus = 'running'                                      
            return


        # do not allow to start another task
        if self.measurementTask:
            self.error(
                'MeasurementModule.startMeasure error: measurement is running.')
            raise RuntimeError('Measurement is running. Please wait...')

        if self.main.dataProcess.dataStoreIndex:
            self.error(
                'MeasurementModule.startMeasure error: Processing result.')
            raise RuntimeError('Processing results. Please wait...')

        if self.main.dataStore.newDataIndex:
            self.error('MeasurementModule.startMeasure error: Storing result.')
            raise RuntimeError('Storing results. Please wait...')
        
        # add the data in startMeasure thread.
        # idx = self.main.dataStore.addIndex(meta, pwd)
        # self.main.dataProcess.startScan(idx,meta)
        chipType = meta.get('chipType','unknown chipType')
        self.debug(f"Start scan: chipType: {chipType}")

        if chipType == 7:
            # self.main.heating.startTempControl()    # only do heating for covid test
            Thread(name='StartMeasure', target=covidMeasure, daemon=True).start()
        else:   # run fibrinogen test by default
            Thread(name='StartMeasure', target=fibrinogenMeasure, daemon=True).start()


        return {'status': 'started'}
