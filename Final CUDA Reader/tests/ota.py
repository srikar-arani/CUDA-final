from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import tarfile
import os
import io
import requests
import hashlib




def tarfilter(tarinfo):    
    if (len(tarinfo.name.split('/src/'))) > 1:
        tarinfo.name = tarinfo.name.split('/src/')[1]
        return tarinfo
    else:
        return None


def getVersion():
    r = requests.get('https://raw.githubusercontent.com/rocksnow1942/covid_sensor_version/main/version.txt')
    return r.text.split('\n')[0].strip(' "\n')

def getMD5():
    r = requests.get('https://raw.githubusercontent.com/rocksnow1942/covid_sensor_version/main/version.txt')
    return r.text.split('\n')[1].strip(' "\n').split('=')[1]
    
SYSTEM_SERIAL = '123456789'
def getEncryptor(pwd):
    "return an encryptor that uses pwd to encrypt or decrypt a byte string."
    pwd = str(pwd).strip()
    
    kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=SYSTEM_SERIAL.encode(),
    iterations=100000,
    backend=default_backend())
    key = base64.urlsafe_b64encode(kdf.derive(pwd.encode()))
    return Fernet(key)
    
en = getEncryptor('password')



target = io.BytesIO()

fb = tarfile.open(fileobj = target,mode = 'w:xz')

fb.add(r"C:\Users\hui\Desktop\src",filter=tarfilter)

for root,fd,files in os.walk(r"C:\Users\hui\Desktop\src"):
    for f in files:
        file = os.path.join(root,f)        
        fb.add(file,filter = tarfilter)

fb.close()


toEncrypt = target.getvalue()


md5 = hashlib.md5(toEncrypt)
    
print(md5.hexdigest())
    

    

encryptRes = en.encrypt(toEncrypt)


with open(r"C:\Users\hui\Desktop\release\encrypted",'wb') as f:
    f.write(encryptRes)






# get the latest firmware from git hub and write to dest

version = getVersion()

version


release = f"https://github.com/rocksnow1942/covid_sensor_version/releases/download/{version}/firmware"

res = requests.get(release)

download = res.content


decryptRes = en.decrypt(download)


fileObj = io.BytesIO(decryptRes)


tarFileRead = tarfile.open(fileobj = fileObj)
    
tarFileRead.extractall(path=r"C:\Users\hui\Desktop\dest")
    
    

md5 = hashlib.md5(decryptRes)
    
print(md5.hexdigest())
    





res = requests.get('http://192.168.1.200:8001/api/availableFirmware')
res.json()














# how to show a progress_bar during downloading. 
from tqdm import tqdm
import requests

url = "http://www.ovh.net/files/10Mb.dat" #big file test
# Streaming, so we can iterate over the response.
response = requests.get(url, stream=True)
total_size_in_bytes= int(response.headers.get('content-length', 0))
block_size = 1024 #1 Kibibyte
progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
with open('test.dat', 'wb') as file:
    for data in response.iter_content(block_size):
        progress_bar.update(len(data))
        file.write(data)
progress_bar.close()
if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
    print("ERROR, something went wrong")






import requests

