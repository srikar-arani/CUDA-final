# MAX31875_driver
Python driver for I2c temperature sensor MAX31875

Require smbus2 ^0.4.1 

- [smbus2 Homepage](https://pypi.org/project/smbus2/)

## Usage


```Python
from MAX31875 import MAX31875
# initialize based on the last digit of sensor part number
sensor = MAX31875(part_number = 7)

#set sensor configurations
sensor.format = 1 # data format, 0: normal, 1: extended
sensor.PEC = 1 # 0: disable PEC, 1: enable PEC
sensor.resolution = 2 # 0: 8bit, 1: 9bit, 2: 10bit, 3: 12bit,
sensor.conversionRate = 2 # 0:0.25/s, 1: 1/s, 2: 4/s, 3: 8/s,
sensor.timeOut = 0 # 0: enable timeout, 1: disable timeout,
sensor.faltQueue = 0 # 0: 1fault, 1: 2falut, 2: 4faluts, 3: 6faults,
sensor.shutDown = 0 # 0: continuous mode, 1: shutdown.
sensor.compInt = 0 # 0: comparator mode, 1: interrupt mode

# call writeConfig to write the configuration settings to sensor register
sensor.writeConfig()

# read configration register and check configuration
sensor.readConfig()
print('PEC setting is ',sensor.PEC)
print('Resolution setting is ',sensor.resolution)

# check configuration bits
print(sensor.configBits)

# check and set T_os and T_hyst
# unlike configuration settings, setting value on T_os and T_hyst 
# triggers write to their respective register immediately.
sensor.T_os = 56 # in celcius
sensor.T_hyst = 50
print('Over temperature setting is: ',sensor.T_os)

# read current temperature
sensor.getTemperature()


# read and write to registers directly
sensor.read(register=0,length=2) # return list of two byte value (integer)

sensor.write(register=1,data=[0x0,0x40]) 

```

### Packet Error Checking (PEC)

If packet error checking is enabled:
```Python
sensor.PEC = 1
sensor.writeConfig()
```
The driver automatically append the CRC byte after the data when writing to registers.

When reading, CRC check is performed automatically. An `IOError` will be raised if CRC check failed.

`sensor.read` returns `None` if CRC check failed.