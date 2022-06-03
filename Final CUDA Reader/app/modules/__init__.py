"""
Modules with standalone function.
"""
from app.modules.heatingModule import HeatingModule
from app.modules.measurementModule import MeasurementModule
from app.modules.dataProcessModule import DataProcessModule
from app.modules.clientModule import ClientModule
from app.modules.dataStoreModule import DataStoreModule
from app.modules.peripheralModule import PeripheralModule
from app.modules.httpServerModule import HttpServerModule
from app.modules.beeModule import BeeModule
from app.modules.statusModule import StatusModule
from app.modules.configModule import ConfigModule
from app.modules.cloudModule import CloudModule
# all modules except for MainModule
# DO NOT include main module in moudleNameDict.
# the order of these modules are the start up order.
moduleNameDict = {(i.__name__[0].lower() + i.__name__[1:-6]): i for i in (HeatingModule, ConfigModule,
                                                                          MeasurementModule, DataProcessModule,  
                                                                          DataStoreModule, PeripheralModule,
                                                                          StatusModule, ClientModule, 
                                                                          HttpServerModule,CloudModule)}  # BeeModule, HttpServerModule, CloudModule

# it's important to import mainModule LAST, otherwise cause error.
from app.modules.mainModule import MainModule