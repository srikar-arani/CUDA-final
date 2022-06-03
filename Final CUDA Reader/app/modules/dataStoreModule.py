from app.utils import LoopEventListener,labelForDev,Task
from app.setup.install import  SYSTEM_ID,SYSTEM_SERIAL
from app.utils import createFolder
from bson.objectid import ObjectId
from datetime import datetime
import time,requests,pickle,base64
from cryptography.fernet import Fernet,InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from threading import Thread
import sqlite3,shutil,os
from queue import Queue,Empty
from functools import wraps
# TODO: data Store Module
# 1. store more information about the data 
# 2. upload data to cloud.
# 3. local storage 
# 4. how should the phone app interface with storage. 
# 5. data compression after certain size. 
# 6. ability to handle sudden power down. 
# 7. Encryption with cryptography



class BackupDataTask(Task):
    def __init__(self,logger,storeDataInterval):
        super().__init__(delay=1200)
        self.interval = storeDataInterval # save data every hour.
        self.logger = logger
        self.isSaving = False
         
    def task(self):
        self.nextRun(delay = self.interval)
        self.isSaving = True 
        try:
            self.logger.backup()
        except Exception as e:
            self.logger.error(f"DataStoreModule.BackupDataTask.task error <{e}>")
        finally:
            self.isSaving = False
        
    def done(self):
        self.status = 'done'

