import random
from app.utils import LoopEventListener, labelForDev
from app.dataProcessing import fitPeak, CoivdResultAnalysis, FibrinogenResultAnalysis
from collections import defaultdict
import random


class DataStore():
    """
    Stores measurment data. 
    data structure:
    scan:
    {
        'C1':{time:[],rawdata:[],fit:[]}
        'C2':{time:[],rawdata:[],fit:[]}
    }
    temperature:
    {
        time:[],
        data:[],
    }
    chipInsertion:
    {
        time:[],
        data:[],
    }
    fluidFill:
    {
        'C1':{time:[],data:[]}
        'C2':{time:[],data:[]}
    }

    """
    def _scanStructure(): return {'time': [], 'rawdata': [], 'fit': [], }
    def _fluidFillStructure(): return {'time': [], 'data': []}

    def __init__(self, scaleRatio):
        self.scaleRatio = scaleRatio
        self.scan = defaultdict(DataStore._scanStructure)
        self.temperature = defaultdict(list)
        self.chipInsertion = defaultdict(list)
        self.fluidFill = defaultdict(DataStore._fluidFillStructure)
        self.startTime = None

    def convertTimeStamp(self, t):
        # convert timestame to relative minutes.
        # t is from time.monotnic()
        if self.startTime is None:
            self.startTime = t
        t_ = (t - self.startTime)/60 * self.scaleRatio
        return round(t_, 6)

    def appendData(self, channel, time, voltage, amp, fitres,other):
        self.scan[channel]['time'].append(self.convertTimeStamp(time))
        self.scan[channel]['rawdata'].append(
            [voltage, [round(a, 6) for a in amp],other])
        self.scan[channel]['fit'].append(fitres)

    def appendTemperature(self, time, temp):
        self.temperature['time'].append(self.convertTimeStamp(time))
        self.temperature['data'].append(round(temp, 3))

    def appendChipInsertion(self, time, data):
        self.chipInsertion['time'].append(self.convertTimeStamp(time))
        self.chipInsertion['data'].append(data)

    def appendFluidFill(self, channel, time, data):
        self.fluidFill[channel]['time'].append(self.convertTimeStamp(time))
        self.fluidFill[channel]['data'].append(round(data, 6))

    def dump(self):
        "dump to dict"
        # when dumping, need to convert to regular dict; otherwise will cause pickle error when stored.
        # TODO
        # this step might take time? not sure how fast it is to convert.
        return {'scan': dict(self.scan), 'temperature': dict(self.temperature),
                'chipInsertion': dict(self.chipInsertion), 'fluidFill': dict(self.fluidFill)}

    def reset(self):
        self.scan = defaultdict(DataStore._scanStructure)
        self.temperature = defaultdict(list)
        self.chipInsertion = defaultdict(list)
        self.fluidFill = defaultdict(DataStore._fluidFillStructure)
        self.startTime = None

    def getData(self, lengthDict):
        "get data from lengt dict"
        result = {'scan': {}, 'temperature': {}, 'fluidFill': {}}
        for channel, data in self.scan.items():
            channelLength = lengthDict.get('scan', {}).get(channel, 0)
            # to avoid send back data that haven't finished fitting.
            ending = min((len(i) for i in data.values()), default=0)
            result['scan'][channel] = {
                f: l[channelLength:ending] for f, l in data.items()}

        tempLength = lengthDict.get('temperature', 0)
        tempending = min((len(i)
                          for i in self.temperature.values()), default=0)
        result['temperature'] = {f: l[tempLength:tempending]
                                 for f, l in self.temperature.items()}

        for channel, data in self.fluidFill.items():
            fluidFillLength = lengthDict.get('fluidFill', {}).get(channel, 0)
            ending = min((len(i) for i in data.values()), default=0)
            result['fluidFill'][channel] = {
                f: l[fluidFillLength:ending] for f, l in data.items()}

        return result

# use this to track what result to give in the next run.



