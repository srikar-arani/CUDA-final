from datetime import datetime
from websocketControl import WSClient
import time

if __name__=='__main__':
    device = input('Enter 3 letter device ID:\n')
    temp = input('Enter goal temperature: (default 37deg) \n').strip() or '37'
    name = input('Enter run name:\n').strip()
    runs = input('Enter how many hours to run: (default infinite)\n').strip()
    if runs:
        runs = int(runs)
    else:
        runs = 9999999
    temp = float(temp)
    client = WSClient(device)
    print(client.send('heating.setGoalTemp',temp=temp))
    i=0
    print("="*20 + ' BURNNING STARTED ' + '='*20)
    while True:        
        i+=1
        if i>runs:
            break
        print(f'Burnning run - {i}')
        print(client.send('measurement.startMeasure',meta={
            "name":f'Burn {name} - {i}',
            "method":'default',
            "temp":35,
            "exp":"Burnning Run",
        },method='default',deltaT=5,pwd=""))
        time.sleep(3600+300)
