from app.utils import LoopEventListener,Task ,labelForDev,readJsonFile,writeJsonFile,createFile
from app.utils.wifi import wifi_connected
import subprocess
try:
    import RPi.GPIO as GPIO 
except:
    import warnings 
    warnings.warn('Import error in peripheralModule.')
import time
from threading import Thread 
from collections import deque
from functools import partial
from queue import Queue
from collections import namedtuple

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

# switch servce by 
#  sudo systemctl start wpa_supplicant@ap0.service
#  sudo systemctl start wpa_supplicant@wlan0.service

# enable service 
# systemctl enable wpa_supplicant@wlan0.service
# systemctl disable wpa_supplicant@ap0.service

# restart by (possibly?)
#  sudo systemctl restart wpa_supplicant@wlan0.service

# button debounce:
# add a 0.1uF capacitor accross switch. 

# scan :
# sudo iwlist wlan0 scan

# set priority to network by
# setting priority=10, higher number means higher priority. 

class BtnEventListener():
    "a button input event"
    _dbclick_threshold = 1 
    _hold_threshold = 4
    _long_hold_threshold = 10
    
    def __init__(self,target,pin,logger,pull_up_down):
        self.target = target # target is the button name.
        GPIO.remove_event_detect(pin)
        GPIO.add_event_detect(pin, GPIO.BOTH, bouncetime=100)
        GPIO.add_event_callback(pin,self.callback)
        self.logger = logger

        if pull_up_down == GPIO.PUD_UP:
            self._ACTION = {1:'keyup',0:'keydown'}
        elif pull_up_down == GPIO.PUD_DOWN:
            self._ACTION = {0:'keyup',1:'keydown'}
        else:
            self.logger.error(f'Event undefined pull_up_down {pull_up_down}')
        
        # hisstory is: button_state, button_time,button_action
        self.history = deque([((1,time.monotonic(),None)),(1,time.monotonic(),'keyup')],maxlen=50)
    def __repr__(self):
        return f"Btn <{self.target}>-<{self.action}> on {self.time:.2f}."
    @property
    def action(self):
        return self.history[-1][-1]
    @property
    def time(self):
        return self.history[-1][-2]

    def callback(self,pin):
        # debounce inaddition to debounce
        time.sleep(0.01)

        state = GPIO.input(pin) 
        action = self._ACTION[state]
        t = time.monotonic()
        _,pprevT,pprevA = self.history[-2]
        _,prevT,prevA = self.history[-1] 
        
        # if the action is the same as previous action, then ignore this button event.. 
        # or if the action is button up, but previous action is not botton down,
        if action == 'keyup' and prevA!='keydown':
            return
        elif action == prevA:
            return 

        self.history.append((state, t, action)) 

        # self.logger.led.show('sys',[1],1,init=not state)
        self.logger.sendMsgToLED(f'btn.{action}')        
        # define events
        if prevA == 'keydown' and action =='keyup':
            # long hold event
            if  t - prevT > self._long_hold_threshold:
                self.history.append((state, t, 'long-hold'))
                self.logger.onBtnEvent(self)
            #  hold event
            elif t - prevT > self._hold_threshold:
                self.history.append((state, t, 'hold'))
                self.logger.onBtnEvent(self)
            else:
                # append single click event to event.
                self.history.append((state,t,'click')) 
                
                # define double click event
                if pprevA == 'click' and (t-pprevT)< self._dbclick_threshold:
                    self.history.append((state,t,'dbclick'))
                self.logger.onBtnEvent(self)
                

