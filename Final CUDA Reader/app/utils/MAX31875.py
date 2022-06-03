"""
A driver for temperature sensor MAX31875
by Hui 20210722
"""

from smbus2 import SMBus

__author__ = "Hui"
__version__ = "1.0.0"


class MAX31875:
    """
    I2C temperature sensor MAX31875
    The configurations are set in the configBuf.
    The confgBuf is initialized with POR state on datasheet.
    Always call writeConfig after made any changes to configurations.
    """
    def __init__(self, part_number=7) -> None:
        """
        part_number: 0 - 7
        corresponds to part number MAX31875R0 - MAX31875R7.
        corresponds to 0x48 - 0x4F on the I2C address.
        """
        self.bus = SMBus(1)
        self.addr = 0x48 + part_number
        self.configBuf = [0x00, 0x40]
        self.config = [0x00, 0x40]

    @property
    def format(self):
        """
        return current temperature format,
        0: normal format
        1: extended format
        """
        return (self.config[1] >> 7)

    @format.setter
    def format(self, fmt):
        """
        set the temperature format, can be 0 or 1.
        0: normal format (default)
        1: extended format
        """
        if fmt not in (0, 1):
            raise ValueError("Invalid format")
        self.configBuf[1] = (self.configBuf[1] & 0x7F) | (fmt << 7)

    @property
    def PEC(self):
        """
        return current packet error checking (PEC) setting
        0: PEC is disabled
        1: PEC is enabled
        """
        return (self.config[1] >> 3) & 1

    @PEC.setter
    def PEC(self, PEC):
        """
        set the packet error checking (PEC) setting
        0: PEC is disabled
        1: PEC is enabled
        """
        if PEC not in (0, 1):
            raise ValueError("Invalid PEC")
        self.configBuf[1] = (self.configBuf[1] & 0xF7) | (PEC << 3)
        if PEC:
            # if enabling PEC, then set the current config state to PEC enabled.
            # otherwise, the config write will fail.
            self.config[1] = (self.config[1] & 0xF7) | (PEC << 3)

    @property
    def resolution(self):
        """
        return current temperature resolution,
        0: 8-bit resolution
        1: 9-bit resolution
        2: 10-bit resolution
        3: 12-bit resolution
        """
        return (self.config[1] >> 5) & 3

    @resolution.setter
    def resolution(self, res):
        """
        set the resolution.
        0: 8-bit resolution
        1: 9-bit resolution
        2: 10-bit resolution
        3: 12-bit resolution
        """
        if res not in (0, 1, 2, 3):
            raise ValueError("Invalid resolution")
        self.configBuf[1] = (self.configBuf[1] & 0x9F) | (res << 5)

    @property
    def conversionRate(self):
        """
        return current conversion rate.
        0: 0.25 conversion/second
        1: 1 conversion/second
        2: 4 conversions/second
        3: 8 conversions/second
        """
        return (self.config[1] >> 1) & 3

    @conversionRate.setter
    def conversionRate(self, rate):
        """
        set the conversion rate.
        0: 0.25 conversion/second
        1: 1 conversion/second
        2: 4 conversions/second
        3: 8 conversions/second
        """
        if rate not in (0, 1, 2, 3):
            raise ValueError("Invalid conversion rate")
        self.configBuf[1] = (self.configBuf[1] & 0xF9) | (rate << 1)

    @property
    def timeOut(self):
        """
        return the current time out setting
        Bus timeout resets I2C interface when SCL is low for 
        more than 30ms.
        0: enable time out on bus.         
        1: disable time out on bus.
        """
        return (self.config[1] >> 4) & 1

    @timeOut.setter
    def timeOut(self, t):
        """
        set the time out.
        0: enable time out on bus.
        1: disable time out on bus.
        """
        if t not in (0, 1):
            raise ValueError("Invalid time out")
        self.configBuf[1] = (self.configBuf[1] & 0xEF) | (t << 4)

    @property
    def faultQueue(self):
        """
        return the fault queue settings.
        Fault queue select how many consecutive overtemperature 
        faults must occur before an overtemperature falut is indicated in 
        the overtemperature status bit.
        0: 1 fault
        1: 2 faults
        2: 4 faults
        3: 6 faults
        """
        return (self.config[0] >> 3) & 3

    @faultQueue.setter
    def faultQueue(self, fq):
        """
        set the fault queue settings.
        0: 1 fault
        1: 2 faults
        2: 4 faults
        3: 6 faults
        """
        if fq not in (0, 1, 2, 3):
            raise ValueError("Invalid fault queue")
        self.configBuf[0] = (self.configBuf[0] & 0xE7) | (fq << 3)

    @property
    def shutDown(self):
        """
        return the current shutdown mode setting
        shutdown mode reduce supply current to 1uA or less. 
        continuous temperature conversion is stopped.
        0: continuous conversion mode
        1: shut down mode
        """
        return self.config[0] & 1

    @shutDown.setter
    def shutDown(self, sd):
        """
        set the shutdown mode.
        0: continuous conversion mode
        1: shut down mode
        """
        if sd not in (0, 1):
            raise ValueError("Invalid shut down mode setting")
        self.configBuf[0] = (self.configBuf[0] & 0xFE) | (sd)

    @property
    def compInt(self):
        """
        return the current comparator interrupt setting.
        the mode determine the behavior of overtemperature status bit operation.
        0: comparator mode
        1: interrupt mode
        """
        return (self.config[0] >> 1) & 1

    @compInt.setter
    def compInt(self, c):
        """
        set the comparator interrupt.
        0: comparator mode
        1: interrupt mode
        """
        if c not in (0, 1):
            raise ValueError("Invalid shut down mode setting")
        self.configBuf[0] = (self.configBuf[0] & 0xFD) | (c << 1)

    @property
    def configBits(self):
        """
        return the current configuration bits in string
        """
        return [f"{i:08b}" for i in self.config]

    def readConfig(self):
        """
        read configuration from the sensor
        """
        buf = self.read(1, 2)
        if buf:
            self.config = buf
        else:
            raise IOError("Failed to read configuration")

    def writeConfig(self):
        """
        write the config buf to config register
        """
        self.write(1, self.configBuf)
        self.config = self.configBuf

    @property
    def T_hyst(self):
        """
        return the current hysteresis temperature setting
        """
        t = self.read(2, 2)
        if t:
            return self.byteToTemp(*t)
        else:
            raise IOError("Failed to read T_hyst")

    @T_hyst.setter
    def T_hyst(self, t):
        """
        set the hysteresis temperature
        """
        u, l = self.tempToByte(t)
        self.write(2, [u, l])

    @property
    def T_os(self):
        """
        return the current over-temperature setting
        """
        t = self.read(3, 2)
        if t:
            return self.byteToTemp(*t)
        else:
            raise IOError("Failed to read T_os")

    @T_os.setter
    def T_os(self, t):
        """
        set the over-temperature
        """
        u, l = self.tempToByte(t)
        self.write(3, [u, l])

    def tempToByte(self, t):
        """
        convert temperature to upper and lower byte
        """
        p = 3 if self.format else 4
        d = int(abs(t) * 16)
        u = d >> (8-p) & 0x7F
        l = d << p & 0xFF
        if t < 0:
            u |= 0x80
        return u, l

    def byteToTemp(self, u, l):
        """
        calculate temperature from 2 data bytes
        """
        p = 3 if self.format else 4
        t = (((u & 0x7F) << (8-p)) + (l >> p)) * 0.0625
        return -t if (u & 0x80) else t

    def getTemperature(self):
        "read current temperature"
        # read upper and lower temperature bytes, c is the optional correction byte
        # TODO: add support for the correction byte
        t = self.read(0, 2)
        if t:
            return self.byteToTemp(*t)
        else:
            raise IOError("Failed to read temperature")

    def write(self, register, data):
        """
        write bytes to register using I2C
        if PEC is enabled, add the CRC-8 byte at then end of data
        """
        addr = self.addr
        if self.PEC:
            crc = self.calcCRC([addr << 1, register] + data)
            self.bus.write_i2c_block_data(addr, register, data+[crc])
        else:
            self.bus.write_i2c_block_data(addr, register, data)

    def read(self, register, length):
        """
        read bytes from register using I2C
        if PEC is enabled, check the crc.
        if crc is correct, return the data bytes
        if crc is incorrect, return None
        """
        addr = self.addr
        if self.PEC:
            data = self.bus.read_i2c_block_data(addr, register, length+1)
            tocheck = [addr << 1, register, (addr << 1)+1] + data[:-1]
            if self.checkCRC(tocheck, data[-1]):
                return data[:-1]
            else:
                return None
        else:
            return self.bus.read_i2c_block_data(addr, register, length)

    def calcCRC(self, data):
        """
        calculate the crc-8 byte from data
        """
        table = b'\x00\x07\x0e\t\x1c\x1b\x12\x158?61$#*-pw~ylkbeHOFATSZ]\xe0\xe7\xee\xe9\xfc\xfb\xf2\xf5\xd8\xdf\xd6\xd1\xc4\xc3\xca\xcd\x90\x97\x9e\x99\x8c\x8b\x82\x85\xa8\xaf\xa6\xa1\xb4\xb3\xba\xbd\xc7\xc0\xc9\xce\xdb\xdc\xd5\xd2\xff\xf8\xf1\xf6\xe3\xe4\xed\xea\xb7\xb0\xb9\xbe\xab\xac\xa5\xa2\x8f\x88\x81\x86\x93\x94\x9d\x9a\' ).;<52\x1f\x18\x11\x16\x03\x04\r\nWPY^KLEBohafst}z\x89\x8e\x87\x80\x95\x92\x9b\x9c\xb1\xb6\xbf\xb8\xad\xaa\xa3\xa4\xf9\xfe\xf7\xf0\xe5\xe2\xeb\xec\xc1\xc6\xcf\xc8\xdd\xda\xd3\xd4ing`ur{|QV_XMJCD\x19\x1e\x17\x10\x05\x02\x0b\x0c!&/(=:34NI@GRU\\[vqx\x7fjmdc>907"%,+\x06\x01\x08\x0f\x1a\x1d\x14\x13\xae\xa9\xa0\xa7\xb2\xb5\xbc\xbb\x96\x91\x98\x9f\x8a\x8d\x84\x83\xde\xd9\xd0\xd7\xc2\xc5\xcc\xcb\xe6\xe1\xe8\xef\xfa\xfd\xf4\xf3'
        _sum = 0
        for byte in data:
            _sum = table[_sum ^ byte]
        return _sum

    def checkCRC(self, data, byte):
        """
        check if the crc byte is correct
        """
        crc = self.calcCRC(data)
        return crc == byte
