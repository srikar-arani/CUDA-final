"""This code works with both 24c02 and 24c16 (though you'll want to also iterate through addresses for using a 24c16 fully):"""

from smbus import SMBus
from math import ceil

def write_to_eeprom(bus, address, data, bs=16):
    """
    Writes to an EEPROM. Only supports starting from 0x00, for now.
    (to add other start addresses, you'll want to improve the block splitting mechanism)
    Will raise an IOError with e.errno=121 if the EEPROM is write-protected.
    Uses 16-byte blocks by default.
    """
    b_l = len(data) # Block count
    b_c = int(ceil(b_l/float(bs))) # Actually splitting our data into blocks
    blocks = [data[bs*x:][:bs] for x in range(b_c)]
    for i, block in enumerate(blocks):
        start = i*bs # and append address in front of each one
        # So, we're sending 17 bytes in total
        bus.write_i2c_block_data(address, start, block)

bus = SMBus(1)
write_to_eeprom(bus, 0x50, [ord(c) for c in "never gonna give you up"])

"""
As for 16-bit-address ICs, like, the 24c32, there's no way I could find to use the default smbus library in a way that wouldn't be slow (one byte at a time), as its `read_block_data()` function literally makes the kernel crash. Basically, using the 16-bit interface, you write two address bytes then read the memory (as opposed to 8-bit reads, when you only write one address byte). The 2-byte write is not something the smbus interface devs seem to have planned for, so you need to first write two bytes, then read a block of data explicitly, and the last one is where all falls down. You can read one byte at a time, sure, but it's very slow and I wouldn't even think about it. Also, i2cdump won't really help you there as it doesn't have a mode for reading 16-bit memory chips =(

However, there's smbus2 library which solves that problem by providing an interface to make things like write-word-then-read-block more easy. Here's how you can read and write 16-bit EEPROMs using smbus2:
Installing smbus2 is as easy as `sudo pip install smbus2`.  
"""  

from smbus2 import SMBus as SMBus2, i2c_msg
from math import ceil
from time import sleep

def write_to_eeprom_2(bus, address, data, bs=32, sleep_time=0.01):
    """
    Writes to a 16-bit EEPROM. Only supports starting from 0x0000, for now.
    (to support other start addresses, you'll want to improve the block splitting mechanism)
    Will (or *might*?) raise an IOError with e.errno=121 if the EEPROM is write-protected.
    Default write block size is 32 bytes per write.
    By default, sleeps for 0.01 seconds between writes (otherwise, errors might occur).
    Pass sleep_time=0 to disable that (at your own risk).
    """
    b_l = len(data)
    # Last block may not be complete if data length not divisible by block size
    b_c = int(ceil(b_l/float(bs))) # Block count
    # Actually splitting our data into blocks
    blocks = [data[bs*x:][:bs] for x in range(b_c)]
    for i, block in enumerate(blocks):
        if sleep_time:
            sleep(sleep_time)
        start = i*bs
        hb, lb = start >> 8, start & 0xff
        data = [hb, lb]+block
        write = i2c_msg.write(address, data)
        bus.i2c_rdwr(write)

def read_from_eeprom_2(bus, address, count, bs=32):
    """
    Reads from a 16-bit EEPROM. Only supports starting from 0x0000, for now.
    (to add other start addresses, you'll want to improve the counter we're using)
    Default read block size is 32 bytes per read.
    """
    data = [] # We'll add our read results to here
    # If read count is not divisible by block size,
    # we'll have one partial read at the last read
    full_reads, remainder = divmod(count, bs)
    if remainder: full_reads += 1 # adding that last read if needed
    for i in range(full_reads):
        start = i*bs # next block address
        
        hb, lb = start >> 8, start & 0xff # into high and low byte


        write = i2c_msg.write(address, [hb, lb])
        # If we're on last cycle and remainder != 0, not doing a full read
        count = remainder if (remainder and i == full_reads-1) else bs
        read = i2c_msg.read(address, count)
        bus.i2c_rdwr(write, read) # combined read&write
        data += list(read)
    return data

bus2 = SMBus2(0)
mul=10
str="never gonna give you up never gonna let you down"
data = [ord(c) for c in str]*mul
write_to_eeprom_2(bus2, 0x50, data)
result = read_from_eeprom_2(bus2, 0x50, len(data))
assert(result == data) # test that helped me verify I'd get the same as I sent
# feel free to add debug prints and stuff