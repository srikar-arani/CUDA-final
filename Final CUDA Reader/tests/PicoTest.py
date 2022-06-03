import serial
import numpy as np
import time
import sys
from pathlib import Path  
import os
import json

def createFolder(folder):
    "create path if not exist"
    _folder = Path(__file__).parent.parent/ folder
    if not os.path.exists(_folder):
        os.mkdir(_folder) 
    return _folder

# template for use in raspberry pico
no_channel_template = """e
var c
var p
var f
var r
set_pgstat_chan 0
set_pgstat_mode 3
set_max_bandwidth {Freq*4}
set_pot_range {E_begin} {E_end}
set_autoranging {crMin} {crMax}
cell_on
set_e {E_begin}
wait {waitTime}
meas_loop_swv p c f r {E_begin} {E_end} {E_step} {E_amp} {Freq}
	pck_start
	pck_add p
	pck_add c
	pck_end
endloop
on_finished:
cell_off

"""

measure_channel_template = """e
var c
var p
var f
var r
{setPin}
set_pgstat_chan 0
set_pgstat_mode 3
set_max_bandwidth {Freq*4}
set_pot_range {E_begin} {E_end}
set_autoranging {crMin} {crMax}
cell_on
set_e {E_begin}
wait {waitTime}
meas_loop_swv p c f r {E_begin} {E_end} {E_step} {E_amp} {Freq}
	pck_start
	pck_add c
	pck_end
endloop
on_finished:
cell_off

"""

chip_insert_script = """e
var a
set_gpio_cfg 1 0
set_gpio_pullup 1 1
wait 100m
get_gpio a
pck_start
	pck_add a
	pck_end
    
"""

fluid_fill_template = """e
var c
var p
var f
var r
{setPin}
set_pgstat_chan 1
set_pgstat_mode 2
cell_on
meas_loop_swv p c f r -500m 500m 100m 50m 100
	pck_start
	pck_add c
	pck_end
endloop
on_finished:
cell_off

"""

# control pins to control mux
# the pin need to be in correct order
CONTROL_PIN = [64, 32]  # pin5 , 6


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

# dictionary containing all used var types for MethodSCRIPT
ms_var_types = [{"vt": "aa", "type": "unknown", "unit": " "},
                {"vt": "ab", "type": "WE vs RE potential", "unit": "V"},
                {"vt": "ac", "type": "CE potential", "unit": "V"},
                #{"vt":"ad", "type": "WE potential"        , "unit" : "V" },
                {"vt": "ae", "type": "RE potential", "unit": "V"},
                {"vt": "ag", "type": "WE vs CE potential", "unit": "V"},

                {"vt": "as", "type": "AIN0 potential", "unit": "V"},
                {"vt": "at", "type": "AIN1 potential", "unit": "V"},
                {"vt": "au", "type": "AIN2 potential", "unit": "V"},

                {"vt": "ba", "type": "WE current", "unit": "A"},

                {"vt": "ca", "type": "Phase", "unit": "Degrees"},
                {"vt": "cb", "type": "Impedance", "unit": "Ohm"},
                {"vt": "cc", "type": "ZReal", "unit": "Ohm"},
                {"vt": "cd", "type": "ZImag", "unit": "Ohm"},

                {"vt": "da", "type": "Applied potential", "unit": "V"},
                {"vt": "db", "type": "Applied current", "unit": "A"},
                {"vt": "dc", "type": "Applied frequency", "unit": "Hz"},
                {"vt": "dd", "type": "Applied AC amplitude", "unit": "Vrms"},

                {"vt": "eb", "type": "Time", "unit": "s"},
                {"vt": "ec", "type": "Pin mask", "unit": " "},

                {"vt": "ja", "type": "Misc. generic 1", "unit": " "},
                {"vt": "jb", "type": "Misc. generic 2", "unit": " "},
                {"vt": "jc", "type": "Misc. generic 3", "unit": " "},
                {"vt": "jd", "type": "Misc. generic 4", "unit": " "}]


