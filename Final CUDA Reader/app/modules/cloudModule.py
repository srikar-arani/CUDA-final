from app.utils import LoopEventListener, DispatchMeta, dispatch, route, Task, labelForDev
from app.utils import createFolder
import json
import os
import requests
import time
from datetime import datetime
from app.setup.install import SYSTEM_ID
import uuid

DEFAULT_CONFIG = dict(
    APP_TYPE = "DEVICE",
    TENANT_DOMAIN = "aptitudedev.galencloud.com",
    API_VERSION = "3",
    BASE_URL = "https://api.galencloud.com",

    # Constants (for Dev environment)
    TENANT_ID = "APTITUDE-1",
    TEST_INFO_DEVICE_MODEL_ID = "edfcab65-18d6-419d-abdc-86d413298b1a",
    TEST_INFO_DEVICE_PROP_SET_ID = "13867531-fcb9-4ccf-bc12-3a53f4385117",
    READER_INFO_DEVICE_MODEL_ID = "de4769bd-3226-40a2-91ab-4d585c1a307c",
    READER_INFO_DEVICE_PROP_SET_ID = "00301ca3-8272-4d5d-b216-17c675a9f2a0",
    MASTER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJlbWFpbEFkZHJlc3MiOiI2YTEwYmE5NS04YmQzLTQ2OTUtYTVmMi1mNGIzNDY0MWFlMTFAZ2FsZW5jbG91ZC5jb20iLCJyb2xlIjoiVGVuYW50QWRtaW4iLCJhcHBUeXBlIjoiREVWSUNFIiwiaXNzIjoiR2FsZW5DbG91ZCIsInRlbmFudElkIjoiQVBUSVRVREUtMSIsInByaW5jaXBhbElkIjoiNmExMGJhOTUtOGJkMy00Njk1LWE1ZjItZjRiMzQ2NDFhZTExIiwidG9rZW5UeXBlIjoiTWFzdGVyVG9rZW4iLCJleHAiOjE2NTE3MTcyNDB9.jBX6MNS068ohxboV19-F60-mWBkm8isWqYZLgWT-nuHly4FxDwpwSAV_-OfkXKd4fQlwSH7BEpgb9m1JGF8Q-w",
)

# Constants (Across environments)
APP_TYPE = "DEVICE"
TENANT_DOMAIN = "aptitudedev.galencloud.com"
API_VERSION = "3"
BASE_URL = "https://api.galencloud.com"

# Constants (for Dev environment)
TENANT_ID = "APTITUDE-1"
TEST_INFO_DEVICE_MODEL_ID = "edfcab65-18d6-419d-abdc-86d413298b1a"
TEST_INFO_DEVICE_PROP_SET_ID = "13867531-fcb9-4ccf-bc12-3a53f4385117"
READER_INFO_DEVICE_MODEL_ID = "de4769bd-3226-40a2-91ab-4d585c1a307c"
READER_INFO_DEVICE_PROP_SET_ID = "00301ca3-8272-4d5d-b216-17c675a9f2a0"
MASTER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJlbWFpbEFkZHJlc3MiOiI2YTEwYmE5NS04YmQzLTQ2OTUtYTVmMi1mNGIzNDY0MWFlMTFAZ2FsZW5jbG91ZC5jb20iLCJyb2xlIjoiVGVuYW50QWRtaW4iLCJhcHBUeXBlIjoiREVWSUNFIiwiaXNzIjoiR2FsZW5DbG91ZCIsInRlbmFudElkIjoiQVBUSVRVREUtMSIsInByaW5jaXBhbElkIjoiNmExMGJhOTUtOGJkMy00Njk1LWE1ZjItZjRiMzQ2NDFhZTExIiwidG9rZW5UeXBlIjoiTWFzdGVyVG9rZW4iLCJleHAiOjE2NTE3MTcyNDB9.jBX6MNS068ohxboV19-F60-mWBkm8isWqYZLgWT-nuHly4FxDwpwSAV_-OfkXKd4fQlwSH7BEpgb9m1JGF8Q-w"

 


class SendHeartBeat(Task):
    def __init__(self, master, delay=5):
        super().__init__(delay=delay)
        self.interval = 60 # send heartbeat every 60 seconds
        self.master = master

    def task(self, *args, **kwargs):        
        success = self.master.sendHartBeat()
        hasInernet = self.master.main.status.hasInternet()
        if not success and hasInernet:
            self.nextRun(delay=10)
        else:
            self.nextRun(delay=self.interval)
        


def conditionalFunction(func):
    "decorator, disable if the master class enable == False, or when reader has no internet access"
    def wrapper(self, *args, **kwargs):
        if self.enable and self.main.status.hasInternet():
            return func(self, *args, **kwargs)
        else:
            return None
    return wrapper

