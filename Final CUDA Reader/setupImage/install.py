from subprocess import STDOUT, check_call
from pathlib import Path
import os,json,random,hashlib,subprocess
import platform
"""
GIT Repo:
https://github.com/AptitudeCodebase/covid_sensor.git
git config --global credential.helper store
sudo git clone <url>
[sudo git checkout hui-branch]
cd covid_sensor/app/setup
sudo python3 install.py
"""

#TODO: able to auto start and setup device specific settings. 
# add auto start capability. 


FUNCTIONS = {} 

# utility functions.

def menuDecorator(displayname,priority=5):
    def deco(func):
        FUNCTIONS[(displayname,priority)] = func
        return func
    return deco

def run(cmd):
    check_call(cmd.split(' '),stderr=STDOUT)

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
        
def appendIfNotExist(content):
    "add content to data if content doesn't exist in text"
    def cb(text):
        newcontent = content
        if content in text:
            return text 
        else:
            if not text.endswith('\n'): text+='\n'
            if not content.endswith('\n'): newcontent+='\n'
            return text + newcontent
    return cb

def replaceLine(original,replace):
    "replace occurance of content in the line with new stuff."
    def cb(text):
        res = []
        for line in text.split('\n'):
            if original in line:
                res.append(line.replace(original,replace))
            else:
                res.append(line)
        return '\n'.join(res)
    return cb

def replaceLineNumber(nbr,replace):
    def cb(text):
        lines = list(filter(lambda x:x.strip() , text.split('\n')))
        lines[nbr]=replace
        return '\n'.join(lines)
    return cb


def getSerial(n=12):
    "generate a random serial number."
    serial = [str(random.randint(0,9)) for i in range(n)]
    return "".join(serial)

def generate_id(length=3,seed=None,alphabet=None):
    "generate a unique id for pi, alphabet is the letters to choose from when generating ID."
    seed = seed or getSeed()
    random.seed(seed)
    id=""    
    s = alphabet or 'BCDFGHJKMPQRTVWXY' #string.ascii_uppercase #+string.digits # using only these to avoid vulgar words
    for _ in range(length):
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
    SYSTEM_ID = f"AMS-{generate_id(length=3,seed=SYSTEM_SEED)}"
    SYSTEM_ID_LONG = f"AMS-{generate_id(length=6,seed=SYSTEM_SEED)}"
    return dict(SYSTEM_SERIAL=SYSTEM_SERIAL,SYSTEM_SEED=SYSTEM_SEED,SYSTEM_ID=SYSTEM_ID,SYSTEM_ID_LONG=SYSTEM_ID_LONG)


def createFolder(folder):
    "create path if not exist"
    _folder = Path(__file__).parent.parent/ folder
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


info_dict = readDeviceInfo()

SYSTEM_SERIAL = info_dict.get('SYSTEM_SERIAL')
SYSTEM_SEED = info_dict.get('SYSTEM_SEED')
SYSTEM_ID = info_dict.get('SYSTEM_ID')
SYSTEM_ID_LONG =info_dict.get('SYSTEM_ID_LONG')
USER_NAME = 'pi'


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
    folder = createFolder('settings')
    idFile = folder/'device_id.json'  
    SYSTEM_ID = f"{name.upper()}"
    SYSTEM_ID_LONG = f"{name.upper()}"
    data = dict(SYSTEM_SERIAL=SYSTEM_SERIAL,SYSTEM_SEED=SYSTEM_SEED,SYSTEM_ID=SYSTEM_ID,SYSTEM_ID_LONG=SYSTEM_ID_LONG)    
    with open('/boot/device_id.json','wt') as f:
        json.dump(data,f,indent=2)
    

       


