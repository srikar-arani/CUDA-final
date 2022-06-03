import pickle
import random
import matplotlib.pyplot as plt
from compress_pickle import load,dump
from app.tests.websocketControl import WSClient
import json
from threading import Thread


with open('./app/defaults/measureSeed','rb') as f:
    data = pickle.load(f)

    
def plot(data, idx,channel):
    fit = [i['pc'] for i in data[idx]['data']['scan'][channel]['fit']]
    plt.plot(fit)
    plt.show()
    return data[idx]['data']['scan'][channel]['rawdata']

    
with open('./app/defaults/download.gz','rb') as f:
    raw = pickle.load(f)
    
raw = load('./app/defaults/savedData.gz')

len(raw)


data.keys()


# positive result in the raw data
res =  plot(raw,-6,'C4')




# negative result in the raw data
res =  plot(raw,,'C2')




# read data from reader
device = WSClient('ams-agl')


res = device.send('dataStore.getRecentPaginated')
data = json.loads(res)['data']['items']



# update the new data to dataStore
id = data[-1]['_id']

data[-1]['data'].keys()

toUpdate = data[-1]['data']

for dtype in ['chipInsertion','temperature']:
    toUpdate[dtype]['time'] = [i/2 for i in toUpdate[dtype]['time']]

for dtype in ['scan','fluidFill']:
    for channel in toUpdate[dtype]:
        toUpdate[dtype][channel]['time'] = [i/2 for i in toUpdate[dtype][channel]['time']]
    

result = device.send('dataStore.updateDataById',id=id,data={'data':toUpdate})

res



"""
███████╗ ██████╗ █████╗ ███╗   ██╗    ██╗      █████╗ ███╗   ██╗
██╔════╝██╔════╝██╔══██╗████╗  ██║    ██║     ██╔══██╗████╗  ██║
███████╗██║     ███████║██╔██╗ ██║    ██║     ███████║██╔██╗ ██║
╚════██║██║     ██╔══██║██║╚██╗██║    ██║     ██╔══██║██║╚██╗██║
███████║╚██████╗██║  ██║██║ ╚████║    ███████╗██║  ██║██║ ╚████║
╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝    ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝
scan local network                                                              
"""


def try_connect(ip:str,devices:list):
    con = WSClient(ip)
    if con:
        id = json.loads(con.send('main.getSystemID'))['data']
        devices.append((id,ip))
        print(f"device {id} @ {ip}")

find_thread = []
devices = []
for i in range(1,255):
    t = Thread(target=try_connect,args=(f'192.168.1.{i}',devices))
    t.start()
    find_thread.append(t)
for t in find_thread:
    t.join()

print(devices)


def mapNumberToLetter(number,padding=6):
    "map an number to base 26 with all cap letters"
    l = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    ll = []
    while number:
        ll.append(l[number % 26])
        number = number // 26
    ll.extend(['A']*(padding-len(ll)))
    ll.reverse()
    return ''.join(ll)
    
    
def mapLetterToNumber(letter):
    n = 0
    for d,l in enumerate(letter[::-1]):
        n += (ord(l)-65) * (26**d)
    return n