class WifiService():
    """
    wifiConfig is used to save wifi settings.
    format: {
        ssid:{psk, priority, key_mgmt, ssid, succeed:True or False}
    }
    """
    def __init__(self,logger):
        self.logger=logger
        self.wifipath = "/etc/wpa_supplicant/wpa_supplicant-wlan0.conf" 
        self._wifistatus = None
        # self.wifiSettingsFile = createFile('settings/wificonfig.json')
        # self.wifiConfig = readJsonFile(self.wifiSettingsFile)
        self.availableWifiList = {"timeStamp": time.monotonic(),'wifi':[]}

    def initialize(self,timeout=60):
        "initialzie wifi"
        t0 = time.monotonic()
        while True: 
            if time.monotonic() - t0 > timeout:
                self.logger.error(f'WifiService initialize timeout - {timeout}s. Enable AP.')
                self.enableAP()                
                time.sleep(5)                
                return 
            status = self.status
            if status=='client' and wifi_connected():
                self.logger.debug(f'WifiService <client> initialized after {time.monotonic()-t0:.2f} seconds.')
                return 
            elif status=='ap':
                self.logger.debug(f'WifiService <ap> initilaized after {time.monotonic()-t0:.2f} seconds.')
                return 
            else: 
                self.logger.debug(f"Waiting for WifiService initialize... status: <{status}>")
            time.sleep(3)

    @property
    def status(self):
        "check the status of wifi service"
        if self._wifistatus in ['ap','client']:
            return self._wifistatus
        w = subprocess.run(['systemctl', 'is-active', 'wpa_supplicant@wlan0'],capture_output=True)
        a = subprocess.run(['systemctl', 'is-active', 'wpa_supplicant@ap0'],capture_output=True)
        if w.stdout.decode().strip() == 'active':
            self._wifistatus = 'client'
        elif a.stdout.decode().strip() == 'active':
            self._wifistatus = 'ap'
        else:
            self._wifistatus = 'Unknown Status'
            self.logger.error(f"Weird wifi status wlan0:{w.stdout.decode().strip()}, ap:{a.stdout.decode().strip()}")
        return self._wifistatus
    
    @property
    def ssid(self):
        "return the ssid wifi connected to"
        p = subprocess.run(['iwgetid','wlan0'],capture_output=True)
        return p.stdout.decode().split(':')[1].strip()[1:-1]
    
    def scanWifi(self):
        p = subprocess.run(['iwlist', 'wlan0','scan', ],capture_output=True)
        result = p.stdout.decode().strip().split('\n')
        ssids = {}
        for idx in range(len(result)):
            if result[idx].strip().startswith('Cell'):
                ssid = result[idx+5].strip().split(':')[1][1:-1]
                if ssid: 
                    quality,signal = result[idx+3].strip().split('Quality=')[1].split('Signal level=')
                    quality = quality.strip()
                    ssids[ssid] = dict(
                    ssid=ssid,
                    address = result[idx].strip().split('Address:')[1].strip(),
                    channel = result[idx+1].strip().split(':')[1],
                    frequency = result[idx+2].strip().split(':')[1],
                    quality = quality,
                    signal = signal,
                    encryption = result[idx+4].strip().split(':')[1])
        if not ssids: self.logger.debug(f'scan wifi no result: Rawoutput: <{result}>.')
        self.availableWifiList['wifi'] = ssids
        self.availableWifiList['timeStamp'] = time.monotonic()
        return ssids
    
    def getWifiList(self):
        "scan wifi and return list. if there is a recent scan, then dont run scan, to save time."
        if (time.monotonic() - self.availableWifiList['timeStamp'] < 300) and self.availableWifiList['wifi']:
            return self.availableWifiList['wifi']
        else:
            return self.scanWifi()
        

    def setMode(self,mode):
        if mode == 'client':
            self.enableClient()
        else:
            self.enableAP()

    def enableAP(self):
        "enable AP mode"
        subprocess.run(['systemctl', 'enable', 'wpa_supplicant@ap0.service'])
        subprocess.run(['systemctl', 'disable', 'wpa_supplicant@wlan0.service'])
        subprocess.run(['systemctl', 'start', 'wpa_supplicant@ap0.service'])        
        self.logger.debug('Switched to <AccessPoint> mode.')
        # reset _wifistatus
        self._wifistatus = None

    def enableClient(self):
        subprocess.run(['systemctl', 'enable', 'wpa_supplicant@wlan0.service'])
        subprocess.run(['systemctl', 'disable', 'wpa_supplicant@ap0.service'])
        subprocess.run(['systemctl', 'start', 'wpa_supplicant@wlan0.service'])        
        self.logger.debug('Switched to <Client> mode.')
        self._wifistatus = None

    def readWifiSettings(self):  
        """
        read wifi settins from wpa_supplicant-wlan0.conf file
        return list of {ssid,psk,priority}
        """
        try:
            with open(self.wifipath,'r') as f:
                data = f.readlines()
        except:
            self.logger.error(f'Failed to read wifi settings from {self.wifipath}')
            # return a default settings file
            return ["country=US","ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev","update_config=1"],[]
        header = []
        wifi = []
        networkStart = False
        for k, outer_line in enumerate(data):            
            if outer_line.strip().startswith('network='):
                networkStart = True
                network = {}
                for line in data[k+1:]:
                    if line.strip().startswith('}'):
                        break
                    fields = line.strip().split('=')
                    if len(fields) == 2:
                        network[fields[0]] = fields[1].strip('"')
                wifi.append(network)
            else:
                if not networkStart:
                    header.append(outer_line)                    
        return header, wifi

    def writewifiSettings(self,header,wifi):
        data = [i.strip() for i in header]
        for network in wifi:
            data.append('network={')
            for key,value in network.items():                                    
                if key in ['psk', 'ssid']: # add quotes around psk and ssid
                    data.append(f'{key}="{value}"')
                else:
                    data.append(f'{key}={value}') 
            data.append('}')
        with open(self.wifipath,'w') as f:
            f.write('\n'.join(data))
            f.write('\n')

    def listSavedWifi(self):
        return self.readWifiSettings()[1]
    
    def updateWifiPassword(self,ssid,psk):
        "update a existing known ssid and psk"
        header, wifi = self.readWifiSettings()
        for network in wifi:
            if network['ssid'] == ssid:
                network['psk'] = psk
                break
        self.writewifiSettings(header,wifi)
        self.logger.debug(f'Updated wifi password for {ssid}')


    def setWifiPassword(self,ssid,pwd):
        "write a ssid, pwd to the wpa_supplicant-wlan0; if pwd is empty, then use none key_mgmt"
        # if len(pwd)<8 or len(pwd)>64:
        #     return        
        header, wifi = self.readWifiSettings()
        # remove the priority field for all ssids and remove the ssid if it exists
        wifi  = list(map(lambda x:{k:i for k,i in x.items() if k!='priority'} , filter(lambda x: x['ssid']!=ssid, wifi)))
        newconfig = {"ssid":ssid}
        if pwd and pwd.strip():
            newconfig['psk'] = pwd.strip()
        else:
            newconfig['key_mgmt'] = 'NONE'
        wifi.insert(0,newconfig)
        self.writewifiSettings(header,wifi)
        # now only allow on wifi and password saved.
        # self.writewifiSettings(header,[(ssid,pwd)])
    
    def setWifiPriority(self,ssid):
        "set one of the wifi to higher priority"
        header, wifi = self.readWifiSettings()
        for network in wifi:
            if network['ssid'] == ssid:
                network['priority'] = '1'
            else:
                network.pop('priority',None)
        self.writewifiSettings(header,wifi)
        
    def removeWifiPassword(self,ssid):
        ""
        header, wifi = self.readWifiSettings()
        wifi  = list(filter(lambda x: x['ssid']!=ssid, wifi))        
        self.writewifiSettings(header,wifi)

    def restartWifi(self):
        "restart the client wlan service"
        subprocess.run(['systemctl', 'restart', 'wpa_supplicant@wlan0.service'])
        self.logger.debug('Restart wifi.')