def Flush(ser):
    """
    Use a while loop to ensure flush all data.
    """    
    ser.write(bytes("\n",  'ascii'))  # write a linefeed to flush
    # blocks the reading until a line break is read.
    res = ser.read_until(bytes("\n", 'ascii')).decode()
    while ser.read_all().decode():                      # read all remaining data.
        time.sleep(0.01)                                # wait 10ms.
    attempt=10
    while res!='\n' and attempt>0:                      # read all remaining data.
        time.sleep(0.01)                                # wait 10ms.
        ser.write(bytes("\n",  'ascii'))  # write a linefeed to flush
        # blocks the reading until a line break is read.
        res = ser.read_until(bytes("\n", 'ascii')).decode()
        attempt -= 1

def IsConnected(ser):   
    ser.write(bytes("t\n",  'ascii'))  # write the command
    response = ser.read_until(bytes("*\n", 'ascii'))  # read until *\n
    response = str(response, 'ascii')  # convert bytes to ascii string
    start = response.find('esp')  # check the presents of "esp" in the repsonse
  
    if start == -1:  # return if string is found
        return False
    return True


def GetResults(ser, timeout=10, emptyout=200):
    "return results as a list of lines, use timeout and max_empty_line to stop."
    results = []
    empty = 0
    t0 = time.monotonic()
    while 1:
        res = ser.readline()
        strline = res.decode('ascii')
        results.append(strline)
        if strline == '\n' or '!' in strline:
            break
        if not strline.strip():
            empty += 1
        if empty > emptyout or (time.monotonic() - t0 > timeout):
            break
    return results


def ValConverter(value, sip):
    return sip_factor.get(sip, np.nan) * value


def ParseVarString(varstr):
    SIP = varstr[7]  # get SI Prefix
    varstr = varstr[:7]  # strip SI prefix from value
    val = int(varstr, 16)  # convert the hexdecimal number to an integer
    val = val - 2**27  # substract the offset binary part to make it a signed value
    return ValConverter(val, SIP)  # return the converted floating point value


def ParseResultsFromLine(res_line):
    lval = list()  # Create a list for values
    lvt = list()  # Create a list for values
    if res_line.startswith('P'):  # data point start with P
        pck = res_line[1:len(res_line)]  # ignore last and first character
        for v in pck.split(';'):  # value fields are seperated by a semicolon
            str_vt = v[0:2]  # get the value-type
            str_var = v[2:2+8]  # strip out value type
            val = ParseVarString(str_var)  # Parse the value
            lval.append(val)  # append value to the list
            lvt.append(str_vt)
    return lval, lvt


def GetValueMatrix(content):
    val_array = [[]]
    j = 0
    for resultLine in content:
        # check for possible end-of-curve characters
        if resultLine.startswith('*') or resultLine.startswith('+') or resultLine.startswith('-'):
            j = len(val_array)  # step to next section of values

        else:
            # parse line into value array and value type array
            vals, _ = ParseResultsFromLine(resultLine)
            # Ignore lines that hold no actual data package
            if len(vals) > 0:
                # If we're here we've found data for this curve, so check that space in allocated for this curve
                # This way we don't allocate space for empty curves (for example when a loop has no data packages)
                if j >= len(val_array):
                    val_array.append([])
                # Add values to value array
                val_array[j].append(vals)
    return val_array


def openSerialPort(comport, logger=None):
    "use proxy for port, so that can auto restart port if problem occur."
    # ser = serial.Serial()
    ser = SerialProxy(
        logger=logger,
        port=comport,  # set the port
        baudrate=230400,  # Baudrate is 230400 for EmstatPico
        bytesize=serial.EIGHTBITS,  # number of bits per bytes
        parity=serial.PARITY_NONE,  # set parity check: no parity
        stopbits=serial.STOPBITS_ONE,  # number of stop bits
        timeout=1,  # timeout block read
        xonxoff=False,  # disable software flow control
        rtscts=False,  # disable hardware (RTS/CTS) flow control
        dsrdtr=False,  # disable hardware (DSR/DTR) flow control
        write_timeout=2,  # timeout for write is 2 seconds
    )
    return ser


def channel_to_pin(channel):
    "convert channel to pin in the multiplexer. channel is C1-C4"
    # get the bitmask for channel.
    pinNum = sum(int(i)*j for i,
                 j in zip(f"{int(channel[1:])-1:02b}", CONTROL_PIN))
    return f"set_gpio_cfg {sum(CONTROL_PIN)} 1\nset_gpio {pinNum}i"


