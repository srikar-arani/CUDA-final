import RPi.GPIO as GPIO 
from queue import Queue
from threading import Thread
import time

class TestLogger:
    info=debug=error=critical = lambda _,x:print(x)
    def __init__(self,):
        self.moduleStatus={
            'wifi':'client',  
            'bt':'running',  
            'pico':'idle',  
        }
    def setStatus(self,**status):
        self.moduleStatus.update(status)

    



class LEDTest(Thread):
    ""
    def __init__(self,LEDs={'R':17,'G':22,'B':27},freq=100):
        super().__init__(daemon=True)
        GPIO.setmode(GPIO.BCM)       
        self.logger = TestLogger()
        self.RGB_Pin = [LEDs['R'],LEDs['G'],LEDs['B']]
        GPIO.setup(self.RGB_Pin, GPIO.OUT, initial=GPIO.LOW)
        self.RGB = [GPIO.PWM(i,freq) for i in self.RGB_Pin]        
        self.displayQ = Queue()
        self._FPS = 24
        self.willStop = False
        self.displayQRGBGenerator = None
        self.statusRGBGenerator = None
        self.statusCopy = {}

    def __repr__(self):
        return 'LED Thread'
    
    @staticmethod
    def toRGB(color):
        "color can be a string or string-brightness"
        res = color.split('-')
        tint = res[0]
        brightness = 1 if len(res)==1 else float(res[1])
        colors = {
            'red':(100,0,0),
            'green':(0,100,0),
            'blue':(0,0,100),
            'black':(0,0,0),
            'white':(100,100,100),
            'purple':(100,0,100),
            'yellow':(100,50,0),
            'cyan':(0,100,100),
            'pink':(100,0,50)
        }
        return tuple(min(i*brightness,100) for i in colors.get(tint,'black'))

    def setColor(self,rgb):
        'display RGB on RGB pin.'
        for i,c in zip(self.RGB,rgb):
            i.start(c)
        time.sleep(1/self._FPS)
            
    def transition(self,fromColor,toColor,seconds,):
        "assuming fps, transit from color1 to color2 in seconds."
        RGB,toRGB = self.toRGB(fromColor) ,self.toRGB(toColor)
        step = int(seconds*self._FPS) + 1
        # stepFuncs = {
        #     'linear':lambda x:tuple(RGB[i]+(x)*(toRGB[i]-RGB[i])/step  for i in range(3)),
        #     'sin':lambda x:tuple(RGB[i]+math.sin(x/step*math.pi/2)*(toRGB[i]-RGB[i])  for i in range(3))
        # }
        for x in range(step+1):
            yield tuple(RGB[i]+(x)*(toRGB[i]-RGB[i])/step  for i in range(3))
    
    def hold(self,color,seconds=-1):
        'holde at one color, if seconds>0, then hold for that time.'
        rgb = self.toRGB(color)
        steps = int(seconds * self._FPS)+1
        while 1:            
            yield rgb
            steps-=1
            if steps==0:
                return

    def cycle(self,*colors,seconds = 3):
        "cycle through the given colors, "
        s = seconds/len(colors)
        for i in range(len(colors)):
            fromColor = colors[i]
            j = i+1
            if j == len(colors):
                j = 0
            toColor = colors[j]
            yield from self.transition(fromColor,toColor,s,)

    def combine(self,*colroGenerators):
        "combine color generators"
        for i in colroGenerators:
            yield from i
 
    def show(self,*colorGenerators,repeats = 1):
        "run given generators"
        for _ in range(repeats):
            for g in colorGenerators:
                for c in g:
                    self.setColor(c)

    def startUpSequence(self):
        "light effect when starting up."
        for c in self.cycle('green','black','red','black','cyan','black','blue','black',seconds=5,):
            self.setColor(c)
    
    def updateDisplayQRGBGenerator(self):
        "dispatch a message from displayQ into a RGB color Generator."
        msg = self.displayQ.get(timeout=0.01)
        self.displayQRGBGenerator = {
            'btn.keydown': self.hold('pink-0.7'),
            'btn.keyup': None,
        }.get(msg,None)

    def updateStatusRGBGenerator(self):
        "update the generator according to recent status"
        if self.statusCopy == self.logger.moduleStatus and self.statusRGBGenerator:
            return
        else:
            self.statusCopy.update(self.logger.moduleStatus)       
        #     'wifi':'client', # can be 'error', 'client', 'ap'
        #     'bt':'running', # can be 'error', 'running'
        #     'pico':'idle', # can be 'idle', 'running', 'waiting', 'error'    
        s = self.statusCopy
        key = f"{s['wifi']}-{s['bt']}-{s['pico']}"

        if ('error' in key):
            cyclecolors = []
            if s['wifi']=='error':cyclecolors.extend(['green','black'])
            if s['bt']=='error':cyclecolors.extend(['blue','black'])
            if s['pico']=='error':cyclecolors.extend(['red','black'])
            # if any error, then cycle R G B color, R for pico error, green for wifi errorr, blue for bluetooth error.
            self.statusRGBGenerator = self.combine(self.cycle(*cyclecolors,seconds=0.5*len(cyclecolors)))
        elif s['pico']!='idle':
            if s['pico'] == 'running':
                # if pico is running, sustain yellow color.
                self.statusRGBGenerator = self.hold('yellow-0.3')
            else:
                # if pico is waiting or anything else, blink yellow color.
                self.statusRGBGenerator = self.combine(self.cycle('yellow-0.3','black',seconds=1))
        else:
            if s['wifi']=='client':
                # if pico is idle, blink green and cyan in client mode.
                self.statusRGBGenerator = self.combine(self.cycle('green-0.3','black','cyan-0.3','black',seconds=5))
            else:
                # if pico is idle, blink green and blue in ap mode.
                self.statusRGBGenerator = self.combine(self.cycle('green-0.3','blue-0.3',seconds=1.5),self.cycle('green','black',seconds=1))

    def selectNextColor(self):
        "the logic to determine which color to display at next time step."
        if self.displayQRGBGenerator:
            try:
                return next(self.displayQRGBGenerator)                
            except StopIteration:
                self.displayQRGBGenerator = None
        if self.statusRGBGenerator:
            try:                
                return next(self.statusRGBGenerator)
            except StopIteration:
                self.statusRGBGenerator=None
                self.updateStatusRGBGenerator()
                return next(self.statusRGBGenerator)

    def displayMessage(self,msg):
        """
        put a message into message Q to display;
        new message will overwrite previous message.
        """
        self.displayQ.put_nowait(msg)

    def run(self,):        
        self.startUpSequence()
        while True:
            if self.willStop:break
            if not self.displayQ.empty():
                self.updateDisplayQRGBGenerator()            
            self.updateStatusRGBGenerator() 
            self.setColor(self.selectNextColor())
        # cleanup after stop.
        GPIO.cleanup(self.RGB_Pin)
        for i in self.RGB:
            i.stop()

    
    def stop(self):
        self.willStop=True
        