class LED():
    "controller for a single led; use GPIO on and off to control the LED."
    def __init__(self,*args,max_b=65535,FPS=24):
        """
        initialize LED by giving the 3 pin GPIO number in R,G,B order.
        max_b is the maximum brightness of the LED that can be set [0, 65535]
        """
        self.pins = args
        self.max_b = max_b
        self._FPS = FPS
        self.colorGenerator = None
        self.tempGenerator = None
    
    def __iter__(self):
        return iter(self.pins)

    def RGB(self,color,bright=1):
        "convert a color name to RGB tuple"
        "bright is the brightness from [0, 1]"
        o = 65535
        b = o - int(bright*self.max_b)
        return {
            'red':(b, o, o),
            'green':(o, b, o),
            'blue':(o, o, b),
            'white':(b, b, b),
            'black':(o, o, o),
            'cyan':(o, b, b),
            'yellow':(b, b, o),
            'purple':(b, o, b)
        }.get(color,(o, o, o))

    def hold(self,color,seconds=-1,bright=1):
        "hold at one color."
        rgb = self.RGB(color,bright)
        steps = int(seconds * self._FPS)
        if steps==0:return
        while 1:
            yield rgb
            steps -= 1
            if steps==0:return
    
    def ramp(self,color1,color2,bright1=1,bright2=1,seconds=-1):
        "smoothly transition between colors"
        return self.rampHelper(self.RGB(color1,bright1),self.RGB(color2,bright2),seconds)
    
    def rampHelper(self,state1,state2,seconds=-1):
        "smoothly transition between states"
        steps = int(seconds*self._FPS)
        rStep = (state2[0] - state1[0])/steps
        gStep = (state2[1] - state1[1])/steps
        bStep = (state2[2] - state1[2])/steps
        r = state1[0]
        g = state1[1]
        b = state1[2]

        while steps >= 0:
            yield (int(r), int(g), int(b))
            r += rStep
            g += gStep
            b += bStep
            steps -= 1


    def blink(self,colors,times,brights=0):
        "ramp the LED between different colors for differnt times"
        "starts by ramping from the last color to the first"
        count = len(colors)
        if brights == 0:
            brights = [1]*count # default to max brightness
        for i in range(count):
            yield from self.ramp(colors[(i-1)%count], colors[i], brights[(i-1)%count], brights[i], times[i])

    def combine(self,*cG):
        for i in cG:
            yield from i

    def repeat(self,methods,args,repeat=0):
        if isinstance(methods,str):
            methods = [methods]
            args = [args]
        while True:
            yield from self.combine(*[getattr(self,m)(*a) for m,a in zip(methods,args)])
            repeat -=1
            if repeat==0:
                return

    def fade(self,generator):
        """
        fade into the next generator.
        combines a ramp from the current state to black over 0.5s with the next generator to be used
        """
        return self.combine(self.rampHelper(self.nextColor(),self.RGB('black'),0.5),generator)
   
    def picoRunning(self,led=2):
        "status for LED when pico is running. LED can be 1,2,3"
        delay = {2:0,3:0.8}.get(led,0)
        return self.combine(self.hold('black',delay),self.repeat("blink",(['white','black'],[0.9,0.7])))

    def unStagedChip(self):
        return self.hold('purple')

    def updateMsg(self,generator):
        "overwite the color generator, store the old generator in temp"
        if not self.tempGenerator:
            self.tempGenerator = self.colorGenerator
        self.colorGenerator = self.fade(generator)

    def clearMsg(self):
        "restore the color generator"
        if self.tempGenerator:
            self.colorGenerator = self.fade(self.tempGenerator)
            self.tempGenerator = None

    def updateStatus(self,generator):
        """
        write a new status generator to LED, 
        if the tempGenerator is already taken, this means statusGenerator is hold at temp,
        then we should update the tempGenerator.
        """
        if self.tempGenerator:
            self.tempGenerator = generator
        else:
            self.colorGenerator = self.fade(generator)


    def nextColor(self):
        "return the next display color if any"
        if self.colorGenerator:
            try:
                return next(self.colorGenerator)
            except StopIteration:
                # if the display ended, then switch back to the status generator.
                self.colorGenerator = self.tempGenerator
                self.tempGenerator = None
                return self.nextColor()
        return self.RGB('black')