def constructScript(method):
    """
    use channel info to set pins.
    construct method script from settings
    covid-trace method format: {
        'script': method script to send.
        'interval': interval
        'repeats' : repeat how many times
        'duration' : total last measurement time. # whichever happens first.
    }
    """
    # channel = settings.get('channel','C1')
    # setPin = channel_to_pin(channel)
    results = {}
    for channel, settings in method.items():
        setPin = channel_to_pin(channel)
        autoERange = settings.get('Auto E Range', False)
        # E_begin = convert_voltage(settings['E Begin'])
        # E_end = convert_voltage(settings['E End'])

        E_begin = "{E_begin}"
        E_end = "{E_end}"

        assert (settings['E Step'] >= 0.001 and settings['E Step']
                <= 0.1), 'E step out of range'
        E_step = convert_voltage(settings['E Step'])
        assert (settings['E Amp'] > 0.001 and settings['E Amp']
                <= 0.25), 'E Amp out of range.'
        E_amp = convert_voltage(settings['E Amp'])
        Freq = int(settings['Frequency'])
        waitTime = convertUnit(max(settings['Wait time'], 1e-6))
        assert (Freq < 999 and Freq > 5), "Frequency out of range."
        crMin = convert_currange_range(settings['CurrentRange Min'])
        crMax = convert_currange_range(settings['CurrentRange Max'])
        interval = settings['Interval']
        duration = settings['Duration(s)']

        script = eval('f'+repr(measure_channel_template))

        results[channel] = {'interval': interval,
                            'script': script, 'duration': duration, 'autoERange': autoERange,
                            'E_begin': settings['E Begin'], 'E_end': settings['E End']}

    return results


def convertUnit(v):
    "convert value to m, or raw value"
    a = np.abs(v)
    if a < 1e-6:
        return f"{v*1e9:.0f}n"
    elif a < 1e-3:
        return f"{v*1e6:.0f}u"
    elif a < 1:
        return f"{v*1e3:.0f}m"
    elif a < 1e3:
        return f"{v:.0f}"
    elif a < 1e6:
        return f"{v/1e3:.0f}k"
    elif a < 1e9:
        return f"{v/1e6:.0f}M"


def convert_voltage(v):
    assert (v >= -1.61 and v <= 1.81), 'Potential out of range'
    return f"{v*1000:.0f}m"


def convert_currange_range(r):
    "'100 nA','1 uA','10 uA','100 uA','1 mA','5 mA'"
    n, u = r.split(' ')
    return n+u[0]