class DataProcessModule(LoopEventListener):
    "For processing data"
    DEMO_MODE_INDEX = 0

    def initialize(self,**kwargs):
        # DEMO: the scale ratio is used to adjust signal ratio in both runPage and data collection.
        self.scaleRatio = 1
        self.data = DataStore(scaleRatio=self.scaleRatio)
        self.dataStoreIndex = None
        self.meta = None  # to store the meta info of the current scan.

    def cleanUp(self):
        self.debug(
            f"DataProcess.cleanUp: <{self.__class__.__name__}> stopped.")

    def run(self):
        """
        this module doesn't need to be running as a thread.
        It just need to register itself to mainModule, so that other modules 
        can utilize it through mainModule.
        """
        self.initialize(**self._initialize_kwargs)
        self.register()
        self.debug(
            f"DataProcess.run: <{self.__class__.__name__}> registered. Exit.")

    def startScan(self, idx, meta={}, **kwrags):
        "mark starting of a scan"
        self.dataStoreIndex = idx
        self.meta = meta
        self.data.reset()

    def endScan(self, **kwargs):
        "mark current scan ending"
        self.saveResult(mode='end')

    def abortScan(self, reason, **kwargs):
        'abort current scan'
        self.saveResult(mode='abort', reason=reason)

    def saveResult(self, mode, reason=None):        
        data = self.data.dump()
        chipType = self.meta.get('chipType',-1)

        if not self.dataStoreIndex:
            return
        
        value = 0 # value of the test result to put in 'result'
        if chipType == 7:
            self.logger.debug('COVID Analysis called')
            status, result = CoivdResultAnalysis(data, mode=mode, reason=reason,)
            value = result

            stat = status.get('stat')
            self.debug('<DataProcessModule> saveResult: COVID analysis complete. \n' +
                       '                        Status: ' + stat + '\n' +
                       '                        Result: ' + result + '\n')
                    
            # if running in demo mode, rewrite the result to random.
            if self.main.measurement.demoMode:                
                result = ['Positive','Negative','Error','Invalid'][self.DEMO_MODE_INDEX % 4]
                self.DEMO_MODE_INDEX += 1

            # display the result to LED:        
            if result=='Positive':
                self.main.peripheral.sendMsgToLED('result.positive')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.covid.finishedTest',
                                                   'data': {'result': 'positive'}})
            elif result=='Negative':
                self.main.peripheral.sendMsgToLED('result.negative')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.covid.finishedTest',
                                                   'data': {'result': 'negative'}})
            elif result=='Error':
                self.main.peripheral.sendMsgToLED('result.error')
            else:
                self.main.peripheral.sendMsgToLED('result.invalid')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.covid.finishedTestInvalid',
                                                   'data': {'result': 'invalid'}})
        else:
            self.logger.debug('Fibrinogen Analysis called')
            status, result = FibrinogenResultAnalysis(data, mode=mode, reason=reason,)
            value = status['channelResult']
            stat = status.get('stat')
            self.debug('<DataProcessModule> saveResult: Fibrinogen analysis complete. \n' +
                       '                                Status: ' + stat + '\n' +
                       '                                Scan avg. result: ' + value + '\n')

            # display the result to LED:        
            if result=='Positive':
                self.main.peripheral.sendMsgToLED('result.positive')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.fibrinogen.finishedTest',
                                                   'data': value})
            elif result=='Negative':
                self.main.peripheral.sendMsgToLED('result.negative')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.fibrinogen.finishedTest',
                                                   'data': value})
            elif result=='Average':
                self.main.peripheral.sendMsgToLED('result.average')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.fibrinogen.finishedTest',
                                                   'data': value})
            elif result=='Error':
                self.main.peripheral.sendMsgToLED('result.error')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.fibrinogen.finishedTestError',
                                                   'data': value})
            else:
                self.main.peripheral.sendMsgToLED('result.invalid')
                self.main.client.notifyBLEClients({'status': 'ok',
                                                   'action': 'dataProcess.fibrinogen.finishedTestError',
                                                   'data': value})

        # upload the result to cloud.
        uploaded = False
        if self.main.cloud.postPendingTestResult(value):
            uploaded = True
            
        # save data to dataStore module.
        self.main.dataStore.addData(idx=self.dataStoreIndex, uploaded=uploaded,
                                    data=data, status=status, result=value)      

        self.data.reset()
        self.dataStoreIndex = None


    # DEMO: set ratio
    @labelForDev
    def dmScaleRatio(self, ratio: float):
        "get or set ratio only set if >1 <=3"
        if (ratio > 1) and ratio <= 3:
            self.scaleRatio = ratio
            self.data.scaleRatio = ratio
            return f'Set ratio to {ratio}.'
        return f'Current ratio is {self.scaleRatio}, cannot set to {ratio}.'

    @labelForDev
    def rePredictResult(self, index: str, pwd: str = ""):
        "re predict result with SVC model from scan data."
        data = self.main.dataStore.getDataFromIndex(
            index, pwd=pwd, returnRaw=True)
        if isinstance(data, str):
            return data
        _, result = CoivdResultAnalysis(
            data.get('data', {}), mode='rePredict',)
        self.main.dataStore.editResult(index, result, pwd)
        return {"index":index,"result":result}

    
    def fitPeak(self,v,a):
        return fitPeak(v,a)

    def appendData(self, channel, timeStamp, voltage, amp, **kwargs):
        "append data to the current scan."
        # temp = self.main.heating.getCurrentTemp()
        fitres = self.fitPeak(voltage, amp)
        other = kwargs.get('other',None)
        self.data.appendData(channel, timeStamp, voltage, amp, fitres,other)
        return fitres

    def swapData(self, channel, seed):
        "swap data of a channel"
        # DEMO: swap out data.
        dataLength = len(self.data.scan[channel]['time'])
        self.data.scan[channel]['rawdata'] = [
            [v, [round(a, 6) for a in amp]] for v, amp in seed[0:dataLength]]
        self.data.scan[channel]['fit'] = [
            fitPeak(v, amp) for v, amp in seed[0:dataLength]]

    def appendTemperature(self, timeStamp, temp):
        self.data.appendTemperature(timeStamp, temp)

    def appendFluidFill(self, channel, timeStamp, data):
        self.data.appendFluidFill(channel, timeStamp, data)

    def appendChipInsertion(self, timeStamp, data):
        self.data.appendChipInsertion(timeStamp, data)


    def getRealtimePrediction(self):
        "return the positive negative call on current data."
        # TODO get real time prediction

        return

    @labelForDev
    def getData(self, dataLengthDict: dict = {}):
        """
        get the Data of current measurement.
        dataLengthDict format:
        if is {}; then return the whole data.
        other wise, return missing data. 
        scan:
        {
            'C1':{time:[],rawdata:[],fit:[]}/lengthOfTime
            'C2':{time:[],rawdata:[],fit:[]}/lengthOfTime
        }
        temperature:
        {
            time:[],/lengthOfTime
            data:[],
        }
        fluidFill:
        {
            'C1':{time:[],data:[]}/lengthOfTime
            'C2':{time:[],data:[]}/lengthOfTime
        }
        """
        return self.data.getData(dataLengthDict)
