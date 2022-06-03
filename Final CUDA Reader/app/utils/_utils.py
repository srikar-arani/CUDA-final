from pathlib import Path  
import os
# necessary import for other modules. I don't want to go back change others. 
from app.setup.install import SYSTEM_ID,SYSTEM_SERIAL,SYSTEM_SEED
import json

def createFolder(folder):
    "create path if not exist"
    _folder = Path("/covid_sensor") / folder
    _folder.mkdir(parents=True, exist_ok=True)    
    return _folder

def createFile(relativePath):
    "create a file if not exist"
    file = Path('/covid_sensor') / relativePath
    file.parent.mkdir(parents=True, exist_ok=True)    
    if not file.exists():
        file.touch()
    return file

def readJsonFile(file):
    "read json file"
    with open(file, 'r') as f:
        try:
            return json.load(f)
        except:
            return {}
    
def writeJsonFile(file,data):
    "write json file. create file if not exist"
    file = createFile(file)
    with open(file, 'w') as f:
        json.dump(data, f)

def mapNumberToLetter(number:int,padding:int=6)->str:
    "map an number to base 26 with all cap letters, padded with A to the left till padding length"
    l = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    ll = []
    while number:
        ll.append(l[number % 26])
        number = number // 26
    ll.extend(['A']*(padding-len(ll)))
    ll.reverse()
    return ''.join(ll)
    
def mapLetterToNumber(letter:str)->int:
    'reverse function of mapNumberToLetter, turn a all cap letter to number, '
    n = 0
    for d,l in enumerate(letter[::-1]):
        n += (ord(l)-65) * (26**d)
    return n
