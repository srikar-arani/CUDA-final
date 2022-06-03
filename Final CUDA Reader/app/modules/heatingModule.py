from threading import Thread
from app.utils import LoopEventListener, Task ,labelForDev
from simple_pid import PID
import math,time
from app.utils.MAX31875 import MAX31875
try:
    import RPi.GPIO as GPIO   
except:
    import warnings 
    warnings.warn('Import error in heatingModule.')


# HOW to enable i2c and spi interface: 
# sudo raspi-config and go to interface options. then enable those. 




#TODO: detect temperature sensor error and stop heating. 
# currently, I'm stopping heating after PWM has been at 99% for over 20minutes.
# also stop heating if temperature sensor reading is abnormal. (<-20 or >120)


class temperature():
    def __init__(self,heatingModule):           # Initialize SPI bus and sensor.
        self.heatingModule = heatingModule
        self.currentTemperature = 25
        try:
            m = MAX31875(part_number=7)
            m.PEC = 0 # disable packet error checking
            m.faultQueue = 2  # after 4 tempe falut, then the overtemperature bit is set to 1
            m.resolution = 3  # 12-bit resolution, highest resolution
            m.conversionRate = 2  # temperature conversion rate, 4 / second
            m.T_os = 110
            m.T_hyst = 105
            m.writeConfig()
            self.sensor = m
        except Exception as e:            
            heatingModule.error(f"Temperature sensor initialize error {e}")
            

    # Grab temperature from sensor and update current temperature
    def updateTemperature(self):        
        try:
            self.currentTemperature = self.sensor.getTemperature()
        except Exception as e:
            self.heatingModule.error(f"Temperature sensor read error {e}")
            self.currentTemperature = 120

    def getTemperature(self):     # Return current temperature
        # self.updateTemperature()
        return self.currentTemperature
        

class HeatController():
    # adapted for using MOSFET to control heating.
    pwmPin = 12    
    pwmFreq = 10 # use low frequency at 10 to remove the noise.
    # Initialize PWM, freq in hertz
    def __init__(self, heatingModule=None):
        
        self.heatingModule = heatingModule        
        self.dutyCycle = 0 #starting duty cycle  = 0        
        pins = [self.pwmPin]
        try:
            GPIO.setup(pins, GPIO.OUT)  # Set pins as outputs
        except:
            self.heatingModule.error("Error setting up MOSFET pins")

        self.pwm = GPIO.PWM(self.pwmPin, self.pwmFreq)  # Create PWM Object
                

    def enableHBridge(self):        # Enable the H-Bridge   
        # need to re write the frequency after disableHBridge.
        # otherwise, the frequency will be set to it's default frequency 
        # after disableHBridge is called.
        self.pwm.ChangeFrequency(self.pwmFreq)    
        self.pwm.start(self.dutyCycle)

    def disableHBridge(self):       # Disable the H-Bridge        
        self.pwm.stop()

    def setDutyCycle(self, dutyCycle):
        if (dutyCycle < 0):                            # Check lower bound
            self.heatingModule.error("Cannot set duty cycle < 0!")
        elif (dutyCycle > 100):                        # Check upper bounds
            self.heatingModule.error("Cannot set duty cycle > 100!")
        else:                                       # Change the duty cycle
            self.dutyCycle = dutyCycle              # Set object data
            self.pwm.ChangeDutyCycle(dutyCycle)     # Update PWM

