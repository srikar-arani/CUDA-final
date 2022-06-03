from socket import timeout
from app.modules import moduleNameDict 
from app.utils import LoopEventListener,createFolder,labelForDev,systemLogFile
from app.utils.wifi import internet_connected
from app.setup.install import aptpkg, pippkg,autoChangeHostName,SYSTEM_ID,SYSTEM_SERIAL,renameDevice
import app
import subprocess
import requests
import threading 
from threading import Thread
from datetime import datetime
import time
import asyncio
import os,json
from dateutil.parser import parse
try:
    import RPi.GPIO as GPIO
except:
    import warnings 
    warnings.warn('Import Error in mainModule.')


class MainModule(LoopEventListener):
    """
    main module.
    all other modules are started by main module, and have a reference to main module.
        e.g.: heating.main => main module.    
    """
    def __init__(self,**kwargs):
        # the _status is unique to mainModule, it is used to later determine 
        # if need to reboot system or restart main Module if it exits.
        self._status = 'started'

        # always load default settings first
        with open(createFolder('app') / 'defaults/defaultSettings.json','rt') as f:
            self.SETTINGS = self.defaultSETTINGS = json.load(f) 

        # load saved settings
        settingsFolder = createFolder( 'settings') 
        self.settingsFile = settingsFolder / 'systemSettings.json' 
        if  os.path.exists(self.settingsFile):     
            with open(self.settingsFile,'rt') as f:
                self.SETTINGS = json.load(f)
        
        # start a file hander for logs.
        self.fileHandler = systemLogFile('COVID_system.log')

        try:
            super().__init__(fileHandler = self.fileHandler, **self.SETTINGS['main'])
            self.initialize()
        except Exception as e: 
            super().__init__(fileHandler = self.fileHandler, **self.defaultSETTINGS['main'])
            self.initialize()
            self.SETTINGS['main'] = self.defaultSETTINGS['main'].copy()
            self.error(f'<mainModule> starting error: {e}. Used default settings to start.')
        self._startTime = time.monotonic()


    @labelForDev
    def getUpTime(self):
        "return the uptime of device, in seconds"
        return time.monotonic() - self._startTime

    @labelForDev
    def getVersion(self):
        "return system version"
        return app.__version__
    
    @labelForDev
    def getUpdateNote(self):
        "return firmware update note"
        return app.__updateNote__

    @labelForDev
    def getSystemID(self):
        'return system id'
        return SYSTEM_ID
    
    @labelForDev
    def getSystemSerial(self):
        'return system cpu serial number'
        return SYSTEM_SERIAL


    @labelForDev
    def getUpdateNote(self):
        "return system update note."
        return app.__updateNote__

    
    def initialize(self,):
        """
        Initialize main module.
        run some config scripts, 
        then initialize event loop. 
        then load all modules. 
        then start.
        """
        self.debug('+++++++++Starting MainModule+++++++++')
        # this is in the initialize process not sure shat GPIO.cleanup() do. 
        self.checkHostName()        
        try:
            # set up GPIO here because all other module that will initialize GPIO pin
            # are called in this thread.
            GPIO.setmode(GPIO.BCM)
        except Exception as e:
            self.error(f"GPIO set error {e}")
        
        # turn bluetooth to discoverable on.
        # subprocess.run(['sudo', 'hciconfig', 'hci0', 'piscan'])

        # start loop thread.
        # to reuse the loop, use get_event_loop() then start the loop if it is not running.
        self.mainLoop = asyncio.get_event_loop()
        if not self.mainLoop.is_running():
            threading.Thread(name='mainLoopThread',target=self.mainLoop.run_forever,daemon=True).start()
        self.start()         
        self.loadModules() 
    
   
    def checkHostName(self):
        "change hostname and AP name to current device name saved in /boot/device_id.json"
        try:
            changed = autoChangeHostName()
            if changed:
                # if changed hostname, reboot system
                self.critical(f'System Host Name changed to {changed}, NEED TO REBOOT.')
                self.critical('====START REBOOT====.')
                subprocess.run(['reboot'])                
        except Exception as e:
            self.error(f'changeHostName error {e}')
    
    @labelForDev
    def changeHostName(self,name:str):
        """        
        change hostname and AP name to given device name.
        The name is case insensitive. It will be converted to uppercase.
        Need to reboot after name change.
        The full string you typed in will be applied. No prefix is added.
        i.e. you enter -abc, the device will be named as -abc, not ams-abc.
        """
        if len(name)<3:
            return f'{name} is in valid. Must be >3 length.'
        renameDevice(name)
        return f"Device name changed to {name.upper()}"
        
    @labelForDev
    def showLoop(self):
        "show tasks in event loop."
        return str(asyncio.current_task(self.mainLoop))

    @labelForDev
    def showThreads(self):
        "Show running threads."
        return [str(i) for i in threading.enumerate()]

    
    def loadModules(self,):
        "Load all modules"
        orderredModuleName = list(moduleNameDict.keys())
        # need to always start peripheral module first to set wifi mode. 
        # orderredModuleName.remove('peripheral')
        # orderredModuleName.insert(0,'peripheral')
        
        for moduleName in orderredModuleName:
            moduleClass = moduleNameDict[moduleName]
            try:
                moduleClass(fileHandler = self.fileHandler,**self.SETTINGS.get(moduleName,{})).start()
            except Exception as e:
                module = moduleClass(fileHandler = self.fileHandler,**self.defaultSETTINGS.get(moduleName,{}))
                self.SETTINGS[moduleName] = self.defaultSETTINGS.get(moduleName,{}).copy()
                module.start()
                module.error(f"<{moduleName}> starting error: {e}. Used default settings to start, reset settings to default.")

    def run(self):
        """main loop, need to respond to the stop of self.willStop signal.
        other wise need to directly respond to self.stop()"""
        self.register()

        
        while True:
            if self.willStop:
                break 
            try:
                self.scheduler.runNextTask()
            except Exception as e:
                self.error(f"{self}.run: Task Loop {self.scheduler} error: {e}") 
        self.cleanUp()
        self.debug(f"MainModule.run <{self}> exit.")
        self.debug('+++++++++All modules stopped. System Exit.+++++++++')

    def cleanUp(self):
        "Stop every module in mainModule.loadedModules"
        # if is measuring, stop measure so that the data is stored.
        self.measurement.stopPico()
        for moduleName in moduleNameDict:
            module = getattr(self,moduleName)
            module.stop()
        for moduleName in moduleNameDict:            
            module = getattr(self,moduleName)
            module.join()
        # turn off all pins.
        GPIO.cleanup()
        

    
    def saveSystemSettings(self,):
        "Save self.SETTINGS to settings file."
        with open(self.settingsFile,'wt') as f:
            json.dump(self.SETTINGS,f,indent=2)

    @labelForDev
    def getSystemTime(self):
        "return system Time of RPi, in iso format"
        return datetime.now().isoformat()

    @labelForDev
    def syncSystemTime(self,timeString:str=""):
        """
        syncronize system time from a ISO time string.
        if the Pi is connected to internet(by ping google), will sync time with internet.
        Otherwise,
        If a timeString is given, will disable automatic time sync with internet,
        and set the time on Pi to the given time string.
        Date is set with datetimeutil on RPi.
        Recommend use isoTime string:
        2020-10-14T15:07:25.029124
        """
        if internet_connected():
            subprocess.run("sudo systemctl enable systemd-timesyncd".split())
            subprocess.run("sudo systemctl daemon-reload".split())
            subprocess.run("sudo systemctl start systemd-timesyncd".split())
            return "Started syncing time with internet."
        else:
            try:
                time = parse(timeString)
            except:
                return f"Can not parse timeString: [{timeString}]."                        
            time = time.strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run("sudo systemctl stop systemd-timesyncd".split())
            subprocess.run("sudo systemctl disable systemd-timesyncd".split())
            subprocess.run(["sudo", "timedatectl", "set-time", time])
            return f"Set Pi time to {time}"
            

    @labelForDev
    def listModules(self):
        "list all modules."
        return list(moduleNameDict.keys()) + ['main']

    @labelForDev
    def aliveModules(self):
        "list all alive modules."
        return [i for i in self.listModules() if getattr(self,i).is_alive()]
    
    @labelForDev    
    def rebootSystem(self):
        "exit system and reboot raspberry pi"
        self.stop()
        self._status = 'reboot'
        return 'reboot system' 
    
    @labelForDev 
    def restartSystem(self): 
        "restart the app but not the raspberry Pi."
        self.stop()
        self._status = 'restart'
        return 'restart system.'

    @labelForDev 
    def updateGit(self,installRequirements:bool=False):
        """
        Update from git hub. 
        Need to set working dir in supervisor.
        And set up git credentials. 
        Supervisor run as the same user and use sudo.
        if installRequirements = True, will install packages in requirements.txt.
        """
        res = subprocess.run(['git','pull' ],capture_output=True)
        gitres = 'success' if res.returncode==0 else ('error: '+res.stdout.decode())
        pkgres = "Not installed."
        if installRequirements:
            try:
                aptpkg()
                pippkg()
                pkgres = 'success'
            except Exception as e:
                pkgres = f'error: {e}'
        return {'git':gitres,'pkg':pkgres}


        
    @labelForDev
    def restartModules(self,modules:list=[]):
        """
        Restart modules.
        modules: a list of module names to reload. 
        If main is in modules, will directly reload all modules. 
        Otherwise reload individule modules.
        Reload module will take at least 1seconds in a separate thead. 
        Reload order is not guranteed. 
        """
        def _restartModule(moduleName):
            "restart module"
            if moduleName == 'client':
                # wait to send the last message if closing client module.
                time.sleep(1)
            getattr(self,moduleName).stopModule()
            getattr(self,moduleName).startModule()

        if 'main' in modules: 
            self.stop()
            return 'Restarted main module.'
        restarted = []
        for moduleName in modules: 
            if getattr(self,moduleName,None):
                Thread(name='restartModule',target=_restartModule,args=(moduleName,)).start() 
                restarted.append(moduleName)
        return f"Restarted modules: {','.join(restarted)}."

    @labelForDev
    def getLatestVersion(self):
        "return the latest version from github"
        url = 'https://raw.githubusercontent.com/rocksnow1942/covid_sensor_version/main/version.txt'        
        try:
            r = requests.get(url,timeout=1)
            v = r.text.split('\n')[0].strip(' "\n')
            self.debug(f'getLatestVersion {v}')
            return v
        except Exception as e:
            self.debug(f'getLatestVersion error {e}')
            return app.__version__