# ███████╗██╗   ██╗███╗   ██╗ ██████╗████████╗██╗ ██████╗ ███╗   ██╗███████╗    
# ██╔════╝██║   ██║████╗  ██║██╔════╝╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝    
# █████╗  ██║   ██║██╔██╗ ██║██║        ██║   ██║██║   ██║██╔██╗ ██║███████╗    
# ██╔══╝  ██║   ██║██║╚██╗██║██║        ██║   ██║██║   ██║██║╚██╗██║╚════██║    
# ██║     ╚██████╔╝██║ ╚████║╚██████╗   ██║   ██║╚██████╔╝██║ ╚████║███████║    
# ╚═╝      ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝    
                                                                              

# install packages 
@menuDecorator('Install apt packages',1)
def aptpkg():
    with open(Path(__file__).parent / 'requirements.json','rt') as f:
        data = json.load(f)
    for p in data['aptPkg']:
        check_call(['apt-get','install','-y', p],stderr=STDOUT)
    return ["Installed apt packages."]

@menuDecorator('Install python3 packages',2)
def pippkg():
    with open(Path(__file__).parent / 'requirements.json','rt') as f:
        data = json.load(f)
    for p in data['pipPkg']:
        check_call(['pip3','install', p],stderr=STDOUT)
    return ["Installed pip packages."]

@menuDecorator('Update system',99)
def updatesys():
    run("sudo apt update")
    run("sudo apt -y upgrade")
    return ["Updated system."]
    
@menuDecorator('Install AccessPoint/Client Mode',6)
def accessPoint():
    #setup Access point and client switch by apon and apoff
    AP_SERVICE="""[Unit]
Description=WPA supplicant daemon (interface-specific version)
Requires=sys-subsystem-net-devices-wlan0.device
After=sys-subsystem-net-devices-wlan0.device
Conflicts=wpa_supplicant@wlan0.service
Before=network.target
Wants=network.target
[Service]
Type=simple
ExecStartPre=/sbin/iw dev wlan0 interface add ap0 type __ap
ExecStart=/sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-%I.conf -Dnl80211,wext -i%I
ExecStopPost=/sbin/iw dev ap0 del
[Install]
Alias=multi-user.target.wants/wpa_supplicant@%i.service
"""
    subprocess.run(['bash', str(Path(__file__).parent / 'setupAP.sh'),SYSTEM_ID])
    editFile("/etc/systemd/system/wpa_supplicant@ap0.service","w",AP_SERVICE)
    return ["*******Installed AP/Client Service*********","*****NEED TO REBOOT*****"]
    
@menuDecorator('Set Up jupyternotebook, Run <sudo jupyter notebook password>',8)
def setupJupyter():
    "setup jupyter lab, need to setup password later. "
    # need to change password, add service to supervisord. etc. 
    run("pip3 install jupyterlab")
    run("jupyter notebook --generate-config")
    p = "/root/.jupyter/jupyter_notebook_config.py"
    settings=f"""c.NotebookApp.ip = "*"
c.NotebookApp.open_browser = False
c.NotebookApp.notebook_dir = '/home/{USER_NAME}'
c.NotebookApp.allow_password_change = True
"""
    editFile(p,'w',settings)
    sv = "/etc/supervisor/conf.d/jupyter.conf"
    svconf=f"""[program:jupyternotebook]
command=/usr/local/bin/jupyter notebook --no-browser --allow-root --config={p}
directory=/home/{USER_NAME}
user=root
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
"""
    editFile(sv,'w',svconf)
    editFile("/etc/supervisor/supervisord.conf","r",appendIfNotExist("[inet_http_server]\nport=0.0.0.0:9001\nusername=ams\npassword=ams"))
    run("supervisorctl reload")
    return ['Installed Jpyter Notebook',"Run <sudo jupyter notebook password> to setup password."]

@menuDecorator(f'Change host name to <{SYSTEM_ID}>',7)
def changeHostName(newhostname=SYSTEM_ID):
    "change host name to AMS-<id>"
    editFile('/etc/hostname','w',newhostname)
    editFile('/etc/hosts','r', replaceLine('raspberrypi',newhostname))
    return ['NEW HOST NAME:',
        '*'*10+f"   {newhostname}   "+'*'*10,
        '*'*10+f"   {newhostname}   "+'*'*10,
        '*'*10+f"   {newhostname}   "+'*'*10,'*****NEED TO REBOOT*****']

