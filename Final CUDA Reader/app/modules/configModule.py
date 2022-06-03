from app.utils import LoopEventListener, DispatchMeta, dispatch, route, Task, labelForDev
from app.utils import createFolder
import json
import os
import requests

DEFAULT_CONFIG = {    
}


class ConfigModule(LoopEventListener):
    """
    config module is for storing any user configurations.
    by default, it's an empty object.
    """

    def initialize(self, **kwargs):
        ""
        settingsFolder = createFolder('settings')
        self.configFile = settingsFolder / 'device_config.json'
        self.settings = DEFAULT_CONFIG
        self.loadSettings()

    def run(self):
        self.initialize(**self._initialize_kwargs)
        self.register()
        self.debug('ConfigModule Registered. Exit thread.')

    def loadSettings(self):
        if os.path.exists(self.configFile):
            with open(self.configFile, 'rt') as f:
                self.settings.update(json.load(f))
        else:
            self.saveSettings()

    def saveSettings(self):
        with open(self.configFile, 'wt') as f:
            json.dump(self.settings, f)

    @labelForDev
    def get(self, name:str,default=None):
        """
        get a settings property from configModule.
        currently have 'DB_URL', 'userId', 'user'
        """
        return self.settings.get(name, default)

    def update(self,**kwargs):
        self.settings.update(kwargs)
        self.saveSettings()
        

    def DB_URL(self, url):
        "all routes at the reader path"
        return f"{self.get('DB_URL','')}/reader{url}"

    def cleanUp(self):
        self.debug('ConfigModule.CleanUP: ConfigModule stopped.')

    @labelForDev
    def setAccountToken(self, token: str):
        """
        Set the token of user account to report result.
        After set, the token is not saved, but the user ID is saved. 
        """
        if token:
            try:            
                res = requests.post(self.DB_URL('/registerReader'), json={
                                    'token': token, 
                                    'reader': {'id': self.main.getSystemID(), 
                                    'serial': self.main.getSystemSerial(),
                                    'status': 'idle'}},timeout=3)
                if res.status_code==200:
                    uid = res.json().get('userId')
                    self.update(userId=uid,user=res.json().get('user',{}))
                    return 'Set Account Token successfuly.'
                else:
                    return f"Error, sever response error code: [{res.status_code}]."
            except Exception as e:
                self.error(f"setAccountToken error: {e}")
                return f"setAccountToken error."
        else:
            self.update(userId='',user=None)
            return 'Removed Account Token.'
    

                
