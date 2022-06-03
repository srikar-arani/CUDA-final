from app.utils import LoopEventListener,createFolder,route,dispatch,DispatchMeta,generateClassDoc,labelForDev
from app.setup.install import SYSTEM_ID
from app.utils.wifi import get_ip
from app import __version__
from http.server import HTTPServer,BaseHTTPRequestHandler
from jinja2 import Template
import sys
import json,os
from pathlib import Path
import mimetypes
import zlib

#TODO reduce data transfer of websockets
#reduce data transfer of the dataStore data by compression 
#lazy load most of data only load it when being clicked on. need to be able to load

def disableDevPage(func):
    """
    Disables a given route if the disableDevPage of self.logger.disableDevPage == True. 
    this flag is set in the settings, and is set after passed resitor QC. 
    disable this trigger for development purose.
    """
    def wrapper(self,*args,**kwargs):
        if False and self.logger.disableDevPage:
            return self.abort404()
        else:
            return func(self,*args,**kwargs)
    return wrapper

def handler(Master):
    class SimpleHandler(BaseHTTPRequestHandler,metaclass=DispatchMeta):
        nonlocal Master
        logger = Master
       
        def json(self):
            "return json dict or empty dict"
            if self.headers['Content-Length']:
                return json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode())
            return {} 

        def abort404(self):
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write('<h1>PAGE NOT FOUND.</h1>'.encode())

        def sendData(self,data,header,cache=True):
            self.send_response(200)
            self.send_header("Content-type", header)
            # FIXME: remove dev testing.
            if (sys.argv[-1] != '-dev'):
                if cache:
                    self.send_header("Cache-Control","public, max-age=432000")
            self.end_headers()
            self.wfile.write(data)

        def sendCSS(self,css):
            self.sendData(css,'text/css')
        def sendHTML(self,html):
            self.sendData(html,'text/html')
        def sendJS(self,js):
            self.sendData(js,'application/javascript')
        def sendMAP(self,js):
            self.sendData(js,'application/json')

        def do_GET(self):
            """Respond to a GET request."""
            # display LED flash.
            # self.logger.main.peripheral.led.show('wifi',[50,1],1,)
    
            try:
                # redirect / to /index
                path = self.path.strip('/') or 'demoUI'
               
                dispatch(self,path=path)
            except Exception as e:
              
                # if not defined, try to look for raw html pate.
                self.sendFileOr404(path)

        def do_POST(self):
            "respond to post request"
            # self.logger.main.peripheral.led.show('wifi',[50,1],1,)    
            try:
                # redirect / to /index
                path = self.path.strip('/') or 'index'
                dispatch(self,path=path)
            except:
                # if not defined, try to look for raw html pate.
                self.sendFileOr404(path)



        def render(self,filepath,*args,**kwargs):
            "render with jinja2"
            if self.logger.resources.get(filepath,None):
                template = self.logger.resources.get(filepath)
                return Template(template.decode()).render(*args,**kwargs).encode()
            return "Page Not Found.".encode()

        @route('download')
        @disableDevPage   
        def download(self):
            "download data to pickle format"
            # TODO
            # chagne the download to a post and be able to download only selected dates. 
            data = self.logger.main.dataStore.dumpPickle()            
            return self.sendData(zlib.compress(data),"application/gzip",cache=False)
        
        @route('logs')
        @disableDevPage   
        def logs(self):
            "download log file"
            log = createFolder('logs') / 'COVID_system.log'
            with open(log,'rb') as f:
                text = f.read()
            data = zlib.compress(text)
            return self.sendData(data,'application/gzip',cache=False)
              
        @route('index')
        @disableDevPage
        def index(self):
            "return index page"
            res = self.render('index.html',sysid=SYSTEM_ID,version=__version__)
            return self.sendHTML(res)

        @route('runtest')
        @disableDevPage
        def runtest(self):
            websockAddr = self.logger.main.client.websockAddr()
            #DEMO : render with scale Ratio
            res = self.render('run.html', sysid=SYSTEM_ID,version=__version__, websocketAddr=websockAddr,scaleRatio=self.logger.main.dataProcess.scaleRatio)
            return self.sendHTML(res)

        @route('demoUI')
        def demoUI(self):
            websockAddr = self.logger.main.client.websockAddr()
            res = self.render('demoUI.html', sysid=SYSTEM_ID,version=__version__, 
                            runMethod='demoRun',websocketAddr=websockAddr)
            return self.sendHTML(res)



        @route('devpage')
        @disableDevPage
        def devpage(self):
            "return devpage"
            from app.modules import moduleNameDict 
            from app.modules import MainModule
            dd = {'main':MainModule}
            dd.update(moduleNameDict)
            methodsDoc, moduleDoc = generateClassDoc(dd)
            websockAddr = self.logger.main.client.websockAddr()
            renderres = self.render('devPage.html',sysid=SYSTEM_ID,modules=methodsDoc, moduledoc = moduleDoc,
                        version=__version__ ,websocketAddr=websockAddr) 
            return self.sendHTML(renderres)

        def sendFileOr404(self,filePath,mode='html'):
            header = mimetypes.guess_type(filePath)[0] or 'application/json'
            if self.logger.resources.get(filePath,None):
                data = self.logger.resources.get(filePath)
                return self.sendData(data,header)
            return self.abort404()

    return SimpleHandler
 

class HttpServerModule(LoopEventListener):
    """
    A simple http server, servering some pages.
    """
    def initialize(self,**kwargs):

        # load all resources from templates folder to self.resources
        filePath = createFolder('app/templates')
        self.resources = {}
        for root,_,files in os.walk(filePath):
            for file in files:
                fp = os.path.join(root,file)
                relative_path = str(Path(fp).relative_to(filePath))
                with open(fp,'rb') as f:
                    self.resources[relative_path] = f.read()
        self.disableDevPage = kwargs.get('disableDevPage',False)
      
        
    def run(self):
        self.initialize(**self._initialize_kwargs)
        self.register()
        try:
            serverAddress = ('localhost',88)
            self.httpServer = HTTPServer(serverAddress,handler(self)) 
            self.debug(f"Started HttpServer on: {serverAddress[0]}:{serverAddress[1]}")
            self.httpServer.serve_forever() 
        except PermissionError:
            serverAddress = (get_ip(),8000)
            self.httpServer = HTTPServer(serverAddress,handler(self)) 
            self.debug(f"Started HttpServer on: {serverAddress[0]}:{serverAddress[1]}")
            self.httpServer.serve_forever()
        except Exception as e:
            self.error(f"Start HttpServer on {serverAddress[0]}:{serverAddress[1]} error: {e}")
        # release binding socket.
        try:
            self.httpServer.socket.close()
        except AttributeError as e:
            self.debug('Warning - tried to close a non-existing Websocket')
        self.debug(f"<{self.__class__.__name__}> stopped.")
    
    @labelForDev
    def stop(self):
        "Stop http server"
        self.httpServer.shutdown()

    @labelForDev
    def disableHttpDevPage(self):
        "Diable the dev page"
        self.disableDevPage = True
        settings = self.getModuleSettings()
        settings.update(disableDevPage= True)
        self.setModuleSettings(settings)
        return 'DevPage Disabled'