@menuDecorator('Setup device app auto run',3)
def deviceApp():
    # enable supervisor 
    folder = Path(__file__).absolute().parent.parent.parent
    supervisorconf = f"""[program:deviceApp]
command=sudo /usr/bin/python3 {folder / 'app.py'} -supervisor
directory={folder}
user=root
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
"""
    run("systemctl stop supervisor")
    editFile("/etc/supervisor/conf.d/deviceApp.conf",'w',supervisorconf)
    editFile("/etc/supervisor/supervisord.conf","r",appendIfNotExist("[inet_http_server]\nport=0.0.0.0:9001\nusername=ams\npassword=ams"))
    # this is try to solve the 'supervisor.sock no such file' error
    try:
        run("/usr/bin/supervisord")
    except Exception as e:
        print(f"****supervisor exception: {e}***")
    # don't know if this will solve the problem. 
    # but by: cd /usr/bin then sudo supervisord can solve problem
    run("systemctl enable supervisor")
    run("supervisorctl reload")
    return ["Installed device App."]

@menuDecorator('enable ssh',5)
def enablessh():
    run("systemctl enable ssh")
    return ['SSH enabled.']

@menuDecorator('open necessary serial ports',4)
def serial():
    "change serial port uart to communicate with pico"
    # disable shell on serial port and enable serial port 
    editFile("/boot/config.txt",'r',appendIfNotExist("\nenable_uart=1"))
    # enable i2c and spi for raspberry pi.
    editFile("/boot/config.txt",'r',appendIfNotExist("\ndtparam=i2c_arm=on"))
    editFile("/boot/config.txt",'r',appendIfNotExist("\ndtparam=spi=on"))

    # remove console=serial0,115200 from /boot/cmdline.txt
    editFile("/boot/cmdline.txt",'r',replaceLine('console=serial0,115200 ',''))

    return ['Serial port enabled.']

@menuDecorator('Set system timezone.',90)
def setTimeZone():
    "set timezone"
    run('timedatectl set-timezone US/Pacific')
    return ['Set timezone to US/Pacific']
    

@menuDecorator('Setup System, combined individual functions.',0)
def setup():
    """
    setup code for fresh install pi
    Steps: 
    0. Update system.
    1. Install apt packages then pip packages.
    2. Setup Device App Auto run in supervisor
    3. Setup serial ports.
    4. Enable ssh
    5. Install AP/Client Mode switch Service. 
    6. Change host name to AMS-<UNIQUE_ID>
    """
    res = []
    res.extend(updatesys())
    res.extend(aptpkg())
    res.extend(pippkg())
    res.extend(setTimeZone())  
    #serial ports enable 
    res.extend(serial())
    # enable ssh
    res.extend(enablessh())
    # enable accesspoint 
    res.extend(accessPoint())
    # change host name
    res.extend(changeHostName(SYSTEM_ID))
    # install alias 
    res.extend(installAlias())
    # setup supervisor
    res.extend(deviceApp())
    return res


@menuDecorator("Rename System",10)
def renameSystem():
    oldname = platform.node()
    print('+'*50)
    print(f"***Current System Name: < {oldname} >" )
    print('+'*50)
    newname = input("Enter the new name for this system:\n").strip()
    if newname:
        toreplace=f'ssid="{oldname}"'
        editFile("/etc/wpa_supplicant/wpa_supplicant-ap0.conf",'r',replaceLine(toreplace,f'ssid="{newname}"'))
        changeHostName(newname)
    return [f'Renamed system to {newname}']        