class CloudModule(LoopEventListener):
    """
    Cloud Module is for sending message to the cloud server.
    """

    def initialize(self,enable=False, **kwargs):
        ""
        self.tokenAt = time.monotonic()
        self._token = None
        self.enable = enable
        self.pendingResultId = None

        # start post heart beat task.
        self.scheduler.addTask(SendHeartBeat(self, delay=5))
        
    @property
    def token(self):
        if (not self._token) or (time.monotonic() - self.tokenAt > 23 * 3600):
            try:
                url =  self.URL( "/auth/refresh-token")
                headers = {
                    "X-APP-TYPE": APP_TYPE,
                    "X-TENANT-DOMAIN": TENANT_DOMAIN,
                    "X-API-VERSION": API_VERSION
                }
                payload = MASTER_TOKEN
                response = requests.post(url, headers=headers, data=payload, timeout=5)
                response.encoding = response.apparent_encoding
                if response.status_code == 200:
                    token = response.headers["Authorization"]                    
                else:
                    raise Exception("Invalid Authentication - " + str(response.text))
                self._token = token
                self.tokenAt = time.monotonic()
            except Exception as e:
                self.error(f"fetch token {e}")
                self._token = ''
        return self._token
    
    @property
    def headers(self):
        return {
        "X-APP-TYPE": APP_TYPE,
        "X-TENANT-DOMAIN": TENANT_DOMAIN,
        "X-API-VERSION": API_VERSION,
        "Content-Type": "application/json",
        "Authorization": self.token,
        }
  
    def URL(self, url):
        return DEFAULT_CONFIG["BASE_URL"]+url

    def cleanUp(self):
        self.debug('CloudModule.CleanUP: CloudModule stopped.')

    def post(self, url, **kwargs):
        try:
            updatedKwargs = {"timeout":3, "headers":self.headers}
            updatedKwargs.update(kwargs)
            res = requests.post(self.URL(url),**updatedKwargs)
            return res            
        except Exception as e:
            self.error(f"Post to {url} server error:{e}")
            return None

                
    def get(self,url,**kwargs):
        """
        GET request. default timeout is 3 second.
        """
        try:
            updatedKwargs = {"timeout":3, "headers":self.headers}
            updatedKwargs.update(kwargs)
            res = requests.get(self.URL(url),**updatedKwargs)
            return res            
        except Exception as e:
            self.error(f"GET {url} server error:{e}")
            return None

    
    @conditionalFunction
    def isReaderRegistered(self):
        """
        check if the reader already been registered
        if already registered, return (currentDeviceDataId,currentPracticeId)
        otherwise return False
        """
        search_url =  "/data/devicedata-advanced"
        payload = {
            "deviceDataModelId" : READER_INFO_DEVICE_MODEL_ID,
            "deviceCriteria" : [{
                "key": "ReaderId",
                "operator": "Equal",
                "value": SYSTEM_ID
            }]
        }
        res = self.post(search_url, json=payload)
        if res and res.status_code == 200:
            responseDict  =  res.json() 
            content0 = responseDict["content"][0]
            currentDeviceDataId = content0["deviceDataId"]
            currentPracticeId = content0["ownerId"]
            return (currentDeviceDataId,currentPracticeId)
        return False

    @conditionalFunction
    def deleteRegisteredReader(self,currentDeviceDataId,):
        """
        delete a reader from cloud, and return True if success
        """
        delete_url = "/data/" + READER_INFO_DEVICE_MODEL_ID + "/devicedata/delete"
        payload = {
        "deviceDataIds": [currentDeviceDataId]
        }
        response = self.post(delete_url, json=payload)                    
        if not response:
            self.error("Could not delete reader registration- No response")            
        elif response.status_code != 200:
            self.error("Could not delete reader registration- " + str(response.text))
        else:
            self.debug(f"deleted registered reader {response.text}")
            return True
        return False

    @conditionalFunction
    def registerReader(self,practiceId):
        """
        register this reader to a give practice.
        return True if success, return False if failed
        """
        create_url = "/data/devicedata"
        # create the record
        deviceData = {}
        deviceData["ReaderId"] = SYSTEM_ID
        deviceData["CreatedOn"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        payload = {
            "deviceDataModelId": READER_INFO_DEVICE_MODEL_ID,
            "devicePropertySetId": READER_INFO_DEVICE_PROP_SET_ID,
            "ownerId": practiceId,
            "data": deviceData
        }
        response = self.post(create_url,  json=payload)
        if not response:
            self.error("Could not register reader- No response")
        elif  response.status_code != 201:
            self.error("Could not register reader - " + str(response.text))
        else:
            self.debug(f"register reader for {practiceId}, {response.text}")
            return True
        return False

    @conditionalFunction
    def authenticateUser(self,emailAddress,password):
        """
        log in a user with email and pasword, return the practice ID.
        """
        url =  "/auth/login"        
        payload = {
            "emailAddress": emailAddress,
            "password": password
        }
        response = self.post(url, params=payload)
        if not response:
            self.error("Could not authenticate user - No response")
        elif response.status_code != 200:
            self.error("Invalid Authentication - " + str(response.text))            
        else:
            responseDict  = response.json()
            practiceId = responseDict.get('defaultRole',{}).get('practice',{}).get('practiceId',None)            
            self.debug(f"authenticateUser for practice {practiceId}")
            return practiceId
        return False
            
    @conditionalFunction
    def createPracticeAdmin(self,practiceId,firstName,lastName,emailAddress,password):
        """
        create a practice account
        """
        url = "/user/user"   
        payload = {
            "user": {
                "firstName": firstName,
                "lastName": lastName,
                "emailAddress": emailAddress,
                "tenant": {
                    "tenantId": TENANT_ID
                },
                "roles": [{
                    "role": "PracticeAdmin",
                    "practice": {
                        "practiceId": practiceId
                    },
                    "defaultRole": True
                }]
            },
            "password": password
        }
        response = self.post(url, json = payload)
        if not response:
            self.error("Could not create practice admin - No response")
        elif response.status_code != 201:
            self.error("Could not create practice admin- " + str(response.text))
        else:
            self.debug(f"Created practice Admin account for {emailAddress}")
            return True
        return False

    @conditionalFunction
    def createPractice(self,practiceName, emailAddress, contactInfo={
                "streetAddress1": "1",
                "city": "Santa Barbara",
                "state": "CA",
                "country": "US",
                "zipcode": "93117",
                "primaryPhone": "+1-000-000-0000"
            }):
        "create a practie and return practice ID if succeed"
        url = "/user/practice"        
        practiceId = str(uuid.uuid4())
        payload = {
            "practiceId": practiceId,
            "name" : practiceName,
            "emailAddress": emailAddress,
            "tenantId": TENANT_ID,
            "contactInfo": contactInfo
        }
        response = self.post(url, json = payload)
        if not response:
            self.error("Could not create practice - No response")
        elif response.status_code != 201:
            self.error("Could not create practice - " + str(response.text))
        else:
            return practiceId
        return False

    @conditionalFunction
    def sendHartBeat(self):
        status = self.main.status.readerStatus()
        deviceData = {}
        deviceData["ReaderId"] = SYSTEM_ID
        deviceData["HeartbeatReceivedOn"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        deviceData["Status"] = status
        payload = {
            "deviceDataModelId": READER_INFO_DEVICE_MODEL_ID,
            "devicePropertySetId": READER_INFO_DEVICE_PROP_SET_ID,
            "data": deviceData
        }
        res = self.post("/data/devicedata", json=payload)
        if not res:
            self.error(f'Post heart beat error No response')
        elif res.status_code != 201:
            self.error(f'Post heart beat error { res.status_code} { res.text}')
        else:            
            return True
        return False

    
    @conditionalFunction
    def getPendingTestId(self):
        url = "/data/devicedata-advanced"
        payload = {
            "deviceDataModelId" : TEST_INFO_DEVICE_MODEL_ID,
            "deviceCriteria" : [{
                "key": "ReaderId",
                "operator": "Equal",
                "value": SYSTEM_ID
            },{
                "key": "TestComplete",
                "operator": "Equal",
                "value": False
            }]
        }
        response = self.post(url,  json = payload)        
        if not response:
            self.error("Could not retrieve device data - reported error")
            self.pendingResultId = ""
        elif (response.status_code != 200):
            self.error("Could not retrieve device data - reported error - " + str(response.text))
            self.pendingResultId = ""
        else:
            responseDict  = response.json()        
            contentArr = responseDict["content"]
            if (len(contentArr) == 0):
                self.pendingResultId = ""
                self.error("Could not retrieve device data - none found")                
            elif (len(contentArr) > 1):
                self.pendingResultId = ""
                self.error("Could not retrieve device data - multiple IDs found")
            else:
                self.pendingResultId = contentArr[0]['deviceDataId']        
                self.debug(f'Got Pending Result ID: {self.pendingResultId}')
        return self.pendingResultId
        

    @conditionalFunction
    def postPendingTestResult(self,result):        
        url =  "/data/devicedata"
        if self.pendingResultId:
            deviceData = {}
            deviceData["TestResult"] = result
            deviceData["TestEndDate"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            deviceData["TestComplete"] = True

            payload = {
                "deviceDataId": self.pendingResultId,
                "deviceDataModelId": TEST_INFO_DEVICE_MODEL_ID,
                "devicePropertySetId": TEST_INFO_DEVICE_PROP_SET_ID,
                "data": deviceData
            }
            response = self.post(url,  json=payload)
            if not response:
                self.error("Could not post test result")                
            elif response.status_code != 201:
                self.error("Could not post test result - " + str(response.text))                
            else:
                return True
        return False