class SerialProxy():
    "a class to proxy serial port so that it can recover automatically. "

    def __init__(self, logger=None, *args, **kwargs):
        self.logger = logger
        self.ser = serial.Serial(*args, **kwargs)
        self.initArgs = args
        self.initKwargs = kwargs
        self.info = self.logger.info if logger else print
        self.error = self.logger.error if logger else print
        self.debug = self.logger.debug if logger else print

    def __setattr__(self, name, val):
        if name in ['logger', 'ser', 'initArgs', 'initKwargs', 'info', 'error', 'debug']:
            super().__setattr__(name, val)
        else:
            setattr(self.ser, name, val)

    def __getattr__(self, name):
        ""
        res = getattr(self.ser, name)
        if callable(res):
            return self.logDeco(res)
        return res

    def logDeco(self, func):
        "a decorator function"
        def wrapped(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
                return res
            except Exception as e:
                self.error(
                    f'Serial Proxy calling serial port function <{func.__name__}> error. Error: {e}')
            # try reconnect:
            try:
                self.ser.close()
            except Exception as e:
                self.error(f"Serial Proxy close port error. Error: {e}")

            # try reconnect for 2 times. if cannot, raise error.
            try:
                for _ in range(2):
                    self.ser = serial.Serial(*self.initArgs, **self.initKwargs)
                    if IsConnected(self.ser):
                        self.info(
                            f'Serial Proxy reopened serial port after {_+1} attempt.')
                        return getattr(self.ser, func.__name__)(*args, **kwargs)
            except Exception as e:
                self.error(f"Serial Proxy reconnect Failed. Error: {e}")
                raise RuntimeError(
                    'Serial Proxy can not recover the serial port after all attempts.')
        return wrapped


class Pico:
    # FIXME
    # need to refine the threshold with fluid fill script.
    FLUID_FILL_THREASHOLD = 0.05

    def __init__(self, port="/dev/serial0", logger=None):
        self.ser = openSerialPort(port, logger)
        Flush(self.ser)
        self.settings = {}

        # this creates folder under ./app/settings
        settingsFolder = createFolder('settings')
        # by default, store measurement settings in ./app/settings/picoSettings.json
        self.settingsFile = settingsFolder / 'picoSettings.json'

        self.currentMethod = 'default'
        self.currentScript = None

        if logger:
            self.logger = logger
        else:
            class LOG:
                info = debug = error = critical = lambda x: print(x)
            self.logger = LOG

    def initialize(self):
        """
        flush the serial port and test if pico is connected
        if app is started with -dev, then bypass initialization.
        """
        if sys.argv[-1] != '-dev':
            Flush(self.ser)          
            attempt = 1
            # normally, the below part shouldn't be executed.
            while (not self.isConnected):
                self.logger.error(
                    f"Pico Serial port is not open, attempt = {attempt}")
                attempt += 1
                Flush(self.ser)
                if attempt >= 3:
                    self.logger.critical(
                        "Cannot open Pico Serial port after 3 attempt!!!")
                    break

    @property
    def isConnected(self):
        "return True if pico is connected"
        return IsConnected(self.ser)

    def close(self):
        "close serial port"
        self.ser.close()

    def loadSettings(self):
        "Load settings for running measurement."
        defaults = createFolder('defaults') / 'defaultPicoMethod.json'

        # first load custom settings.
        if os.path.exists(self.settingsFile):
            with open(self.settingsFile, 'rt') as f:
                self.settings.update(json.load(f))

        # then load defaults.
        with open(defaults, 'rt') as f:
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

    def methodValidate(self, method: str):
        """
        raise KeyError if method is not in settings.
        if no error is raised, the method is considered usable.
        """
        if method not in self.settings:
            self.logger.error(f'Pico method <{method}> not found')
            raise KeyError(f'Pico method <{method}> not found')

    def chipInserted(self):
        "detect if chip is inserted with GPIO 0"
        try:
            Flush(self.ser)
            self.ser.write(chip_insert_script.encode('ascii'))
            time.sleep(0.05)
            # rawres: ['e\n', 'Pec800009Fi\n', '\n']
            res = GetResults(self.ser)

            # bitmask is an interger. last bit is GPIO 0.
            bitmask = int(ParseResultsFromLine(res[1])[0][0])
            # if last bit is 1, then chip is not inserted.
            return not (bitmask % 2)
        except Exception as e:
            self.logger.error(f'Pico.chipInserted Error: {e}')
            return False

    def fluidFillValue(self, channel: str):
        """
        detect fluid fill in given channel. channel should be C1-C4.
        return current in uA.
        """
        try:
            Flush(self.ser)
            sc = fluid_fill_template.format(setPin=channel_to_pin((channel)))
            self.ser.write(sc.encode('ascii'))
            time.sleep(0.05)
            res = GetValueMatrix(GetResults(self.ser))
            average = sum(i[0] for i in res[0])/len(res[0])
            return average * 1e6
        except Exception as e:
            self.logger.error(f'Pico.fluidFillValue Error {e}')
            return 0

    def fluidFill(self):
        "return channels that have fluid level lower than threshodl."
        channels = self.getChannels()
        fills = [self.fluidFillValue(c) for c in channels]
        return [c for c, f in zip(channels, fills) if f < self.FLUID_FILL_THREASHOLD]

    # below are Measreument specific functions
    # currentMethod is set to a method first.
    def selectMethod(self, method):
        "set the method to use for all running related calculations"
        self.methodValidate(method)
        self.currentMethod = method

        # this currentScript is a dictionary, holding information for setting up the run.
        # different chip may use differnt format.
        self.currentScript = constructScript(self.settings[method])

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
        if self.currentScript[channel]['autoERange']:
            if lastFit and (lastFit.get('err') == 0):
                peakvoltage = lastFit.get('pv')
                gap = (self.currentScript[channel]['E_end'] -
                       self.currentScript[channel]['E_begin'])/2
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
        E_begin = convert_voltage(scanRange[0])
        E_end = convert_voltage(scanRange[1])
        return script.format(E_begin=E_begin, E_end=E_end)

    def measure(self, channel: str, lastFit: dict):
        """
        measurement attempt; if success return result, return None otherwise.
        lastFit is a dictionary containing fitting result of last scan.
        lastFit: {pv: peak voltage, err: 0 (no error in fitting) or 1 (error)}
        if this is first scan, lastFit is None.
        """
        Flush(self.ser)
        # generate new script based on last fit data.
        scanRange = self.getScanRange(channel, lastFit)
        sc = self.getScript(channel, scanRange)

        self.ser.write(sc.encode('ascii'))
        # sleep briefly before pulling the result.
        time.sleep(0.05)
        results = GetResults(self.ser, timeout=10, emptyout=20)
        valMatrix = GetValueMatrix(results)

        # only return amp from pico measurement.
        amp = [i[0] * 1e6 for i in valMatrix[0]]  # convert to uA
        # voltage will return the scan range and length of amp.
        voltage = list(scanRange) + [len(amp)]
        return voltage, amp

    # testing funcitons
    def runScript(self, script, parseValue=False):
        "run given script and return results."
        Flush(self.ser)
        self.ser.write(script.encode('ascii'))
        time.sleep(0.05)
        results = GetResults(self.ser, timeout=10, emptyout=20)
        if parseValue:
            return results, GetValueMatrix(results)
        return results

    def openChannelScript(self, channel):
        "construct script to open a given channel"
        sc = channel_to_pin(channel)
        return "e\n{}\n\n".format(sc)

    def channelSWVScript(self, channel):
        if not self.currentScript:
            self.selectMethod('default')
        return self.getScript(channel, self.getScanRange(channel))

    def openChannel(self,channel):
        "open multiplexer channel"
        sc = self.openChannelScript(channel=channel)
        self.logger.debug(sc)
        return self.runScript(sc,parseValue=False)

    def scanChannel(self,channel,parameters={}):
        "scan a given channel with default parameters"
        defaultParam = {
        "Auto E Range": True,
        "E Begin": -0.6,
        "E End": 0.0,
        "E Step": 0.002,
        "E Amp": 0.05,
        "Frequency": 100.0,
        "Wait time": 0.2,
        "Interval": 20.0,
        "Duration(s)": 3600.0,
        "CurrentRange Min": "100 uA",
        "CurrentRange Max": "100 uA"
        }
        defaultParam.update(parameters)
        sc = constructScript({channel:defaultParam})[channel]['script']        
        E_begin = convert_voltage(defaultParam['E Begin'])
        E_end = convert_voltage(defaultParam['E End'])
        sc = sc.format(E_begin=E_begin, E_end=E_end)
        self.logger.debug(sc)
        _,valMatrix = self.runScript(sc,parseValue=True)
        amp = [i[0] * 1e6 for i in valMatrix[0]]  # convert to uA
        # voltage will return the scan range and length of amp.
        voltage = np.linspace(defaultParam['E Begin'],defaultParam['E End'],len(amp))
        return voltage, amp

    def resistorChipCheck(self):
        "run check with a resistor dummpy chip"
        sc = """e
var c
var p
var f
var r
{setPin}
set_pgstat_chan 0
set_pgstat_mode 3
set_max_bandwidth 400
set_autoranging 100u 100u
cell_on
meas_loop_swv p c f r -800m -200m 20m 50m 100
	pck_start
	pck_add p
	pck_add f
	pck_add r
	pck_end
endloop
on_finished:
cell_off

"""       
        channels = ['C1','C2','C3','C4']
        text = []
        for channel in channels:          
            setPin=channel_to_pin(channel)
            res = self.runScript(sc.format(setPin=setPin),parseValue=True)           
            p = np.array([i[0] for i in res[1][0]])
            f = np.array([i[1] for i in res[1][0]]) + 1e-12
            r = np.array([i[2] for i in res[1][0]]) + 1e-12
            Rr = np.array(p) / np.array(r) 
            Rf = (np.array(p)+0.1) / np.array(f)  
            Rravg = Rr.mean()
            Rfavg = Rf.mean()
            RrCV = Rr.std(ddof=1) / Rravg
            RfCV = Rf.std(ddof=1) / Rfavg
            Rcalc =(Rravg+Rfavg)/2           
            text.append(f'{channel} - Avg Resistance: {Rcalc:.4g} Ohm, Forward CV: {RfCV:.2%}, Reverse CV: {RrCV:.2%}')
        return '; '.join(text)


if __name__ == '__main__':         
    # create a new instance of the Picoscope
    ps = Pico()
    ps.initialize()
    print(f'Pico is {"" if ps.isConnected else "NOT "}connected.')
   