class DataBaseOperationTask(Task):
    """
    task to operate on database.
    in the staticmethod of this Task Class, all the self are referring to the dataStoreModule instance.
    """
    def __init__(self,logger):
        super().__init__(delay=0.01)
        self.logger = logger
    
    @staticmethod
    def dispatchToDatabaseTask(func):
        "function decorator to make a func execute in task."
        @wraps(func)
        def wrap(ins,*args,**kwrags):
            t0 = time.monotonic()
            ts = time.monotonic()
            ins.callQueue.put((func.__name__, args,kwrags,ts))
            # print(f"put func to call queue {func.__name__}")
            while True:
                if time.monotonic() - t0 > 60:
                    ins.logger.critical(f'DataStoreModule.{func.__name__}.dispatchToDatabaseTask error: Timeout>60s')
                    return f'Timeout: DataBaseOperationTask take over 30 seconds to finish.'
                try:                    
                    res,id,funcname = ins.resultQueue.get(timeout=1)
                except Empty:
                    time.sleep(0.1)
                    continue                    
                if id == ts and funcname == func.__name__:
                    return res
                else:
                    if t0 - id>120:
                        # delete the result that has been in queue for over 120 seconds.
                        ins.logger.error(f'DataStoreModule.{funcname}.dispatchToDatabaseTask error: result sit for over 120s.')
                        continue
                    else:
                        ins.logger.debug(f'DataStoreModule.{func.__name__}.dispatchToDatabaseTask \
                            Result Mismatch: Expect:<{func.__name__}-{ts}> Got:<{funcname}-{id}>, put back.')                        
                        time.sleep(0.1)
                        ins.resultQueue.put((res,id,funcname))                                                     
        return wrap

    
    @staticmethod
    def addData(self,status,data,result,idx,**kwargs):
        "add data to the recent self.newDataIndex "
        if self.newDataIndex:
            if idx == self.newDataIndex:
                # update new data index.            
                self.DB_updateData({'status':status,
                                    'data':data, 
                                    'result':result,
                                    'uploaded':kwargs.get('uploaded',None)},where={'_id':self.newDataIndex})
                self.newDataIndex = None
            else:
                self.error(f"DataStoreModule.addData: index didn't match: idx:{idx}, newDataIndex:{self.newDataIndex}")
        else:
            self.error("DataStoreModule.addData: self.newDataIndex is not created.")
    
    @staticmethod
    def updateDataById(self,id,data={}):
        """
        update a data in database from ID.
        data should be a dictionary with following fields:
        meta, data,result, status
        """
        if id and data:
            self.DB_updateData(data,where={'_id':id})
            return f'Data updated to {id}.'
        else:
            return 'Must provide id and data.'

    
    @staticmethod
    def dumpPickle(self,pwd:str=""):
        "dump all the data to pickle bytes"
        decryptor = self.getEncryptor(pwd).decrypt
        fields = self.DB_rawFields()
        res = self.cur.execute(f'SELECT {",".join(fields+["createdAt"])} FROM {self.dbName} ORDER BY createdAt') 
        data =  [self.decryptMetaData(self.DB_dataToDict(dict(zip(fields,row))),pwd,decryptor,) 
                    for row in res]
        return pickle.dumps(data)
            

    @staticmethod
    def editMeta(self,index:str,meta:dict,pwd:str=""):
        "edit meta data with updates in meta dict."
        item = self.DB_getDataFromIndex(index,fields=('meta',))
        if item:        
            decryptor = self.getEncryptor(pwd).decrypt
            oldmeta = self.decryptMetaData(item,pwd,decryptor)['meta']
            if oldmeta.get('error',None):
                return f"Cannot decrypt {index}."
            oldmeta.update(meta)
            newmeta = self.getEncryptor(pwd).encrypt(pickle.dumps(oldmeta))
            self.DB_updateData(data={'meta':newmeta},where={'_id':index})
            return f"Updated meta for {index}."
        else:
            return f"<index> not found in data."

    @staticmethod
    def editResult(self,index:str,result:str,pwd:str=""):
        "edit result data"
        item = self.DB_getDataFromIndex(index,fields=('result',))
        if item: 
            self.DB_updateData(data={'result':result},where={'_id':index})
            return f"Updated result for {index}."
        else:
            return f"<index> not found in data."


    @staticmethod
    def uploadData(self,index:str,pwd:str=""):
        item = self.DB_getDataFromIndex(index,)      
        if item:            
            decryptor = self.getEncryptor(pwd).decrypt
            data = self.decryptMetaData(item,pwd,decryptor) 
            if data['meta'].get('error',None):
                return f"Cannot decrypt {index}."
            Thread(name='UploadData',target=self.ngs_server_uploadData,args=(data,item),daemon=True).start()
            return f"Uploading data {index}..."
        return f"<index> not found in data."

    @staticmethod
    def addIndex(self,meta:dict={},pwd:str=""):
        createdAt = datetime.now().isoformat()
        meta.update(created = createdAt,device=SYSTEM_ID)
        # encrypt meta here
        meta = self.getEncryptor(pwd).encrypt(pickle.dumps(meta))
        
        # this id is not goint to overlap on the same raspberryPi
        self.newDataIndex = str(ObjectId())

        self.DB_insertData({
            'createdAt': createdAt,
            'meta': meta,
            '_id': self.newDataIndex
        })        
        return self.newDataIndex

    @staticmethod
    def getRecentPaginated(self,page:int=0,perpage:int=10,pwd:str="",returnRaw=True):        
        fields = self.DB_rawFields(returnRaw)
      
        decryptor = self.getEncryptor(pwd).decrypt

        records = self.cur.execute(f'SELECT {",".join(fields)} FROM \
                    {self.dbName} ORDER BY createdAt desc LIMIT ?,?',(page*perpage,perpage+1)).fetchall()

        items = [ self.decryptMetaData(self.DB_dataToDict(dict(zip(fields,row))),pwd,decryptor,) 
                    for row in records]

        hasNext = True if len(items)>perpage else False
        hasPrev = True if page>0 else False
        
        return {'items':items[0:perpage], 'hasNext': hasNext,'hasPrev':hasPrev}

    @staticmethod
    def getDataFromIndex(self,index:str, pwd:str="",returnRaw=False):
        fields = self.DB_rawFields(returnRaw)

        item = self.DB_getDataFromIndex(index,fields=fields)
        if item:            
            decryptor = self.getEncryptor(pwd).decrypt
            return self.decryptMetaData(item,pwd,decryptor,)
        else:
            return f"<{index}> not found in data."

    @staticmethod
    def getDataFromIndexes(self,indexes:list, pwd:str="",returnRaw=True):
        #TODO
        # use a more efficient where clause to filter out indexes in one run. 
        fields = self.DB_rawFields(returnRaw)
        items = []
        decryptor = self.getEncryptor(pwd).decrypt
        for index in indexes:
            item = self.DB_getDataFromIndex(index,fields=fields)
            if item:                            
                items.append(self.decryptMetaData(item,pwd,decryptor,))
        return {'items':items}

    @staticmethod
    def getDataAfterIndex(self, index:str, pwd:str="",returnRaw=True):
        item = self.DB_getDataFromIndex(index,fields=['createdAt'])
        if item:
            decryptor = self.getEncryptor(pwd).decrypt
            fields = self.DB_rawFields(returnRaw)
            records = self.cur.execute(f'SELECT {",".join(fields)} FROM {self.dbName} \
                WHERE createdAt >= ? ORDER BY createdAt desc',(item['createdAt'],)).fetchall()
            return [self.decryptMetaData(self.DB_dataToDict(dict(zip(fields,row))),pwd,decryptor,) 
                    for row in records]
        return []

    @staticmethod
    def deleteDataByIndex(self, index:str):
        "delete a data by its index."
        deletedcount = self.DB_deleteDataFromIndex(index)
        if deletedcount:
            return f'id-{index} deleted.'
        else:
            return f"id-{index} doesn't exist."


    def task(self):
        self.nextRun(delay=0.1)
        try:
            funcname,args,kwargs,ts = self.logger.callQueue.get(timeout=1)
            # print(f'got {funcname} from call queue')
            try:
                res = getattr(self,funcname)(self.logger,*args,**kwargs)
            except Exception as e:
                res = f"{e}"
            self.logger.resultQueue.put((res,ts,funcname))
        except Empty as e:
            pass 
       
