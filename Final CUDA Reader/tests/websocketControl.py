import websocket
import json
import time
"""
For testing multiple Websocket WSClients
And automate update tasks on multiple devices.
"""

class WSClient:
    def __init__(self,deviceID:str,):
        self.id = deviceID
        if deviceID.isalpha():            
            self.wsAddr = f'ws://ams-{deviceID}.local:8765'
        else:
            self.wsAddr = f'ws://{deviceID}:8765'                    
        for i in range(1):                       
            self.connect()
            if self.con:
                return
            else:
                time.sleep(1)
    
    def __bool__(self):
        return bool(self.con)
    
    def connect(self):
        try:
            self.con = websocket.WebSocket()
            self.con.connect(self.wsAddr)
            
        except Exception as e:
            self.con=None
            self.error = e
       
    
    def __repr__(self):
        return f"ams-{self.id}"
    def reconnect(self):
        if not self.con:
            self.connect()
            res = 'Failed' if not self.con else 'Success'
            return f"{self} connection {res}."
        else:
            return f'{self} already connected.'

    def send(self,action,**kwargs):
        kwargs.update(action=action)
        try:
            self.con.send(json.dumps(kwargs))
            return self.con.recv()
        except Exception as e:
            return f'{self} send msg error: {e}'
        
            
    def updateDevice(self):
        return self.send('main.updateGit')

    def restartSystem(self):
        return self.send('main.restartSystem')
    
    def rebootSystem(self):
        return self.send('main.rebootSystem')

class Proxy:
    def __init__(self,items):
        self._items = items
    def __repr__(self):
        return ','.join(repr(i) for i in self._items)
    def __getattr__(self,name):
        return Proxy([getattr(i,name) for i in self._items])
    def __call__(self,*args,**kwargs):
        return Proxy([i(*args,**kwargs) for i in self._items])

class WSClients(Proxy):
    def __init__(self,IDs):
        self._items = [WSClient(id) for id in IDs]
        self._items = [i for i in self._items if i]

    def updateDevices(self,):
        print('Before Update:')
        print(self.send('main.getVersion'))
        print(self.updateDevice())
    
     
        

if __name__ == "__main__":
    # script to control pis in group.
    print('Enter the device name or IP address you want to sync:')
    default = "qhk xrc yon luu vlo aop kxj wcg axp"
    devices = input(f"Spearate by space. default = {default} \n") or default
    devices = devices.strip().split()
    clients = WSClients(devices)
    print('='*50)
    print('Devices connected:')
    print(clients)
    while True:
        try:
            print("Enter command you want to do: (update,restart,reboot,reconnect)")
            action = input(">>>:  ")
            res = getattr(clients, {
                'update':'updateDevices',
                'restart': 'restartSystem',
                'reboot': 'rebootSystem',
                'reconnect': 'reconnect',
            }[action])()
            print(res)
        except KeyboardInterrupt:
            print('\nByebye.\n')
            break
        except Exception as e:
            print(f"Error: {e}")

     
     




