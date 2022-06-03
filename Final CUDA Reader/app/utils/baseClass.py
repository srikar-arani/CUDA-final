import time
import heapq
from threading import Thread
import threading
from queue import SimpleQueue
from app.utils import Logger
from itertools import zip_longest
import inspect 

def generateClassDoc(moduleNameDict,tag='_labelForDev'):
    """
    generate doc dict from a dictionary of name::classes
    only generate docs for class method with the tag labeled as True. 
    """
    methods = {}
    moduledoc = {}
    for moduleName,module in moduleNameDict.items():
        moduledoc[moduleName] = module.__doc__ 
        methods[moduleName] = {}
        for funcName, func in inspect.getmembers(module):
            if getattr(func,tag,False):
                signature = [ ]
                for k,i in inspect.signature(func).parameters.items():
                    if k == 'self': continue 
                    default = "default: empty" if i.default is inspect._empty else f"default:{i.default}"
                    annote = "type: N.A." if i.annotation is inspect._empty else f"type: {i.annotation.__name__}"
                    signature.append((k, f"{default} ; {annote}"))
                methods[moduleName][funcName] = {
                    'doc': func.__doc__ and func.__doc__.strip(),
                    'signature': signature
                } 
    return methods,moduledoc


def labelForDev(func):
    func._labelForDev = True
    return func

def route(uri):
    """
    route path to function
    """
    def deco(func):
        func.isDispatchMethod = True
        func.__name__ = uri
        return func
    return deco

def dispatch(instance,path,):
    """
    NOT USED ANYMORE
    msg format: {
        action: methodName/tag1/tag2,
        other key:value pairs will also be passed to method.
    }
    route an action to instance dispatchers
    """
    methodName = path
    method = getattr(instance,methodName,None)
    if method==None: 
        raise KeyError(f'Method <{methodName}> was not found on <{instance.__class__.__name__}>.')
    return method()

    
class TaskQueue(list):
    """
    Task queue implemented with List 
    This is similar implementation as PriorityQueue
    """
    def put(self,x):
        heapq.heappush(self,x)
    def peek(self):
        return self[0]
    def get(self,):
        if self.empty(): return None
        return heapq.heappop(self)
        
    def empty(self):
        return len(self)==0
    def cancelTask(self,task):
        "remove a task instance from queue"
        for i,t in enumerate(self):
            if t is task:
                # self[i].done()
                del self[i]
                break
        heapq.heapify(self) 
    def nextTime(self):
        if self.empty(): return 999
        return self.peek().nextExec - time.monotonic()
    def getOccupancy(self):
        'return occupancy of the taskqueue'
        return sum([t.avgTime/t.interval for t in self])


class Task():
    """base class for task.
    always call suer().__init(delay=xx) when subclassing. 
    default intermal parameters: 
        self.nextExec = time.monotonic() + delay
        self.runCount = 0
        self.avgTime = 0
        self.interval = 1
        self.status = 'waiting'
        self.startTime = time.monotonic()
    when the task is added to a scheduler,
    scheduler will reset the startTime to current time.
    """
    def __init__(self,delay=0):
        "init a measurement task"
        self.nextExec = time.monotonic() + delay
        self.runCount = 0
        self.avgTime = 0
        self.interval = 1
        self.status = 'waiting'
        self.startTime = time.monotonic()

    def __repr__(self):
        return f"<{self.__class__.__name__}><{self.status}><avg:{self.avgTime:.2f}s><next{(self.nextExec-time.monotonic()):.2f}s>, "
    def __gt__(self,b):
        return self.nextExec > b.nextExec

    def __lt__(self,b):
        return self.nextExec < b.nextExec

    def __eq__(self,b):
        return self.nextExec == b.nextExec
    def cancelRun(self):
        self.nextExec = None
    def run(self,*args,**kwargs):
        #FIXME
        # it's not necessary to do the avg Time in production.
        self.nextExec = None
        t0 = time.perf_counter()
        res = self.task(*args,**kwargs)
        dt = time.perf_counter() - t0
        self.avgTime = (self.avgTime * min(self.runCount,4) + dt) / (min(self.runCount,4) + 1)
        self.runCount += 1
        return res
    def task(self,*args,**kwargs):
        return ""
    def nextRun(self,delay=1):
        self.nextExec = time.monotonic() + delay

    def done(self):
        """clean up asfter task is done, 
        always need to marke status as done.
        if the task is marked as done, it won't be run again by scheduler.
        """
        self.status = 'done'