class LED_Control(Thread):
    "controls the LEDs through the PWM driver"
    def __init__(self,logger):
        super().__init__(daemon=True)
        self._FPS = 20
        self.logger = logger
        self.LED1 = LED(5,6,7,max_b=32767,FPS=self._FPS)
        self.LED2 = LED(8,3,4,max_b=32767,FPS=self._FPS)
        self.LED3 = LED(11,10,9,max_b=32767,FPS=self._FPS)
        self.LEDs = [self.LED1,self.LED2,self.LED3]
        self.RGB_Pin = [*self.LED1,*self.LED2,*self.LED3]
        self.prevStatus = ''    # previous status of the outside LEDs
        self.prevStatusMid = '' # previous status of the middle LED

        # PWM driver setup
        self.pca = PCA9685(busio.I2C(SCL, SDA))
        self.pca.frequency = 60

        self.displayQ = Queue()
        self.willStop = False
        
        # add default status, so that show this LED state before other things initialzied.
        self.statusCopy = {
            'wifi':'ap',
            'bt':'running',  
            'pico':'idle',   
            'heater':'ready',
        }

    def __repr__(self):
        return 'LED Thread'
    
   
    def setColor(self,rgb):
        '''display RGB on the RGB pins. 
        RGB should be a tuple of the same length as self.RGB_Pin. 
        to set the duty cycle of individual pins'''
        for i in range(len(rgb)):
            self.pca.channels[self.RGB_Pin[i]].duty_cycle = rgb[i]
        time.sleep(1/self._FPS)

    def startUpSequence(self):
        "light effect when starting up."
        blink1 = ['red', 'black', 'green', 'black']
        blink2 = ['blue', 'black', 'cyan', 'black']
        blink3 = ['purple', 'black', 'yellow', 'black']
        l1 = self.LED1.combine(self.LED1.hold('black',0),self.LED1.repeat("blink",(blink1,[0.3,0.9]*2)))
        l2 = self.LED1.combine(self.LED1.hold('black',0.3),self.LED1.repeat("blink",(blink2,[0.3,0.3]*2)))
        l3 = self.LED1.combine(self.LED1.hold('black',0.6),self.LED1.repeat("blink",(blink3,[0.3,0.9]*2)))
        count = 0
        for i,j,k in zip(l1,l2,l3):
            color = [*i,*j,*k]            
            self.setColor(color)
            count += 1            
            if count > self._FPS * 2.5:
                break
        # self.setColor(self.LED1.RGB('white')*3)  
        # time.sleep(0.1)
        # self.setColor(self.LED1.RGB('black')*3)   
        # l1 = self.LED1.fade(None)
        # l2 = self.LED1.fade(None)
        # l3 = self.LED1.fade(None)
        # count = 0
        # for i,j,k in zip(l1,l2,l3):
        #     color = [*i,*j,*k]            
        #     self.setColor(color)
        #     count += 1            
        #     if count > self._FPS * 1:
        #         break
        

    
    def updateDisplayQRGBGenerator(self):
        "dispatch a message from displayQ into a RGB color Generator."
        msg = self.displayQ.get(timeout=0.01)
        if msg == 'btn.keydown':
            self.LED2.updateMsg(self.LED2.repeat("blink",(['white','black'],[0.5,0.5])))
        elif msg == 'btn.keyup':
            self.LED2.clearMsg()
        elif msg in ['startNewMeasure','clear']:
            self.LED1.clearMsg()
            self.LED2.clearMsg()
            self.LED3.clearMsg()
        elif msg == 'result.positive':
            self.LED1.updateMsg(self.LED1.hold('black'))
            self.LED3.updateMsg(self.LED3.combine(self.LED3.ramp('black','red',seconds=0.5), self.LED3.hold('red')))
        elif msg == 'result.negative':
            self.LED1.updateMsg(self.LED1.combine(self.LED1.ramp('black','green',seconds=0.5), self.LED1.hold('green')))
            self.LED3.updateMsg(self.LED3.hold('black'))
        elif msg == 'result.average':
            self.LED1.updateMsg(self.LED1.combine(self.LED1.ramp('black','blue',seconds=0.5), self.LED1.hold('blue')))
            self.LED3.updateMsg(self.LED3.combine(self.LED3.ramp('black','blue',seconds=0.5), self.LED3.hold('blue')))
        elif msg == 'result.invalid':
            self.LED1.updateMsg(self.LED1.combine(self.LED1.ramp('black','yellow',seconds=0.5), self.LED1.hold('yellow')))
            self.LED3.updateMsg(self.LED3.combine(self.LED3.ramp('black','yellow',seconds=0.5), self.LED3.hold('yellow')))
        elif msg == 'result.error':
            self.LED1.updateMsg(self.LED1.repeat('blink',(['purple','black'],[0.5,0.4])))
            self.LED3.updateMsg(self.LED3.repeat('blink',(['purple','black'],[0.5,0.4])))
        elif msg == 'testError':
            self.LED1.updateMsg(self.LED1.repeat('blink',(['purple','black'],[0.5,0.4])))
            self.LED3.updateMsg(self.LED3.repeat('blink',(['purple','black'],[0.5,0.4])))            
        elif msg =='unstagedChipInserted':
            self.LED1.updateMsg(self.LED1.repeat('blink',(['purple','black'],[0.5,0.4])))
            self.LED3.updateMsg(self.LED3.repeat('blink',(['purple','black'],[0.5,0.4])))
            # self.LED1.updateMsg(self.LED1.hold('purple'))
            # self.LED3.updateMsg(self.LED1.hold('purple')) 
        elif msg =='chip-inserted-on-start':
            self.LED1.updateMsg(self.LED1.repeat('blink',(['red','black'],[0.5,0.4])))
            self.LED3.updateMsg(self.LED3.repeat('blink',(['red','black'],[0.5,0.4])))
        elif msg == 'pico-error':
            self.LED2.updateMsg(self.LED2.repeat('blink', (['red','black'], [0.3,0.5])))
        elif msg == 'pico-running':
            self.LED1.updateMsg(self.LED1.repeat("blink",(['white','black'],[0.4,0.8])))
            self.LED3.updateMsg(self.LED3.combine(self.LED3.hold('black',0.2),self.LED3.repeat("blink",(['white','black'],[0.4,0.8]))))
        elif msg == 'wifi-client':
            self.LED2.updateMsg(self.LED2.combine(self.LED2.ramp('black','blue',seconds=0.5), self.LED2.hold('blue')))
        elif msg == 'wifi-ap':
            self.LED2.updateMsg(self.LED2.combine(self.LED2.ramp('black','white',seconds=0.5), self.LED2.hold('white')))
        elif msg == 'demoMode-ON': # if turn on demo mode, LED2 will blink red
            self.LED1.updateMsg(self.LED1.repeat('blink',(['red','black'],[0.3,0.3]),6))
        elif msg == 'demoMode-OFF': # if turn off demo mode, LED2 will blink green
            self.LED1.updateMsg(self.LED1.repeat('blink',(['green','black'],[0.3,0.3]),6))
        else:
            self.logger.error(f'UpdateDisplayQREGGenerator: Unknown msg {msg}')


    def updateStatusRGBGenerator(self):
        "update the generator according to recent status"
        if getattr(self.logger,'main',None) and getattr(self.logger.main,'status',None):
            if self.statusCopy == self.logger.main.status.moduleStatus:
                return
            else:
                self.statusCopy.update(self.logger.main.status.moduleStatus)    
        else:
            # if the statusCopy is  marked as justStarted, Then we know
            # we have already intialzied the LED, then we return.
            if self.statusCopy.get('justStarted',None):
                return
            else:
                # use this as a marker to know the LED status just started,
                # so that LED will show the default status.
                # and wait for other modules to start up.
                self.statusCopy['justStarted'] = True
            
        #     'wifi':'client', # can be 'error', 'client', 'ap'
        #     'bt':'running', # can be 'error', 'running'
        #     'pico':'idle', # can be 'idle', 'running', 'waiting', 'error'    
        s = self.statusCopy
        key = f"{s.get('wifi','')}-{s.get('bt','')}-{s.get('pico','')}-{s.get('heater','')}"

        # set LED2 (status LED), only fade if the state changes
        if s['wifi'] != self.prevStatusMid:
            if ('error' in key):
                cyclecolors = ['red','black']            
                # if s['wifi']=='error':cyclecolors.extend(['black','purple'])
                # if s['bt']=='error':cyclecolors.extend(['black','blue'])
                # if s['pico']=='error':cyclecolors.extend(['black','red'])            
                self.LED2.updateStatus(self.LED2.repeat('blink', (cyclecolors,[0.3,0.5])))
            elif s['wifi']=='client':
                self.LED2.updateStatus(self.LED2.combine(self.LED2.ramp('black','blue',seconds=0.5), self.LED2.hold('blue')))
            elif s['wifi']=='ap':
                self.LED2.updateStatus(self.LED2.combine(self.LED2.ramp('black','white',seconds=0.5), self.LED2.hold('white')))
            elif s['wifi'] == 'internet_disconnected':
                # if internet disconnected, blink blue
                self.LED2.updateStatus(self.LED2.repeat('blink', (['black','blue'],[0.3,0.5])))
            else:
                self.LED2.updateStatus(self.LED2.repeat('blink', (['black','red'],[0.3,0.5])))
        self.prevStatusMid = s['wifi']

        # LED1 and LED3 status for test running and test result, only fade if the state changes
        #DEMO : change color status
        if s['pico'] != self.prevStatus:
            if s['pico']=='idle':
                self.LED1.updateStatus(self.LED1.hold('black'))
                self.LED3.updateStatus(self.LED3.hold('black'))
            elif s['pico'] == 'waiting':
                self.LED1.updateStatus(self.LED1.repeat("blink",(['green','black'],[0.4,0.4])))
                self.LED3.updateStatus(self.LED3.combine(self.LED3.hold('black',0.2),self.LED3.repeat("blink",(['green','black'],[0.4,0.4]))))
            elif s['pico'] == 'running':
                self.LED1.updateStatus(self.LED1.repeat("blink",(['white','black'],[0.4,0.8])))
                self.LED3.updateStatus(self.LED3.combine(self.LED3.hold('black',0.2),self.LED3.repeat("blink",(['white','black'],[0.4,0.8]))))
            else:
                self.LED1.updateStatus(self.LED1.hold('black'))
                self.LED3.updateStatus(self.LED3.hold('black'))
        self.prevStatus = s['pico']



    def displayMessage(self,msg):
        """
        put a message into message Q to display;
        new message will overwrite previous message.
        """
        self.displayQ.put_nowait(msg)

    def run(self,):        
        self.startUpSequence()
        while True:
            try:
                if self.willStop:break            
                self.updateStatusRGBGenerator()             
                if not self.displayQ.empty():            
                    self.updateDisplayQRGBGenerator()                        
                todisplay = [i  for j in self.LEDs for i in j.nextColor()]            
                self.setColor(todisplay)
            except Exception as e:
                self.logger.error(f'UpdateDisplayQREGGenerator: {e}')
        
    def stop(self):
        self.willStop=True
        