class UpdateControllerTask(Task):
    def __init__(self,tempObj=None, pidObj=None, heaterObj=None,logger=None,overshootTemp=5,overshootTime=10):
        super().__init__()
        self.tempObj = tempObj 
        self.pidObj = pidObj 
        self.heaterObj = heaterObj
        self.interval = 0.5
        self.logger = logger
        self.maxHeatingTime = time.monotonic()
        self.abnormalCount = 0
        self.overshootTemp = overshootTemp
        self.overshootTime = max(overshootTime,1) # overshoot time will always be positive.
        self.pidObj.setpoint = self.pidObj.setpoint + self.overshootTemp
        
        
    @property 
    def timeControlling(self):
        return time.monotonic() - self.startTime
    
    @property
    def temperatureReady(self):
        """
        determine if heating already reached set temperature
        """
        return self.overshootTime <= 0 

    def task(self):
        self.nextRun(delay = self.interval)        
        if self.overshootTime <= 0 and self.overshootTemp:
            self.pidObj.setpoint = self.pidObj.setpoint - self.overshootTemp
            self.overshootTemp = 0
        try:
            self.tempObj.updateTemperature()
            temp = self.tempObj.getTemperature() 
                        
            
            # if temperature reading abnormal don't heat.
            if temp < -20 or temp>90:
                self.abnormalCount += 1
                newDutyCycle = 0
            else:
                newDutyCycle = self.pidObj(temp)
                self.abnormalCount = max(0,self.abnormalCount-1)

            if self.abnormalCount > 20:
                raise Exception(f'Temperature sensor reading abnormal: {temp:.2f} C.')

            # if temperature is within 0.5 deg of the setpoint, decrease the overshoot time.
            if (temp + 0.5 > self.pidObj.setpoint) and (self.overshootTime >= 0):                
                self.overshootTime -= self.interval
            

            # if the heating is at maximum, check if current time is already 20minutes from last time lower than max.
            curtime = time.monotonic()
            if newDutyCycle > 99:
                if (curtime - self.maxHeatingTime > 300):
                    raise Exception('Heating at maximum power for over 5 minutes. Stop heating.')
            else:
                self.maxHeatingTime = curtime
            # self.logger.debug(f"Heating PWM: {newDutyCycle:>6.2f}%; Time: {curtime:>10.1f}s")


            self.heaterObj.setDutyCycle(newDutyCycle) 
        except Exception as e:
            self.logger.error(f'Temperature Control Task error: {e}. Stop.')
            # send msg to LED instead.
            self.logger.status = 'error'
            # try:
            #     self.logger.main.client.notifyClients({'status':'error','data':f"Temperature Control error: {e}",'action':'heating.Error'})
            # except Exception as e:
            #     self.logger.error(f'Temp Control cannot send msg to client: {e}.')
            self.cancelRun()
            self.done()
            
    
    def done(self):
        "stop the heater"
        self.heaterObj.disableHBridge()
        self.logger.UpdateControllerTask = None 
        self.status = 'done'


