from app.utils import LoopEventListener, DispatchMeta, dispatch, route, Task ,labelForDev

# use websocket_client for sending connection to ws server. 
# 

class BeeModule(LoopEventListener):
    "BeeModule for taking with other Pi(s) and set itself to worker/queen mode."
    def initialize(self,**kwargs):
        ""

    def cleanUp(self):
        ""