class PeripheralModule(LoopEventListener):
    "For dealing peripheral devices."

    def __init__(self, daemon, loopInterval, logLevel, printMessages, fileHandler, **kwargs):
        super().__init__(daemon=daemon, loopInterval=loopInterval, logLevel=logLevel, printMessages=printMessages, fileHandler=fileHandler, **kwargs)        
        # for peripheral module, initialze it first.
        # so that the wifi module can correctly initialize
        # If I initialize it in run, then the websocket cannot be connected if 
        # wifi switched from client to AP during start up.
        # so I will initialize Peripheral module during init, and this module is
        # started before all other modules. 
        self.initialize(**self._initialize_kwargs) 

    def initialize(self, wifiTimeout=10,**kwargs):
        ""
        # if already have wifi or led attribute, means it's already initialized, then return.
        if getattr(self,'wifi',None) or getattr(self,'led',None):
            return
        # Input pins 
        ButtonInput = {
            'btn1': 21, #GPIO 21 is the btn pin on Slarkee's board.
            # 'btn2': 17,
            # 'btn3': 27 
        }
        # setup inputs
        btninitstate = GPIO.PUD_UP
        GPIO.setup(list(ButtonInput.values()),GPIO.IN,pull_up_down=btninitstate) # all pins pull up.
        for n,b in ButtonInput.items():
            BtnEventListener(target=n,pin=b,logger=self,pull_up_down=btninitstate)
     
        # start LED thread.
        # LEDs = {'R':17,'G':22,'B':27}
        # self.led = LED_single(LEDs=LEDs,logger=self)
        self.led = LED_Control(logger=self)
        self.led.start()

        # set wifi mode to AP if not connected. 
        # load wifi module after led is started.
        self.wifiTimeout = wifiTimeout
        self.wifi = WifiService(self)
        self.wifi.initialize(wifiTimeout)

        # initialize button dispatch.
        self.ButtonDispatch={}


    def onBtnEvent(self,event):
        "button event handler"
        # have to initialize the dispatch here to get main module.
        if not self.ButtonDispatch:
            self.ButtonDispatch = {
                'btn1' : {'click' : lambda :self.setWifiMode('ap'), 
                          'hold' : lambda : self.setWifiMode('client'),
                          # need to implement this long hold program in anohter process. 
                          # temporaliy use long hold to toggle demo mode
                          'long-hold':lambda : self.main.measurement.toggleDemoMode(),
                          },               
            }
        "receive an input event"
        target = event.target
        action = event.action
        try:
            res = self.ButtonDispatch.get(target,{}).get(action,lambda : f"Event <{target}-{action}> not defined.")()
            self.debug(f"Btn <{target}-{action}> result: {res}")
        except Exception as e:
            self.error(f"Btn <{target}-{action}> error: {e}")
    
    def cleanUp(self):
        "clean up, how to cleanup the leds?"
        self.led.stop()
        self.led.join(timeout=60)
        if self.led.is_alive():
            self.error('PeripheralModule.cleanUp error: LED thread join timeout.')

    def restartHttpModule(self,mode):
        self.main.httpServer.stopModule()
        t0=time.monotonic()
        while not self.main.httpServer.is_alive():
            self.main.httpServer.startModule()
            time.sleep(0.1)
            if time.monotonic() - t0 >self.wifiTimeout:
                self.error(f'switchWifiMode cannot start httpServer @ <{mode}> mode')
                return
        self.debug(f'switchWifiMode restarted http server after {time.monotonic() - t0:.2f}s')

    def switchWifiMode(self,mode):
        """Set the wifi mode to 'client' or 'ap'. And restart websocket and http server accordingly. 
        If switch from ap mode to client mode, and there is no available wifi connection,
        will restart to ap mode. """
        self.wifi.setMode(mode)
        if mode == 'ap':
            time.sleep(3)
            self.main.client.restartWebsocketServer()
            # self.restartHttpModule(mode)
            return 'switched to AP mode'
        else:
            t0 = time.monotonic()
            while not wifi_connected():
                time.sleep(1)
                if time.monotonic() - t0 > self.wifiTimeout * 2:
                    # if cann't connect to wifi in , timeout.
                    self.debug(f'Peripheral switch wifi to <{mode}> mode failed in {self.wifiTimeout*2}s. Fall back to ap mode.')
                    # exponential backoff; max 1minute wait.
                    self.wifiTimeout = min(self.wifiTimeout*1.5,60)
                    return self.switchWifiMode('ap')
            self.debug(f"switchWifiMode Connected to network <{self.wifi.ssid}> after { time.monotonic() - t0 :.2f} seconds.")
            # reset the wifiTimeout to 2X the time elapsed.
            self.wifiTimeout = min((time.monotonic() - t0 ) * 2,60)
            self.main.client.restartWebsocketServer()
            # don't need to restart http server as we are always serving at local host. 
            # self.restartHttpModule(mode)
            return 'switched to Client Mode'
    
    @labelForDev
    def sendMsgToLED(self,msg:str):
        """send a message to led display Queue and be displayed.
        msg can be (currently supported):        
        'btn.keydown':
        'btn.keyup': None,
        'clear': clear LED status.        
        'result.positive':
        'result.negative':
        'result.average':
        'result.invalid':
        'result.error': 
        'testError': 
        'pico-running':
        'pico-error':
        'wifi-client':
        'wifi-ap':
        """
        self.led.displayMessage(msg)


    @labelForDev
    def reconnectWifi(self,mode='client'):
        """
        reconnect wifi, restart wifi in given mode. mode can be 'client' or 'ap'. 
        if the mode is client, then will fisrt restart wlan0.service, so that it will reconnect.        
        """
        def restart():
            time.sleep(1)
            if mode == 'client':
                self.wifi.restartWifi()
            self.switchWifiMode(mode)
        Thread(name='restartwifi',target=restart,daemon=True).start()
        return "Restart wifi in 1 second."

    @labelForDev
    def setWifiMode(self,mode:str):
        """Set the wifi mode to 'client' or 'ap'. And restart websocket and http server accordingly. 
        If switch from ap mode to client mode, and there is no available wifi connection,
        will restart to ap mode. 
        """
        if mode not in ('ap','client'):
            return "mode can only be 'client' or 'ap'"        
        if mode == self.wifi.status:
            return  f"setWifiMode: wifi already in <{mode}> mode."
        self.reconnectWifi(mode)
        return f"Wifi switch to <{mode}> mode in 3 seconds."

    @labelForDev
    def getWifiSSID(self):
        "return the ssid reader is connected to"
        return self.wifi.ssid

    @labelForDev
    def setWifiPassword(self,ssid,pwd):
        "set the password and ssid, try to connect and restart websocket and http server."
        # if len(pwd)<8:return "password too short."
        # if len(pwd)>64: return "password too long."                    
        self.wifi.setWifiPassword(ssid,pwd)
        if ssid != self.wifi.ssid:
            self.reconnectWifi()
        return f"Set <{ssid}> pwd succeed. Restart Wifi in 3 seconds..."

    @labelForDev
    def updateWifiPassword(self,ssid,pwd):
        "similar to setWifiPassword, but will not reconnect, only write the password records"
        self.wifi.updateWifiPassword(ssid,pwd,)        
        return f"Set <{ssid}> pwd succeed."
    
    @labelForDev
    def setWifiPriority(self,ssid:str):
        "set the given ssid priority to 1, change all other wifi priority to 0"
        self.wifi.setWifiPriority(ssid)
        if ssid != self.wifi.ssid:
            self.reconnectWifi()
        return f"Set <{ssid}> priority succeed. Restart wifi in 3 seconds ..."

    @labelForDev
    def removeWifiPassword(self,ssid):
        "remove the ssid from saved password. and reconnect."
        self.wifi.removeWifiPassword(ssid)
        if ssid == self.wifi.ssid:
            # self.wifi.restartWifi()
            self.reconnectWifi(mode='ap')
        return "Remove wifi password succeed."

    @labelForDev
    def scanWifi(self):
        "return a list of available SSID"
        return self.wifi.scanWifi()

    @labelForDev
    def listSavedWifi(self):
        "return list of saved ssid"
        return self.wifi.listSavedWifi()