class Scheduler():
    "Basic Task scheduler, if any one task failed, will stop the loop. "
    def __init__(self, loopInterval=0.01):
        "loopInterval in seconds"
        self.taskQueue = TaskQueue()
        self.loopInterval= loopInterval
        self.toCancel = None
        
    def __repr__(self):
        return f"Scheduler: {str(self.taskQueue)} - interval {self.loopInterval}s."

    def reschedule(self):
        "re-heapify the task queue"
        heapq.heapify(self.taskQueue)

    def addTask(self,task):
        "add a task"
        self.taskQueue.put(task)
        task.status='running'
        task.startTime = time.monotonic()

    def cancelTask(self,task):
        self.taskQueue.cancelTask(task)
        task.status='done'
        task.done()

    def runNextTask(self,):
        "run the next task in taskQueue, default gap 10ms"
        nextTime = self.taskQueue.nextTime()
        if nextTime > self.loopInterval:
            time.sleep(self.loopInterval) 
            return
        time.sleep(max(0, nextTime))
        nextTask = self.taskQueue.get()
        if nextTask is None: return 
        
        # if task is marked as done, don't run the task.
        if nextTask.status!='done':
            nextTask.run()
        
        if (nextTask.status!='done') and  nextTask.nextExec:
            self.taskQueue.put(nextTask)
        

