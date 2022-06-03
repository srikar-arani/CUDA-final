import serial
import numpy as np
import time
import sys
import os
import json
from threading import Lock
from pathlib import Path  



# dictionary list for conversion of the SI prefixes
sip_factor = {
    'a': 1e-18,
    'f': 1e-15,
    'p': 1e-12,
    'n': 1e-09,
    'u': 1e-06,
    'm': 0.001,
    ' ': 1.0,
    'i': 1.0,
    'k': 1000.0,
    'M': 1000000.0,
    'G': 1000000000.0,
    'T': 1000000000000.0,
    'P': 1000000000000000.0,
    'E': 1e+18,
}



def createFolder(folder):
    "create path if not exist"
    _folder = Path("/covid_sensor") / folder
    if not os.path.exists(_folder):
        os.mkdir(_folder) 
    return _folder

class PstatMixins:
    def loadSettings(self):
        "Load settings for running measurement."
        defaults = createFolder('app') / 'defaults/defaultPicoMethod.json'

        # first load defaults.
        with open(defaults, 'rt') as f:
            self.settings.update(json.load(f))


        # then load custom settings.
        if os.path.exists(self.settingsFile):
            with open(self.settingsFile, 'rt') as f:
                self.settings.update(json.load(f))
       
        # if settingsFile is not created, load default settings from ./app/defaults/defaultPicoMethod.
        # add default settings in a different file for other Pstat.

    def getMethod(self, method):
        "return settings json"
        if method:
            return self.settings.get(method, {})
        else:
            return self.settings

    def setMethod(self, method, settings):
        "set settings json"
        if method and settings:
            self.settings.update({method: settings})
            # save current settings file
            with open(self.settingsFile, 'wt') as f:
                json.dump(self.settings, f)
            return f"Method <{method}> saved."
            
        elif method in self.settings:
            self.settings.pop(method)
            with open(self.settingsFile, 'wt') as f:
                json.dump(self.settings, f)
            return f"Method <{method}> deleted."
        
    def deleteMethod(self,method):
        "delete method in settings json"
        self.settings.pop(method,None)
        with open(self.settingsFile, 'wt') as f:
                json.dump(self.settings, f)
        return f"Method <{method}> deleted."


    def methodValidate(self, method: str):
        """
        raise KeyError if method is not in settings.
        if no error is raised, the method is considered usable.
        """
        if method not in self.settings:
            self.logger.error(f'Method <{method}> not found')
            raise KeyError(f'Method <{method}> not found')




