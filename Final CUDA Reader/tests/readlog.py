"read the log downloaded"
import zlib

file = r"C:\Users\hui\Desktop\logs.gz"


with open(file,'rb') as f:
    data = f.read()
    
    
log = zlib.decompress(data)

out = r'C:\Users\hui\Desktop\logs.txt'

with open(out,'wt') as f:
    f.write(log.decode())
    
    
    
class LED():
    "controller for a single led; use GPIO on and off to control the LED."
    def __init__(self,*args,on_state=0,FPS=24):
        """
        initialize LED by giving the 3 pin GPIO number in R,G,B order.
        on_state is the GPIO state for the LED to turn on. can be 0 or 1.
        if the LED is connected to 
        """
        self.pins = args        
        self.pud = on_state
        self._FPS = FPS
        self.colorGenerator = None
        self.tempGenerator = None
    
    def __iter__(self):
        return iter(self.pins)

    def RGB(self,color):
        "convert a color name to RGB tuple"
        return {
            'red':(self.pud,not self.pud, not self.pud),
            'green':(not self.pud, self.pud, not self.pud),
            'blue':(not self.pud,not self.pud, self.pud),
            'white':(self.pud, self.pud,  self.pud),
            'black':(not self.pud, not self.pud, not self.pud),
            'cyan':(not self.pud, self.pud, self.pud),
            'yellow':( self.pud, self.pud, not self.pud),
            'purple':( self.pud, not self.pud, self.pud)
        }.get(color,(self.pud,self.pud,self.pud))

    def hold(self,color,seconds=-1):
        "hold at one color."
        rgb = self.RGB(color)
        steps = int(seconds * self._FPS)+1
        while 1:
            yield rgb
            steps -= 1
            if steps==0:return
    
    def blink(self,colors,times):
        "blink the LED at different colors for differnt times"
        for c,t in zip(colors,times):
            yield from self.hold(c,t)

    def combine(self,*cG):
        for i in cG:
            yield from i

    def repeat(self,*cG,repeat=0):
        while True:
            yield from self.combine(*cG)
            repeat -=1
            if repeat==0:
                break

    def picoWaiting(self):
        'return the generator when pico is waiting'
        return self.repeat(self.blink(['yellow','black'],[0.5,0.3]))
    
    def picoRunning(self):
        return self.repeat(self.blink(['white','black'],[0.5,0.3]))

    def testError(self):
        return self.repeat(self.blink(['red','black'],[0.5,0.3]))
    
    def unStagedChip(self):
        return self.hold('purple')

    def updateMsg(self,generator):
        "overwite the color generator, store the old generator in temp"
        if not self.tempGenerator:
            self.tempGenerator = self.colorGenerator
        self.colorGenerator = generator

    def clearMsg(self):
        "restore the color generator"
        if self.tempGenerator:
            self.colorGenerator = self.tempGenerator
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
            self.colorGenerator = generator


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



LED1 = LED(1)
l2 = LED1.combine(LED1.hold('black',0.3),LED1.repeat(LED1.blink(['white','black'],[0.5,0.3])))


l = LED1.hold('black',1)
n = LED1.repeat(LED1.blink(['white','black'],[0.5,0.3]))


next(n)