class DataStoreModule(LoopEventListener):
    """
    Interface for storing data.
    Locally stored as sqlite database. 
    The data structure is as following:
    table name: data;
    columns:
    createdAt: text of iso time string, to help order data.
    _id: text,
    meta: blob, using picke bytes:
        {'metainfo',will always have 'created'}, # this information need to be encrypted.
    data: blob, pickle bytes of measurement raw data:
        {'time': [timepoint in minutes], 'rawdata': [[v,a]...], 'fit': [{fitresult}...], 'temp':[]} 
    result: text, 'positive' or 'negative' or reason of abort.
        # currently using mock result, can store more complicated results later. 
    status: blob, status: 'ok' or 'abort', / other status maybe added later.
    """
    def initialize(self,storeDataInterval,uploadURL,**kwargs):
        self.dbName = 'data'
        self.dbFile = createFolder('data_storage') / 'measurementResults.sqlite' 
        self.dbBackUpFile = createFolder('data_storage') / 'backup.sqlite' 
        
        self.newDataIndex = None
        self.uploadURL = uploadURL

        # use queue to interact.
        self.callQueue = Queue()
        self.resultQueue = Queue()
        

        # Decided to not backup data for now. 
        # TODO: 
        # make the backup only happens at certain time, or block reader usage while backup is in progress.
        # shouldn't remove the task.
        self.backupDataTask = BackupDataTask(logger=self,storeDataInterval=storeDataInterval)
        # self.scheduler.addTask(self.backupDataTask)

        self.databaseOperationTask = DataBaseOperationTask(self)
        self.scheduler.addTask(self.databaseOperationTask)
        
    def connect(self):
        "connect to database. create data table if not exist."
        self.dbConn = sqlite3.connect(self.dbFile)
        self.cur = self.dbConn.cursor()
        table = self.cur.execute("select name from sqlite_master where type = 'table'").fetchone()
        if table and table[0]==self.dbName:
            pass
        else:
            self.cur.execute(f'''CREATE TABLE {self.dbName} (createdAt text, _id text, meta blob, data blob, result text, status blob, uploaded boolean)''')

    def renameBrokenDB(self,file):
        "rename the self.dbFile to a different name."
        if os.path.exists(file):
            newname = file + '_broken'
            while os.path.exists(newname):
                newname += '+'
            shutil.move(file,newname)
            return newname
        return f'{file} not exist.'
    
    def backup(self):
        # def progress(status, remaining, total):
        #     self.debug(f'DataStoreModule.backup: Copied {total-remaining} of {total} pages...')
        self.debug(f'DataStoreModule.backup: Backup started.')
        bck = sqlite3.connect(self.dbBackUpFile)        
        with bck:
            self.dbConn.backup(bck, pages=500, ) #progress=progress
        bck.close()
        self.debug(f'DataStoreModule.backup: Backup ended.')

    # database helper functions:
    def DB_dataToDict(self,data):
        "convert certain field of database data dictionary to regular python object"
        for i in ['data','status']:
            if data.get(i,None):
                data[i]=pickle.loads(data[i])
        return data

    def DB_dictToData(self,data):
        "convert certain field of data to database blobs"
        for i in ['data','status']:
            if data.get(i,None):
                data[i]=pickle.dumps(data[i])
        return data

    def DB_updateData(self,data,where=None):
        """
        execute an update task with data on condition where.
        both data and where are dictionaries.  
        """
        data = self.DB_dictToData(data)
        sql = f"UPDATE {self.dbName} SET " + ', '.join(f"{i}=? " for i in data.keys())
        tasks = list(data.values())
        if isinstance(where,dict):
            sql += ' WHERE ' + ' , '.join(f" {i}=? " for i in where.keys())
            tasks.extend(where.values())
        elif isinstance(where,str):
            sql += where
        self.cur.execute(sql,tasks)
        self.dbConn.commit()

    def DB_getDataFromIndex(self,index,fields=('_id','meta','data','result','status')):
        "return an dictionary, or None if not exsit."
        sql = f"SELECT {','.join(fields)} from {self.dbName} WHERE _id=?"
        res = self.cur.execute(sql,(index,)).fetchone()
        if res:            
            return self.DB_dataToDict(dict(zip(fields,res)))
        else:
            return None
        
    def DB_insertData(self,data):
        "insert a new record to database, only have _id and meta field."
        sql = f"INSERT INTO {self.dbName} values (?,?,?,?,?,?,?)"
        values = [data.get('createdAt'), data.get('_id'),data.get('meta'),None,None,None,None]
        self.cur.execute(sql,values)
        self.dbConn.commit()

    def DB_deleteDataFromIndex(self,index):
        "delete index from db, return number of row deleted."
        sql = f"DELETE FROM {self.dbName} WHERE _id=?"
        self.cur.execute(sql,(index,))
        self.dbConn.commit()
        return self.cur.rowcount

    def DB_rawFields(self,returnRaw=True):
        "return the fields that whether contain data depends on returnRaw."
        if returnRaw:
            return ["_id","meta",'data',"result","status"]
        else:
            return ["_id","meta","result","status"]
            
    def getEncryptor(self,pwd):
        "return an encryptor that uses pwd to encrypt or decrypt a byte string."
        pwd = str(pwd).strip()
        if pwd:
            kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=SYSTEM_SERIAL.encode(),
            iterations=100000,
            backend=default_backend())
            key = base64.urlsafe_b64encode(kdf.derive(pwd.encode()))
            return Fernet(key)
        else:
            class VOID:
                encrypt = lambda x: x
                decrypt = lambda x: x
            return VOID

    def decryptMetaData(self,item,pwd,decryptor):
        "decrypt and create a shallow copy of item."
        cp = item.copy()
        if type(cp['meta']) == bytes:
            try:
                cp['meta'] = pickle.loads(decryptor(cp['meta']))
            except InvalidToken as e:
                cp['meta'] = {'error': "Decryption Failed. - Wrong Password."}
                self.debug(f'Decryption failed with Item <{item["_id"]}>, pwd: {pwd}.')
            except Exception as e:
                cp['meta'] = {'error': "Decryption Failed. - Wrong Password."}
                self.error(f"Other uncaught error during decryption: {e}. ")
        return cp

    @labelForDev
    def setUploadURL(self,url):
        """
        set a url for uploading data. 
        the data is send to the url with POST method.
        """
        self.main.SETTINGS[self.name].update(uploadURL=url)
        self.uploadURL = url
        self.main.saveSystemSettings() 
        return url
    
    def ngs_server_uploadData(self,packet,item):
        """
        This is for transforming data to ngs server covid-trace format.
        Deprecated:
            due to the changes in data format, the data packet format is no longer valid for ngs_server.
        """
        try:
            packet.update(dtype='device-trace')
            res = requests.post(self.uploadURL,json=packet)
            if res.status_code == 200 and res.json().get('status') == 'ok':
                item.update(upload='S')
            else:
                item.update(upload='F')
        except Exception as e:
            self.error(f"Upload data to {self.uploadURL} error. Error: {e}.")
            item.update(upload='E')

    def cleanUp(self):
        "clean up"
        "clean up"
        if self.backupDataTask.isSaving:
            self.critical(f'{self}.cleanUp error: backupDataTask is saving')
            time.sleep(1)
        self.dbConn.close()
        
    def initDB(self):
        "initialize db connection, if failed, use from backup file."        
        try:
            self.connect()        
        except Exception as e:
            self.error(f'DataStoreModule.initDB error: {e}')
            try:
                newname = self.renameBrokenDB(self.dbFile)
                if os.path.exists(self.dbBackUpFile):
                    shutil.copy(self.dbBackUpFile,self.dbFile)
                    self.connect()
                    self.info(f"DataStoreModule.initDB restored from backup file. Broken DBFile renamed to {newname}")
                else:
                    self.connect()
                    self.info(f"DataStoreModule.initDB: no backup file found, reinit db. Broken DBFile renamed to {newname}")
            except Exception as e2:
                self.critical(f"DataStoreModule.initDB error restoring backup: {e2}")
                newname = self.renameBrokenDB(self.dbFile)
                newname2 = self.renameBrokenDB(self.dbBackUpFile)
                self.connect()
                self.critical(f'DataStoreModule.initDB recreated blank database. Renamed Broken DB files to {newname} and {newname2}')                               


    def run(self):
        "implement run loop differently, without call clean up after loop is done."
        self.initialize(**self._initialize_kwargs)
        self.register()
        self.initDB()
        while True:
            if self.willStop:
                break 
            try:
                self.scheduler.runNextTask()
            except Exception as e:
                self.error(f"{self}.run: Task Loop {self.scheduler} error: {e}") 
        self.cleanUp()
        self.debug(f"DataStoreModule.run <{self}> exit.")
    

    def stop(self):
        "to stop this module, need to close db in this thread. so call clean up first."        
        self.willStop = True    

    @DataBaseOperationTask.dispatchToDatabaseTask
    def dumpPickle(self):
        "dump all the data to pickle bytes"
        
    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def editMeta(self,index:str,meta:dict,pwd:str=""):
        "edit meta data with updates in meta dict."
    
    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def editResult(self,index:str,result:str,pwd:str=""):
        "edit result data"
    
        

    @DataBaseOperationTask.dispatchToDatabaseTask
    def addData(self,status,data,result,idx,**kwargs):
        "add data to the recent self.newDataIndex "

    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def uploadData(self,index:str,pwd:str=""):
        """
        POST a data packet to self.uploadURL. 
        Packet format:
        {
            _id: ObjectID,
            dtype:'device-trace',
            meta: {},
            status: 'ok' or 'abort',
            data: {'time': [timepoint in minutes], 'rawdata': [[v,a]...], 'fit': [{fitresult}...], 'temp':[]} 
            result: 'positive' or 'negative' # currently using mock result, can store more complicated results later. 
        }
        """

    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def addIndex(self,meta:dict={},pwd:str=""):
        """
        This should be first called when starting a new measurement.
        Generate a objectId index for new measurement.
        Automatically add 'created' field to the meta data with the current time on device. 
        meta is other meta information that device will send in. 
            potentially: {
                'name': name of the patient, 
                'chipid': id of the chip, 
                etc...
            }
        pwd is a string password used for encryption. White space are trimmed off the pwd.
        The meta dict is first pickled, then the bytestring is encrypted with SHA256.
        if pwd=="", will save unencrypted data (but the data is still pickled for interface consistency).


        After the run is done, additional data is added.
        The data is stored in the following fields in sqlite3 datebase:
            'createdAt': createdAt time when the index is generated,
            'meta': meta; encrypted by pwd,
            '_id': ObjectID generated here.
            'data': pickled: {
                scan:
                {
                    'C1':{time:[0,0.1,...(minutes)],
                          rawdata:[[(Vstart,Vend,length of V),[current...]],...],
                          fit:[{pv,pc,fx,fy,err},...]
                    },
                    'C2':{...},
                    'C3':{...},
                    'C4':{...}
                }
                temperature:
                {
                    time:[0,0.1,...(minutes)],
                    data:[65,64.1,...],
                }
                fluidFill:
                {
                    'C1':{time:[0,1.3,...],
                          data:[5,6,...]
                    },
                    'C2':{...},
                    'C3':{...},
                    'C4':{...}
                }
            },
            'result': string, should be the result either positive or negative or abort reason.
            'status': pickled: currently only the string that can be OK or abort
        """         
    

    
    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def getRecentPaginated(self,page:int=0,perpage:int=10,pwd:str="",returnRaw=True):
        """
        get the data in chronical order, with pagination.
        page: which page of the data, 
        perpage: how many records per page. 
        Note: even the un finished data will be returned. 
        pwd: the password for decryption. white space are trimmed.
        returnRaw: whether return raw data.
        """
    
    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def getDataFromIndex(self,index:str, pwd:str="",returnRaw=False):
        """
        return data from an index.
        the index is the device generated ObjectID
        returnRaw: whether return raw data.
        """
    
    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def getDataFromIndexes(self,indexes:list, pwd:str="",returnRaw=True):
        """
        return data from a list of index.
        the index is the device generated ObjectID
        returnRaw: whether return raw data.
        """

    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def getDataAfterIndex(self, index:str, pwd:str="",returnRaw=True):
        """
        get the data that's recorded after given index in time.
        also return the data with this index.
        """

    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def deleteDataByIndex(self, index:str):
        "delete a data by its index."

    @labelForDev
    @DataBaseOperationTask.dispatchToDatabaseTask
    def updateDataById(self,id:str,data:dict={}):
        """
        update a data in database from ID.
        data should be a dictionary with possibly the following fields:
        data,result, status; cannot update meta. 
        """
      