class M355(PstatMixins):
    FLUID_FILL_THREASHOLD = 0.1
    def __init__(self,port='/dev/serial0',logger=None):
        self.logger= logger 
        # self.ser = SerialProxy(
        #     logger=logger,
        #     port=port,  # set the port
        #     baudrate=115200,  # Baudrate is 230400 for EmstatPico
        #     bytesize=serial.EIGHTBITS,  # number of bits per bytes
        #     parity=serial.PARITY_NONE,  # set parity check: no parity
        #     stopbits=serial.STOPBITS_ONE,  # number of stop bits
        #     timeout=1,  # timeout block read
        #     xonxoff=False,  # disable software flow control
        #     rtscts=False,  # disable hardware (RTS/CTS) flow control
        #     dsrdtr=False,  # disable hardware (DSR/DTR) flow control
        #     write_timeout=2,  # timeout for write is 2 seconds
        # )
        self.ser = serial.Serial(          
            port=port,  # set the port
            baudrate=115200,  # Baudrate is 230400 for EmstatPico
            bytesize=serial.EIGHTBITS,  # number of bits per bytes
            parity=serial.PARITY_NONE,  # set parity check: no parity
            stopbits=serial.STOPBITS_ONE,  # number of stop bits
            timeout=1,  # timeout block read
            xonxoff=False,  # disable software flow control
            rtscts=False,  # disable hardware (RTS/CTS) flow control
            dsrdtr=False,  # disable hardware (DSR/DTR) flow control
            write_timeout=2,  # timeout for write is 2 seconds
        )
        self.settings = {}
        self.picoLock = Lock()
        
        # custom M355 script settings: need to remove in future.
        settingsFolder = createFolder('settings')
        self.settingsFile = settingsFolder / 'picoSettings.json'
        self.currentMethod = 'default'
        self.currentScript = None
        if logger:
            self.logger = logger
        else:
            class LOG:
                info = debug = error = critical = lambda x: print(x)
            self.logger = LOG
    def _write(self,string):
        # print(f'{time.monotonic():10.2f} write:',string)
        self.ser.write(string.encode())
    def _read(self):
        return self.ser.read_all()        
    def close(self):
        self.ser.close()
    def _flush(self):        
        res = self._read()
        while res:            
            time.sleep(0.05)
            res = self._read()
    def json(self,data,timeout=10):
        """
        Always use json method to read and write data to M355.
        if didn't get data before timeout, return {error:}.
        """
        if not self.picoLock.acquire(timeout=timeout):
            self.logger.critical(f"M355.json timeout cannot acquire lock: {data}")
            return {"error": 1}       
        res = 'not started'
        try:
            self._flush()            
            self._write(self._encode(data))            
            res = self._read_until('*') 
            result = json.loads(res)
        except Exception as e:
            self.logger.critical(f"M355.json error:{e}, cmd={data}, data = {res[-50:]}")
            result = {'error': 2}
        self.picoLock.release()        
        return result
        
    def _encode(self,data):
        return (json.dumps(data,separators=(',',':')) + '*')
        
    def _read_until(self,char='*',timeout=10):
        res = ''
        t0=time.monotonic()
        while 1:
            d = self.ser.read_all().decode()            
            if d:
                res += d
                if d[-1]==char:
                    break
            time.sleep(0.1)
            if time.monotonic() - t0 > timeout:                
                break
        return res[0:-1] # remove the last '*' character

    def initialize(self):
        ""
        try:
            res = self.json({'s':1})
            if not res.get('a'):
                self.logger.error(f'M355 status is not ready: {res}')
        except Exception as e:       
            self.logger.error('M355 initialization error')

    @property
    def isConnected(self):
        "return 1 if pico is connected, else return 0"
        return (self.json({'s':1})).get('a',0)
        
    def chipInserted(self):
        """
        check if chip is inserted with GPIO, this method need to raise exception,
        so that caller will know the pstat is not communicating.
        """
        res = self.json({'cI':0})
        if res.get('error',None):
            raise RuntimeError('M355.chipInserted error')
        return res.get('cI',0)
        
    def fluidFillValue(self,channel:str):
        """
        return the fluid fill valude for a channel C1 - C4.
        if error in M355, return 0.
        """
        ch = int(channel[1]) - 1
        res = self.json({"vS":-600,"vE":0,"vI":50,"vA":100,"Hz":100,"iS":100,"vP":-600,"tP":1,"f":0,"r":0,"ch":ch,"ps":1})
        return np.array(res.get('c',[0])).mean()
            
    def fluidFill(self):
        "return channels that have fluid level lower than threshodl."
        channels = self.getChannels()
        fills = [self.fluidFillValue(c) for c in channels]
        return [c for c, f in zip(channels, fills) if f < self.FLUID_FILL_THREASHOLD]
    
    def selectMethod(self, method):        
        self.methodValidate(method)
        self.currentMethod = method        
        self.currentScript = {}
        for channel, settings in self.settings[method].items():
            iS = settings['CurrentRange Max']
            iS = int(iS.split(' ')[0]) * 1e6 * sip_factor.get(iS.split(' ')[1][0], 1)
            self.currentScript[channel] = {
                'interval':settings['Interval'],
                'duration':settings['Duration(s)'],
                'autoERange':settings.get('Auto E Range', False),
                'E_begin': settings['E Begin'], 'E_end': settings['E End'],
                'script': dict(                    
                    vS=settings['E Begin']*1000,
                    vE=settings['E End']*1000,
                    vI=max(settings['E Step'], 0.005)*1000, # avoid using step smaler than 5mV
                    # amplitude need to be doubled for M355 to match Pico. 
                    # on Pico, 50mV amplitude is 100mV on M355
                    vA=settings['E Amp']*2000, 
                    Hz=int(settings['Frequency']),
                    iS=iS, #uA
                    vP=settings['E Begin']*1000,
                    tP=settings['Wait time']*1000,
                    f=0, # flag for forward current
                    r=0,
                    ch = int(channel[1]) -1 ,     #   mux select pins (0-3)
                    ps=0 #potentiostat 0
                )
            }

    def getChannels(self,):
        "get the channels in selected method"
        return list(self.currentScript.keys())

    def getInterval(self, channel):
        'return scan interval in seconds for given channel'
        return self.currentScript[channel]['interval']

    def getRemainingTime(self, startTime, channel, isRunning):
        """
        calculate remaining run time given runCount scans is already done.
        if isRunning == False, then measurement is waiting for heating.
        Measurement haven't started. So it should the total time without substract the elapsed time.
        """
        # get the max total duration.
        totalTimeByTime = self.currentScript[channel].get('duration', 9999999)
        if not isRunning:
            return totalTimeByTime
        timeByTime = totalTimeByTime - (time.monotonic() - startTime)
        return timeByTime

    
    def getScanRange(self, channel, lastFit=None):
        "the voltage returned is V (not mV), this voltage is used for the next scan"
        if self.currentScript[channel]['autoERange']:
            if lastFit and (lastFit.get('err') < 0.5):
                peakvoltage = lastFit.get('pv')
                gap = (self.currentScript[channel]['E_end'] -
                       self.currentScript[channel]['E_begin'])/2                
                # limit peak voltage range to 0.1 to 0.4
                peakvoltage =min( 0, max(peakvoltage,-0.4))                
                estart = peakvoltage - gap
                eend = peakvoltage + gap
                if estart >= -1.61 and eend <= 1.81:
                    return estart, eend
        return (self.currentScript[channel]['E_begin'],
                self.currentScript[channel]['E_end'])
    
    def getScript(self, channel, scanRange):
        "Update script based on last fitresult if needed."
        # this is a helper method for measure. Not necessary if not doing autoRange.
        script = self.currentScript[channel]['script']        
        script['vS'] = int(scanRange[0] * 1000)
        script['vE'] = int(scanRange[1] * 1000)
        return script

    def measure(self, channel: str, lastFit: dict):
        """
        measurement attempt; if success return result, return None otherwise.
        lastFit is a dictionary containing fitting result of last scan.
        lastFit: {pv: peak voltage, err: 0 (no error in fitting) or 1 (error)}
        if this is first scan, lastFit is None.
        """
      
        # generate new script based on last fit data.
        scanRange = self.getScanRange(channel, lastFit)
        sc = self.getScript(channel, scanRange)        
        results = self.json(sc)       
        # the current returned are in the unit of uA
        # fCurrent = results.get('f')
        # rCurrent = results.get('r')        

        # I have to flip the sign here, I don't know why, it 
        # was positive in some measurements I didn't before, but on 6/14, I saw it negative.        
        # later when I restart everythin, the data is not flipped anymore.
        # 6/24/2021 after changed to Fermi's code, the subtract current is negative again. SO I do the flip again.
        # 6/30/2021 I figured out the sign is flipped in the C code during data processing. Now the sign of subtract current should be correct.
        # sCurrent = [-i for i in results.get('subtractCurrent')]
        sCurrent = results.get('c',[])

        # only return amp from pico measurement.
        amp = sCurrent
        # voltage will return the scan range and length of amp.
        voltage = list(scanRange) + [len(amp)]
        return voltage, amp

    def runTest(self,para):
        ""
        results = self.json(para)
        sCurrent = results.get('c',[])

        # only return amp from pico measurement.
        amp = sCurrent
        # voltage will return the scan range and length of amp.        
        return [], amp


        

    def resistorChipCheck(self):
        "run check with a resistor dummpy chip"
        para=dict(            
            vS=-600,
            vE=-100,
            vI=5,
            vA=200,
            Hz=100,
            iS = 100,            
            vP=-600,
            tP = 0,
            f=1, # flag for forward current
            r=1,
            ps=0,
            ch=0
            ) # flag for forward current
        text = []
        resistors = [10,22,33,47]
        for channel in range(4):          
            para['ch'] = channel
            res = self.json(para)  
            f = np.array(res['f'])  + 1e-12        
            v = np.linspace(-600,-100,len(f))
            Rf = v / f           
            Rfavg = Rf.mean()           
            RfCV = Rf.std(ddof=1) / Rfavg
            if abs(Rfavg - resistors[channel]) / resistors[channel] > 0.1 :
                text.append(f'C{channel} - Avg Resistance: {Rfavg:.2f} kOhm, Forward CV: {RfCV:.2%}')
        return '; '.join(text)


import time



if __name__ == '__main__':
    m = M355()
    m.initialize()
    print(f'M355 connected? {m.isConnected}')
    m.loadSettings()
    m.selectMethod('default-4channel')
    vsRange = list(range(-700,-300,7))
    counter = 0
    while 1:     
        vS = vsRange[counter]
        vE = vS + 599
        t0 = time.perf_counter()
        v,a = m.runTest({'vS': vS, 'vE': vE, 'vI': 5.0, 'vA': 100.0, 'Hz': 100, 'iS': 100.0, 'vP': vS, 'tP': 10.0, 'f': 0, 'r': 0, 'ch': 0, 'ps': 0})            
        dt = time.perf_counter()  - t0
        print(f'vS = {vS}, dT = {dt:.2f}s, lenA: {len(a)}, avgA: {sum(a)/max(1,len(a)):.2f}')                 
        time.sleep(.1)
        counter += 1
        if counter >= len(vsRange):
            counter = 0