class LoopEventListener(Thread,Logger):
    """
    Base class for all modules. 
    DO NOT overwrite the "start","stop" methods. 
    DO NOT overwrite 'main' attribute. 
    DO NOT overwrite module instance name attribute on main module. (see below)
    
    Implement the following function:
    initialize: function to initialize specific modules.
    cleanUp: clean up work to do when module stops.
    
    All modules should be subclassed from this parent class. 
    Module class name should follows rule: 
        xxxxxModule, xxxxx is module specific.
    Module instance have a name attribute.
    This name attribute is used for referencing loaded modules from main module. 
    This name attribute follows rule: 
        className[0].lower + className[1:-6]
    Loaded modules can be referenced by self.main.nameAttributeOfOtherModule.
        For example: reference HeatingModule from MeasurementModule: 
        in MeasurementModule: self.main.heating => loaded HeatingModule 
    """
    def __init__(self,daemon=None,loopInterval=0.01,
                 logLevel='DEBUG',printMessages=False,fileHandler=None,**kwargs):
        super().__init__(daemon=daemon)
        self.name = self.__class__.__name__[0].lower() + self.__class__.__name__[1:-6]
        
        Logger.__init__(self,self.name.upper(),logLevel,printMessages,fileHandler)
        
        self.scheduler = Scheduler(loopInterval=loopInterval)
        self.willStop = False
        self._initialize_kwargs = kwargs
        
        self.debug(f"<{self.__class__.__name__}> initialized.")
    
    def __repr__(self):
        return f"{self.__class__.__name__}"

    def initialize(self,**kwargs):
        "additional parameters to initialize"

    def register(self):
        "register self to mainModule and register main module to self."
        while True:
            for t in threading.enumerate():
                if t.name=='main':
                    self.main = t 
                    setattr(t,self.name,self)
                    break 
            if getattr(self,'main'):
                break 
            time.sleep(1)

    def run(self):
        """main loop, need to respond to the stop of self.willStop signal.
        other wise need to directly respond to self.stop()"""
        self.initialize(**self._initialize_kwargs) 
        self.register()
        while True:
            if self.willStop:
                break 
            try:
                self.scheduler.runNextTask()
            except Exception as e:
                self.error(f"{self}.run: Task Loop {self.scheduler} error: {e}") 
        self.cleanUp()
        self.debug(f"LoopEventListener.run <{self}> exit.")
        
       
    def cleanUp(self):
        "clean up code after stop is called."

    def stop(self):
        "stop the main loop"
        if not self.is_alive():            
            self.cleanUp()
        self.willStop = True

    @labelForDev
    def showRunningTask(self):
        "Show the current running task in module scheduler."
        return str(self.scheduler.taskQueue)

    @labelForDev
    def tailMsg(self,n:int=50):
        "tail the last n messge  printed."
        return {'tailMsg':list(self.msgDeque)[0:n]}

    @labelForDev
    def isRunning(self):
        "Check if the module is still alive. (thread.is_alive())"
        return self.is_alive()

    @labelForDev
    def getModuleSettings(self,):
        """
        Get current settings of a the module. 
        """
        return self.main.SETTINGS[self.name] 

    @labelForDev
    def setModuleSettings(self,settings:dict={},):
        """
        Change settings of the module. 
        settings: new settings to overwrite.
        if settings == 'default', will set module settings to default value.
        """
        if settings == 'default': 
            self.main.SETTINGS[self.name] = self.main.defaultSETTINGS[self.name].copy()
        else:
            self.main.SETTINGS[self.name] = settings
        self.main.saveSystemSettings()
        return f"Saved settings to {self.name}."

    @labelForDev
    def startModule(self,):
        "start module and add it to main reference"
        moduleName = self.name
        if self.is_alive():
            return f"Module {moduleName} already started."
        module = self.__class__
        newInstance = module(fileHandler=self.main.fileHandler,**self.main.SETTINGS[moduleName]) 
        newInstance.main = self.main
        setattr(self.main , moduleName, newInstance) 
        self = newInstance
        self.start()
        return f"started {self.name} module."

    @labelForDev
    def stopModule(self, ):
        "stop a module."
        if self.is_alive():
            self.stop()
            if not (threading.current_thread() is self):
                self.join(10) 
            if self.is_alive():
                self.critical(f"Error: Module <{self.name}> cannot be stopped.")
                return f"Error: Module {self.name} cannot be stopped."
            return f"Module {self.name} stopped."
        return f"Module {self.name} already stopped."
    
    @labelForDev
    def evaluate(self,expression:str):
        """
        For dev purposes.
        Evaluate an arbitrary string and return output.
         : eval(expression)
        Caution: will cause problem if return value is not json serializeable.
        """
        return str(eval(expression))

    @labelForDev
    def execute(self,expression:str):
        """
        For dev purposes.
        Execute an arbitrary string and return output.
         : exec(expression)
        Caution: will cause problem if return value is not json serializeable.
        """
        return str(exec(expression))
    
class MessageConnection():
    "NOT USED ANYMORE"
    def __init__(self,inputQ,outputQ):
        self.inputQ = inputQ 
        self.outputQ = outputQ 
    def send(self,obj):
        self.outputQ.put(obj)
    
    def recv(self,):
        "get item from inputQ without blocking"
        return self.inputQ.get(False)

    def poll(self):
        "return True if there is something to recv."
        return (not self.inputQ.empty())
    
def MessagePipe():
    """
    NOT USED ANYMORE
    return two end of MessageConnection
    """
    inputQ = SimpleQueue()
    outputQ = SimpleQueue()
    return MessageConnection(inputQ,outputQ),MessageConnection(outputQ,inputQ)

class DispatchMeta(type):
    """
    NOT USED ANYMORE
    enable dispatch class function to a new name using dispatch."""
    def __new__(meta,name,bases,dct):
        for k in list(dct.keys()):
            item = dct[k]
            if getattr(item,'isDispatchMethod',None):
                dct[item.__name__] = dct.pop(k)
        return super(DispatchMeta, meta).__new__(meta, name, bases, dct)

