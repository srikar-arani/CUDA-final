import sys
sys.path.append('../../')
from app.modules.heatingModule import temperature, HeatController, PID
from threading import Thread
from datetime import datetime
import json
from tests._test_utils import TestLogger
import RPi.GPIO as GPIO
import time
import os

def makeJsonFile(file):
    affix = 1
    if not os.path.exists(file+'.json'):
        return file + '.json'
    while os.path.exists(file+f'-{affix}'+'.json'):
        affix += 1
    return file+f'-{affix}'+'.json'
        



class hBridgeTest(HeatController):
    def __init__(self, pwmFreq):
        super().__init__(heatingModule=TestLogger())
        self.pwmFreq = pwmFreq


class HeatingTest(TestLogger):
    def __init__(self, pwmFreq=10, interval=0.5, setpoint=65, config='./config.txt'):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.heater = hBridgeTest(pwmFreq)
        self.pid = PID(Kp=60, Ki=1, Kd=40, setpoint=setpoint)
        self.pid.output_limits = (0, 100)
        self.pid.auto_mode = True
        self.temp = temperature(TestLogger())
        self.interval = interval
        self.printMsg = True
        self.willStop = False
        self.history = []  # store time,temperature, dutyCycle at each update.
        self.configFile = ''
        self.config = []
        self.readConfig(config)
        self.execStart = False
        self.execStartTime = time.monotonic()
    
    def pasreString(self,s):
        try:
            return float(s)
        except:
            return s.upper()


    def readConfig(self, config):
        if config:
            with open(config, 'r') as f:
                data = f.read()
            data = [i.strip().split('#')[0].strip() for i in data.split(
                '\n') if not i.strip().startswith('#')]
            data = [i for i in data if i]
            self.configFile = data
            data = [[self.pasreString(j) for j in i.strip(
            ).split()] for i in data]
            print('Configuration:')
            for i in data:
                print(f"{i[0]}  {i[1]} {i[2]}")
            self.config = data
        else:
            self.config = []

    def start(self):
        self.willStop = False
        self._controlthread = Thread(target=self.run)
        self._controlthread.start()

    def clear(self):
        self.history = []

    def getCurrentTemp(self):
        self.temp.updateTemperature()
        return self.temp.getTemperature()

    @property
    def goalTemp(self):
        return self.pid.setpoint

    @goalTemp.setter
    def goalTemp(self, temp):
        self.pid.setpoint = temp

    def setPID(self, Kp, Ki, Kd):
        "set Kp, Ki and Kd of PID"
        self.pid.tunings = (Kp, Ki, Kd)
    
    def finishCmd(self):        
        print(f'Command {self.config[0][1]} {self.config[0][2]} is finished in {time.monotonic() - self.execStartTime:>10.2f} seconds.\n')        
        self.config = self.config[1:]
        self.execStart = False
        self.execStartTime = time.monotonic()
        if not self.config:
            raise Exception('Command in configuration is finished.')
        t,c,v = self.config[0]
        print(f'Start Command {t} {c} {v}.')


    def updateFromConfig(self,temp):
        cmd = self.config[0] if self.config else None
        if cmd is None:
            raise Exception('Command in configuration is finished.')
        t, c, v = cmd
        if t == 'SET':
            if c == 'MPR':
                self.pid.output_limits = (0, v)
                self.finishCmd()
                return self.updateFromConfig(temp)
            else:
                raise Exception(f'Unknown command: {c}')
        elif isinstance(t, float):
            if t > 0:
                if not self.execStart:
                    if abs(temp - v) < 1 or c in ['GOL','PWR']:
                        print(f'Command {t} {c} {v} start counting down.')
                        self.execStart = True
                if self.execStart:
                    cmd[0] -= self.interval
                if c in ['TMP','GOL']:
                    self.goalTemp = v
                return c                
            else:
                self.finishCmd()
                
                return self.updateFromConfig(temp)

    def updatePID(self):
        temp = self.getCurrentTemp()
        try:
            cmd = self.updateFromConfig(temp)        
        except:
            self.willStop = True
            return 0,0
        if cmd in ['TMP','GOL']:
            newDutyCycle = self.pid(temp)                        
        elif cmd == 'PWR':
            newDutyCycle = self.config[0][-1]
        else:
            raise Exception(f'Unknown command returned from updateFromConfig: {cmd}')
        self.heater.setDutyCycle(newDutyCycle)
        return temp, newDutyCycle

    def setFreq(self, freq):
        self.heater.pwmFreq = freq

    def startHeater(self, cycle):
        if not self.heater.enabled:
            self.heater.enableHBridge()
        self.heater.setDutyCycle(cycle)

    def stopHeater(self):
        self.heater.disableHBridge()

    def run(self):        
        tstart = time.monotonic()
        self.heater.enableHBridge()
        self.execStartTime = time.monotonic()
        while True:
            t0 = time.monotonic()
            temp, duty = self.updatePID()

            if self.willStop:
                break
            self.history.append((t0-tstart, temp, duty))
            if self.printMsg:
                self.info(
                    f'>{self.config[0][0]:>9.2f}s; T: {temp:>6.2f}; PWR: {duty:>6.2f}%')
            t1 = time.monotonic()
            time.sleep(self.interval-t1+t0)
            
        self.heater.disableHBridge()
        self.info(f'Stopped Heating Test.')

    def stop(self):
        self.willStop = True
        self._controlthread.join()        


if __name__ == "__main__":

    test = HeatingTest(pwmFreq=10, interval=0.5)
    freq = test.heater.pwmFreq
    interval = test.interval
    print(f'Heater para: Freq: {freq} , Interval {interval}')
    test.start()
    print('Heating Test started...')
    while True:
        try:
            time.sleep(1)
            if test.willStop:
                test.stop()
                break
        except KeyboardInterrupt:
            test.willStop = True            
    
    GPIO.cleanup()         
    savefile = makeJsonFile('./result')
    with open(savefile, 'wt') as f:
        json.dump({'para': {'freq': freq, 'interval': interval},
                    'config': test.configFile, 'result': test.history}, f, indent=2)
    
    print(f'Heating Test Result saved to {savefile}')
