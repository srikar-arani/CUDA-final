from app._version_ import __version__,__updateNote__
import time
from app.modules import MainModule
import subprocess
import sys

# default settings, can be stored separately later. 

# TODO : System level todo.
# 1. how to set datetime on raspberry Pi. 
# sudo  date  -s  STRING to set time. 
# 

# BUG : currently observed bugs
# 1. weirdly, after overnight, the pi cannot be connected. after power cycle, it goes back to normal.
# 2. Radhey find Pi cannot be paired automatically. need to run sudo bluetoothctl -> pairable on; 
#   on the pi-uyy, at the time of testing, pairable is always on, even without run 'sudo', 'hciconfig', 'hci0', 'piscan'


def startSystem():
    "Start the system"
    argv = sys.argv
    # loop = asyncio.new_event_loop()
    mainModule = MainModule() 
    mainModule.info(f"<MainModule> Started from {argv}")
    # main thread wait for keyboard interrupt or mainmodule exit. 
    while True:
        try:
            time.sleep(1)
            if not mainModule.is_alive():
                # if main module exits, restart it.
                if mainModule._status == 'reboot':
                    mainModule.critical(f"Reboot System.")
                    subprocess.run(['reboot'])
                    return 
            
                elif mainModule._status == 'restart':
                    # if started by supervisor, just quit and restart by supervisor.
                    if len(argv) > 1 and argv [1] == '-supervisor':
                        mainModule.critical(f"Restart system from supervisor.")
                        return 
                    elif len(argv) == 1:
                        # if started without tag
                        mainModule.critical(f"Restart system from subprocess.")
                        subprocess.Popen([ 'sudo', 'python3' , argv[0] ])        
                    return 
                else:    
                    mainModule.critical(f"Main system abnormal quit detected.")
                    mainModule.join()
                    mainModule = MainModule()  
                    mainModule.critical(f"Reloaded Main System.")
        except KeyboardInterrupt:
            mainModule.debug('KeyboardInterrupt, Stopping modules...')
            mainModule.stop()
            mainModule.join() 
            break