@menuDecorator("Install alias to bashrc",11)
def installAlias():
    folder = Path(__file__).absolute().parent.parent.parent
    log = folder/'app/logs/COVID_system.log'
    setup = folder/'app/setup/install.py'
    app = folder/'app.py'
    alias = [
        'alias tl="echo apon,apoff,log,cl,ins,app,gp,startApp,stopApp"',
        'alias apon="sudo systemctl start wpa_supplicant@ap0.service"',
        'alias apoff="sudo systemctl start wpa_supplicant@wlan0.service"',
        f'alias log="tail -f -n 100 {log}"',
        f'alias cl="sudo rm {log}"',
        f'alias ins="sudo python3 {setup}"',
        f'alias app="sudo python3 {app}"',
        f'alias gp="sudo git pull"',
        'alias startApp="sudo supervisorctl restart deviceApp"',
        'alias stopApp="sudo supervisorctl stop deviceApp"',
    ]
    res = []
    for ali in alias:
        res.append(ali)
        editFile(f"/home/{USER_NAME}/.bashrc",'r',appendIfNotExist(ali))
    return ["Installed following alias:"]+res

def deleteFileIfExist(file):
    if os.path.exists(file):
        os.remove(file)

def deleteFilesInFolder(folder):
    files = os.listdir(folder)
    for file in files:
        deleteFileIfExist(os.path.join(folder,file))
    return files

@menuDecorator("Clean up system for clone SD card",12)
def cleanupSys():
    # remove 
    folder = Path(__file__).absolute().parent.parent.parent
    log = folder/'app/logs/COVID_system.log'
    deleteFileIfExist(log)
    db = folder / 'app/data_storage/measurementResults.sqlite'
    deleteFileIfExist(db)
    files = deleteFilesInFolder(folder/'app/settings')
    idfile = '/boot/device_id.json'
    deleteFileIfExist(idfile)
    return ["Removed following files:",str(log),str(db),idfile] + [str(f) for f in files]

def deleteFileIfExist(file):
    if os.path.exists(file):
        os.remove(file)

def deleteFilesInFolder(folder):
    files = os.listdir(folder)
    for file in files:
        deleteFileIfExist(os.path.join(folder,file))
    return files

@menuDecorator("Clean up system for clone SD card",12)
def cleanupSys():
    # remove 
    folder = Path(__file__).absolute().parent.parent.parent
    log = folder/'app/logs/COVID_system.log'
    deleteFileIfExist(log)
    db = folder / 'app/data_storage/measurementResults.sqlite'
    deleteFileIfExist(db)
    files = deleteFilesInFolder(folder/'app/settings')
    idfile = '/boot/device_id.json'
    deleteFileIfExist(idfile)
    return ["Removed following files:",str(log),str(db),idfile] + [str(f) for f in files]


# from install_pkg import run,getSupervisorFile,editFile
def main():    
    print('\nSet up Pi for device app.')

    print(("*"*50+'\n'))
    print(f"Device ID:  >> {SYSTEM_ID} <<\n")
    print(("*"*50+'\n'))

    print('Choose an operation:\n')
    menu = list(FUNCTIONS.keys())
    menu.sort(key=lambda x: x[1])
    for i,(name,_) in enumerate(menu):
        print(f">> {i+1} <<. {name}")
    ans = input("\nEnter option number: [default=1]\n").strip() or 1
    operation = FUNCTIONS[menu[int(ans)-1]]
    print(f'\nYou selected <{ans}>: { menu[int(ans)-1][0] }')
    print(operation.__doc__)
    confirm = input("Continue ? [Y/n]")
    if confirm.lower()=="n":
        return 
    res = operation()
    print('='*50)
    print((f'\n{"*"*50}\n').join(res))   
    print('='*50)
    res=input('\nContinue...?[Y/n]')
    if res.lower()=='n':
        raise KeyboardInterrupt

if __name__ == "__main__":
    while 1:
        try:
            main()
        except KeyboardInterrupt as e:
            print('\nExit...\n\n')
            break
