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


temp = temperature(TestLogger())

for i in range(5):
    time.sleep(1)
    temp.updateTemperature()
    print('temperatuere is ' , temp.getTemperature())