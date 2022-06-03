import os,hashlib
import json
from datetime import datetime
import time

# Hui Kang
# for write the device_id.json to /boot on a SD card automatically.
# this script will update the setup/files/serialSeed.txt
# How to use the script works:
# in the setup folder, run 
# python writeSDCard.py
# once a SD card is inerted to the computer, it will scan if config.txt exsits.
# if config.txt exist but not device_id.json,
# the script will write a device_id.json file to the drive
# this is the /boot partition on Pi.
# reader firmware will read the file and use it this as the device_id.json. 
# after write the device_id.json, the script will update the serialSeed by 1.
# the serialSeed is the actural serial number, and it is a 12 digit integer.
# the serial number is then used to generate a SYSTEM_SEED using hexdigest of md5 hash.
# the serial number is also used to conver to a 6 letter ID. 
# (this is like a base 10 number to base 19 number conversion)
# the current number will be AMS-RD?, and will increase.





ALPHABETS = [
'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
]
BASE = len(ALPHABETS[0])
MAX_COMBINATION = BASE**6


def getSeed(serial:str=''):
    "generate a int seed from serial number"
    serial = serial
    h = hashlib.md5(serial.encode())
    return int(h.hexdigest(),16)

def checkAlphabets():
    for i in ALPHABETS:
        print(len(set(i)))

def convert(o,base=BASE):
    "convert a integer to base N, return a list from most to least significant bit"
    c = []
    while o:
        r = o % base
        c.append(r)
        o = o//base    
    return c[::-1]


def idFormat(c):
    "convert a list of integer to use id format"    
    c = [0]*(6-len(c)) + c
    d = []
    for i,j in enumerate(c):
        d.append(ALPHABETS[i][j])
    return ''.join(d[0:3])+'-'+''.join(d[3:])

def getIDfromSerial(serial):
    return idFormat(convert(int(serial) % MAX_COMBINATION ))

def getNextDeviceID():
    "return a new "
    seedfile = './files/serialSeed.txt'
    with open(seedfile,'rt') as f:
        counter = int(f.read().strip())
    serialNo = f"{counter:012}"
    seed = getSeed(serialNo)
    id = getIDfromSerial(serialNo)
    device = {
    "SYSTEM_SERIAL": serialNo,
    "SYSTEM_SEED": seed,
    "SYSTEM_ID": id,
    "SYSTEM_ID_LONG": id
    }
    with open(seedfile,'wt') as f:
        f.write(str(counter+1))
    return device
    

def sdCardInserted():
    root = 'CDEFGHIJKLMNOPQRST'
    for r in root:
        if os.path.exists(f"{r}:/config.txt"):            
            return r
    return False
    
def writeToSDCard(file):
    device = getNextDeviceID()
    with open(file,'wt') as f:
        json.dump(device,f,indent=2)
    result = f'{datetime.now().strftime("%Y%m%d %H:%M:%S")} - write to {file}: {device["SYSTEM_ID"]}, serial: {device["SYSTEM_SERIAL"]}\n'
    with open("./files/writerecord.txt",'a') as f:
        f.write(result)
    print(result)

def waitUntilChipRemoved(r):
    print('Please Remove SD card...')
    while os.path.exists(f"{r}:/config.txt"):
        time.sleep(0.1)
    print('SD card removed. Ready for next...')
    print('='*50)

def main():
    print("+"*25+'SD card flush utility'+'+'*25)
    print('Started SD card writing script.')
    # mode = input('Enter n if need to generate 1 code and exit\n')
    # if mode == 'n':
    #     writeToSDCard('./device_id.json')
    #     return 
    print('Start Auto Device ID writing. Insert SD card to begin.')
    while True:
        try:
            r = sdCardInserted()
            if r:
                if (not os.path.exists(f"{r}:/device_id.json")):
                    writeToSDCard(f"{r}:/device_id.json")
                else:
                    with open(f"{r}:/device_id.json",'rt') as f:
                        existing = json.load(f)
                        print(f'Existing Device ID: {existing.get("SYSTEM_ID")}.')
                    overwrite = input('Overwrite Device ID? (y/n)')
                    if overwrite.lower() == 'y':
                        writeToSDCard(f"{r}:/device_id.json")
                    else:
                        print('Skip writing to SD card.')
                waitUntilChipRemoved(r)
            time.sleep(0.05)     
        except KeyboardInterrupt:
            print('User stopped script. exiting...')
            exit(0)
        
            

if __name__=='__main__':
    main()