class HeatingModule(LoopEventListener,):
    "For heating."
    def initialize(self,goalTemperature=65,*kwrags):
        self.status = 'initializing'
        
        self.heaterObj = HeatController(heatingModule=self) 
        # disable hearterObj every time when starting.
        self.heaterObj.disableHBridge()

        # initilaize PID controller
        #DEBUGCOMMENT set point to 27
        self.pidController = PID(Kp=60, Ki=1, Kd=40, setpoint=goalTemperature)
        self.pidController.output_limits = (0, 100)     # Set duty cycle in range of 0-100
        self.pidController.auto_mode = True  # set automode true.
        #pid.auto_mode = True                      # Enable the PID
        #pidController.proportional_on_measurement = True    # Want to test this in the future

        # init temperature sensor 
        self.temperatureObj = temperature(self)
        
        self.UpdateControllerTask = None 

        # set the overshoot parameters
        self.overshootTemp = 0
        self.overshootTime = 1

        # start temperature control automatically        
        # self.startTempControl()

        ## and QC the temperature sensor. to see if heating is happening.
        # self.startHeaterQC()
        #Thread(target=self.startHeaterQC,daemon=True).start()
        
         
    
    def cleanUp(self):
        "stop heating."
        self.heaterObj.disableHBridge()
        
    @labelForDev
    def setGoalTemp(self,temp:float,):
        "set goal temperature. this will not start or stop temperature control."
        # print(kwargs)
        temp = float(temp) 
        if temp > 80 or temp <10:
            self.error(f'Temperature out of range <{temp}>.')
            raise ValueError(f'Temperature out of range <{temp}>.')
        self.pidController.setpoint = temp 
        return temp

    @labelForDev
    def getOvershootSettings(self):
        "return the current heating overshoot setting"
        return f"Temperature: {self.overshootTemp}, Time: {self.overshootTime}"
    @labelForDev
    def setOvershootSettings(self,temp:float,time:float):
        """
        set the overshoot temperature(degree C) and time(seconds)
        Overshoot temperature is the delta amount to overshoot, not the actual temperature.
        Don't set overshoot temperature that bring target temperature above 90.
        E.g. goalTemp is 65, don't set ovverShoot temp above 25.
        """
        temp = float(temp)
        time = float(time)
        if temp < 0:
            self.error(f'Overshoot temperature cannot be negative.')
            raise ValueError(f'Overshoot temperature cannot be negative.')
        if time < 0:
            self.error(f'Overshoot time cannot be negative.')
            raise ValueError(f'Overshoot time cannot be negative.')
        self.overshootTemp = temp
        self.overshootTime = time
        return f"Set overshoot Temperature: {self.overshootTemp}, Time: {self.overshootTime}"
    
    def startHeaterQC(self):
        """
        start a 30seconds temperature QC procedure. 
        this procedure reads temperature, then heat at max power for 20 seconds, return the temperature
        increase amount.
        """
        self.status = 'heatingQC'        
        tmps = []
        for i in range(5):
            tmps.append(self.getCurrentTemp())
            time.sleep(0.2)
        avgTmp = sum(tmps[-3:])/3
        
        self.heaterObj.enableHBridge()        
        self.heaterObj.setDutyCycle(100)        
        time.sleep(10)
        if self.UpdateControllerTask is None:
            self.heaterObj.disableHBridge()
        tmps = []
        for i in range(5):
            tmps.append(self.getCurrentTemp())
            time.sleep(0.2)
        avgTmp2 = sum(tmps[-3:])/3        
        dt = avgTmp2 - avgTmp
        if dt < 1:
            self.status = 'error'       
            self.error(f"Heating QC failed. Temperature increase <{dt:.2f}> is less than 1 C.") 
        else:
            self.status = 'ready'
            self.debug(f"Temperature increase <{dt:.2f}> C in heating QC.") 
        return dt

    @property
    def temperatureReady(self):
        "check if heating controller is ready."
        if self.UpdateControllerTask is None:
            return False
        else:
            return self.UpdateControllerTask.temperatureReady
        
    @labelForDev
    def startTempControl(self):
        """
        Start heating to currently set goal temperature.
        """
        if not self.UpdateControllerTask: 
            self.heaterObj.enableHBridge()
            # reset pid controller before start.
            self.pidController.reset()
            # update temperature first before starting the controller task 
            # to ensure temperature reading is correct and up to date.
            self.temperatureObj.updateTemperature()
            self.UpdateControllerTask = UpdateControllerTask(
                tempObj=self.temperatureObj, heaterObj=self.heaterObj, pidObj=self.pidController,logger=self,
                overshootTemp=self.overshootTemp, overshootTime=self.overshootTime,
                )
            self.scheduler.addTask(self.UpdateControllerTask)            
            return 'Started heating.'
        return 'Heating already started.'
    
    @labelForDev
    def getCurrentTemp(self,):
        "return current temperature"
        if not self.UpdateControllerTask:
            self.temperatureObj.updateTemperature()
        return self.temperatureObj.getTemperature()
    
    @labelForDev
    def getTempControllingTime(self):
        """
        Return the time in seconds that heating module have been started.
        Return 0 if heating module is not working.
        """
        return getattr(self.UpdateControllerTask, 'timeControlling', 0)

    @labelForDev
    def getGoalTemp(self):
        "return current temperature control goal."
        return self.pidController.setpoint 

    @labelForDev
    def stopTempControl(self,):
        "Stop temperature control."
        if self.UpdateControllerTask:
            self.scheduler.cancelTask(self.UpdateControllerTask)
            self.UpdateControllerTask = None
            return 'Temperature Control Stoped.'
        else:
            return "Temperature Control Not Running."

