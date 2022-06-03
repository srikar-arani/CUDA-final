from subprocess import STDOUT, check_call
from pathlib import Path
import os,json,random,hashlib
import secrets

def editFile(file,mode,callback):
    data = None
    if mode=='r':
        f = open(file,mode) 
        data = f.read() 
        f.close()
        mode = 'w'
    if callable(callback):
        if (data is None):
            towrite = callback()
        else:
            towrite = callback(data)
    else:
        towrite = callback
    if not towrite.endswith('\n'): towrite+='\n'
    with open(file,mode) as f:
        f.write(towrite)
        

def replaceLineNumber(nbr,replace):
    def cb(text):
        lines = list(filter(lambda x:x.strip() , text.split('\n')))
        lines[nbr]=replace
        return '\n'.join(lines)
    return cb


def getSerial(n=12):
    "generate a random serial number."
    serial = [str(secrets.randbelow(10)) for i in range(n)]
    return "".join(serial)

def generate_id(length=3,seed=None,alphabet=None):
    "generate a unique id for pi, alphabet is the letters to choose from when generating ID."
    seed = seed or getSeed()
    random.seed(seed)
    id=""    
    s = alphabet or 'BCDFGHJKMPQRTVWXY' #string.ascii_uppercase #+string.digits # using only these to avoid vulgar words
    for _ in range(length):
        if _ % 4 == 0:
            id+='-'
        id += random.choice(s)        
    return id

def getSeed(serial:str=''):
    "generate a int seed from serial number"
    serial = serial or getSerial()
    h = hashlib.md5(serial.encode())
    return int(h.hexdigest(),16)

def generate_default_reader_info():
    SYSTEM_SERIAL = getSerial()
    SYSTEM_SEED = getSeed(SYSTEM_SERIAL)
    id = generate_id(8,SYSTEM_SEED)
    SYSTEM_ID = f"AMS{id}"
    SYSTEM_ID_LONG = f"AMS{id}"
    return dict(SYSTEM_SERIAL=SYSTEM_SERIAL,SYSTEM_SEED=SYSTEM_SEED,SYSTEM_ID=SYSTEM_ID,SYSTEM_ID_LONG=SYSTEM_ID_LONG)


def createFolder(folder):
    "create path if not exist"
    _folder = Path('/covid_sensor')/ folder
    if not os.path.exists(_folder):
        os.mkdir(_folder) 
    return _folder

def readDeviceInfo():
    """
    read device ID related information.
    look for /boot/device_id.json. 
    if that file doesn't exist, look for it under app/settings/device_id.json
    otherwise, create new random device ID.
    """
    folder = createFolder('settings')
    idFile = folder/'device_id.json'
    if os.path.exists('/boot/device_id.json'):
        with open('/boot/device_id.json','rt') as f:
            data = json.load(f)        
    else:
        if os.path.exists(idFile):
            with open(idFile,'rt') as f:
                data = json.load(f)
        else:
            # if file doesn't esxist, use a randomly generated info. 
            data = generate_default_reader_info()
            with open('/boot/device_id.json','wt') as f:
                json.dump(data,f,indent=2)
    return data


def _changeHostName(SYSTEM_ID):
    'change hostname to given system_ID'    
    # be carefull, Pi only work at band width from 2412 to 2457
    frequency = random.choice(range(2412,2458,5))
    editFile('/etc/hosts','r', replaceLineNumber(-1,f"127.0.1.1       {SYSTEM_ID}"))
    editFile('/etc/wpa_supplicant/wpa_supplicant-ap0.conf','w',f"""country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
ssid="{SYSTEM_ID}"
mode=2
key_mgmt=WPA-PSK
proto=RSN WPA
psk="aptitude"
frequency={frequency}
}}    
""")
    editFile('/etc/hostname','w',SYSTEM_ID)

def autoChangeHostName()->str:
    'change hostname to system_ID'
    with open('/etc/hostname','r') as f:
        id = f.read().strip()
    if id!= SYSTEM_ID:
        _changeHostName(SYSTEM_ID)
        return SYSTEM_ID
    else:
        return False


def renameDevice(name:str):
    """
    change the name of device by create a new device_id.json. 
    write the data to /boot/device_id.json
    will keep the same SYSTEM_SEED and SYSTEM_SERIAL"""    
    SYSTEM_ID = f"{name.upper()}"
    SYSTEM_ID_LONG = f"{name.upper()}"
    data = dict(SYSTEM_SERIAL=SYSTEM_SERIAL,SYSTEM_SEED=SYSTEM_SEED,SYSTEM_ID=SYSTEM_ID,SYSTEM_ID_LONG=SYSTEM_ID_LONG)    
    with open('/boot/device_id.json','wt') as f:
        json.dump(data,f,indent=2)

# install packages 
def aptpkg():
    with open(Path(__file__).parent / 'requirements.json','rt') as f:
        data = json.load(f)
    for p in data['aptPkg']:
        check_call(['apt-get','install','-y', p],stderr=STDOUT)
    return ["Installed apt packages."]

def pippkg():
    with open(Path(__file__).parent / 'requirements.json','rt') as f:
        data = json.load(f)
    for p in data['pipPkg']:
        check_call(['pip3','install', p],stderr=STDOUT)
    return ["Installed pip packages."]


info_dict = readDeviceInfo()

SYSTEM_SERIAL = info_dict.get('SYSTEM_SERIAL','0000000000')
SYSTEM_SEED = info_dict.get('SYSTEM_SEED','0000000000')
SYSTEM_ID = info_dict.get('SYSTEM_ID','AMS-AAA')
SYSTEM_ID_LONG =info_dict.get('SYSTEM_ID_LONG','AMS-AAAAAA')
USER_NAME = 'pi'

