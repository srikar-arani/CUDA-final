import dbus
import dbus.service
import dbus.mainloop.glib
import dbus.exceptions
from typing import Dict
import socket


try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject


BLUEZ_SERVICE_NAME = "org.bluez"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

GATT_MANAGER_IFACE = "org.bluez.GattManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_IFACE = "org.bluez.GattDescriptor1"


class BleTools(object):
    @classmethod
    def get_bus(self):
        bus = dbus.SystemBus()
        return bus

    @classmethod
    def find_adapter(self, bus):
        remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, "/"), DBUS_OM_IFACE)
        objects = remote_om.GetManagedObjects()

        for o, props in objects.items():
            if LE_ADVERTISING_MANAGER_IFACE in props:
                return o

        return None

    @classmethod
    def power_adapter(self):
        adapter = self.get_adapter()
        adapter_props = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                       "org.freedesktop.DBus.Properties");
        adapter_props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))


class BLEAdvertisement(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/advertisement"

    def __init__(self, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = BleTools.get_bus()
        self.ad_type = advertising_type
        self.local_name = None
        self.service_uuids = None
        self.solicit_uuids = None
        self.manufacturer_data = None
        self.service_data = None
        self.include_tx_power = None
        dbus.service.Object.__init__(self, self.bus, self.path)

    def get_properties(self):
        properties = dict()
        properties["Type"] = self.ad_type

        if self.local_name is not None:
            properties["LocalName"] = dbus.String(self.local_name)

        if self.service_uuids is not None:
            properties["ServiceUUIDs"] = dbus.Array(self.service_uuids,
                                                    signature='s')
        if self.solicit_uuids is not None:
            properties["SolicitUUIDs"] = dbus.Array(self.solicit_uuids,
                                                    signature='s')
        if self.manufacturer_data is not None:
            properties["ManufacturerData"] = dbus.Dictionary(
                self.manufacturer_data, signature='qv')

        if self.service_data is not None:
            properties["ServiceData"] = dbus.Dictionary(self.service_data,
                                                        signature='sv')
        if self.include_tx_power is not None:
            properties["IncludeTxPower"] = dbus.Boolean(self.include_tx_power)

        if self.local_name is not None:
            properties["LocalName"] = dbus.String(self.local_name)

        return {LE_ADVERTISEMENT_IFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service_uuid(self, uuid):
        if not self.service_uuids:
            self.service_uuids = []
        self.service_uuids.append(uuid)

    def add_solicit_uuid(self, uuid):
        if not self.solicit_uuids:
            self.solicit_uuids = []
        self.solicit_uuids.append(uuid)

    def add_manufacturer_data(self, manuf_code, data):
        if not self.manufacturer_data:
            self.manufacturer_data = dbus.Dictionary({}, signature="qv")
        self.manufacturer_data[manuf_code] = dbus.Array(data, signature="y")

    def add_service_data(self, uuid, data):
        if not self.service_data:
            self.service_data = dbus.Dictionary({}, signature="sv")
        self.service_data[uuid] = dbus.Array(data, signature="y")

    def add_local_name(self, name):
        if not self.local_name:
            self.local_name = ""
        self.local_name = dbus.String(name)

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature="s",
                         out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE,
                         in_signature='',
                         out_signature='')
    def Release(self):
        self.logger.debug('%s: Released!' % self.path)

    def register_ad_callback(self):
        self.logger.debug("BLE advertisement initialized")

    def register_ad_error_callback(self):
        self.logger.debug("Failed to initialize BLE advertisement")

    def register(self):
        bus = BleTools.get_bus()
        adapter = BleTools.find_adapter(bus)
        ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                    LE_ADVERTISING_MANAGER_IFACE)
        ad_manager.RegisterAdvertisement(self.get_path(), {},
                                         reply_handler=self.register_ad_callback,
                                         error_handler=self.register_ad_error_callback)


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class NotPermittedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotPermitted"


class BLEServer(dbus.service.Object, ):
    def __init__(self, logger):
        dbus.mainloop.glib.threads_init()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.mainloop = GObject.MainLoop()
        self.bus = BleTools.get_bus()
        self.path = "/"
        self.services = []
        self.next_index = 0
        self.logger = logger
        dbus.service.Object.__init__(self, self.bus, self.path)

    def set_bt_status(self, status):
        self.logger.main.client.bluetoothStatus = status

    def get_char_value(self, name):
        if len(self.services) > 0:
            return self.services[0].get_characteristic_value_by_name(name)

    def update_char_value(self, name:str, value:str, notify:bool):
        if len(self.services) > 0:
            self.services[0].set_characteristic_value_by_name(name, value, notify)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()
        return response

    def register_app_callback(self):
        self.set_bt_status('running')
        self.logger.debug("BLE services initialized")

    def register_app_error_callback(self, error):
        self.set_bt_status(str(error))
        self.logger.debug("BLE services failed to initialize: " + str(error))

    def register(self):
        adapter = BleTools.find_adapter(self.bus)
        service_manager = dbus.Interface(
            self.bus.get_object(BLUEZ_SERVICE_NAME, adapter),
            GATT_MANAGER_IFACE)
        service_manager.RegisterApplication(self.get_path(), {},
                                            reply_handler=self.register_app_callback,
                                            error_handler=self.register_app_error_callback)

    def run(self):
        self.mainloop.run()

    def quit(self):
        self.mainloop.quit()
        self.logger.debug("BLE released")


class Service(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/service"
    characteristic_values: Dict[str, bytearray]

    def __init__(self, index, uuid, primary):
        self.bus = BleTools.get_bus()
        self.path = self.PATH_BASE + str(index)
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        self.next_index = 0
        self.characteristic_values = dict()
        dbus.service.Object.__init__(self, self.bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(
                    self.get_characteristic_paths(),
                    signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        result = []
        for chrc in self.characteristics:
            result.append(chrc.get_path())
        return result

    def get_characteristics(self):
        return self.characteristics

    def get_characteristic_value_by_name(self, name):
        "Decodes the utf-8 encoded byte array of a characteristic and returns the value as a str"
        return "".join([str(x) for x in self.characteristic_values[name]])

    def set_characteristic_value_by_name(self, name: str, value: str, notify: bool):
        self.characteristic_values[name] = bytearray(value, 'utf-8')
        if notify:
            cs = self.characteristics
            for c in cs:
                if c.__class__.__name__ == name:
                    c.notify_devices()
                    return

    def get_bus(self):
        return self.bus

    def get_next_index(self):
        idx = self.next_index
        self.next_index += 1
        return idx

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    def __init__(self, uuid, flags, service):
        index = service.get_next_index()
        self.path = service.path + '/char' + str(index)
        self.bus = service.get_bus()
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.descriptors = []
        self.next_index = 0
        self.notifying = False
        dbus.service.Object.__init__(self, self.bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self.service.get_path(),
                'UUID': self.uuid,
                'Flags': self.flags,
                'Descriptors': dbus.Array(
                    self.get_descriptor_paths(),
                    signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        result = []
        for desc in self.descriptors:
            result.append(desc.get_path())
        return result

    def get_descriptors(self):
        return self.descriptors

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE,
                         in_signature='a{sv}',
                         out_signature='ay')
    def ReadValue(self, options):
        return self.service.characteristic_values[self.__class__.__name__]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        self.logger.debug('Default WriteValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        if not self.notifying:
            self.notifying = True
            self.notify_devices()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        if self.notifying:
            self.notifying = False

    @dbus.service.signal(DBUS_PROP_IFACE,
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    def get_bus(self):
        return self.bus

    def get_next_index(self):
        idx = self.next_index
        self.next_index += 1
        return idx

    def notify_devices(self):
        if self.notifying:
            self.PropertiesChanged(
                "org.bluez.GattCharacteristic1",
                {
                    'Value': dbus.ByteArray(self.service.characteristic_values[self.__class__.__name__])
                }, [])


class Descriptor(dbus.service.Object):
    def __init__(self, uuid, flags, characteristic):
        index = characteristic.get_next_index()
        self.path = characteristic.path + '/desc' + str(index)
        self.uuid = uuid
        self.flags = flags
        self.chrc = characteristic
        self.bus = characteristic.get_bus()
        dbus.service.Object.__init__(self, self.bus, self.path)

    def get_properties(self):
        return {
            GATT_DESC_IFACE: {
                'Characteristic': self.chrc.get_path(),
                'UUID': self.uuid,
                'Flags': self.flags,
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE,
                         in_signature='a{sv}',
                         out_signature='ay')
    def ReadValue(self, options):
        return self.chrc.ReadValue()

    @dbus.service.method(GATT_DESC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        self.logger.debug('Default WriteValue called, returning error')
        raise NotSupportedException()


"""


        CUDA ADVERTISEMENT DEFINITION


"""


class ReaderAdvertisement(BLEAdvertisement):
    def __init__(self, index, logger):
        BLEAdvertisement.__init__(self, index, "peripheral")
        self.add_local_name(socket.gethostname())
        self.include_tx_power = True
        self.logger = logger


"""

        CUDA SERVICE DEFINITION

            - BLE IS IMPLEMENTED WITH A SINGLE CUSTOM GATT SERVICE
            - EXTENDS SERVICE CLASS WITH A DICTIONARY OF CHARACTERISTIC NAMES : VALUES
            - EACH CHARACTERISTIC HAS A UTF-8 ENCODED STRING VALUE

"""


class ReaderService(Service):
    def __init__(self, index):
        Service.__init__(self,
                         index=index,
                         uuid="ab173c6c-8493-412d-897c-1974fa74fc13",
                         primary=True)

        self.characteristics = [
            DeviceData(self),
            DeviceStatus(self),
            DeviceAction(self)
        ]

        for c in self.characteristics:
            self.characteristic_values[c.__class__.__name__] = bytearray("{}", 'utf-8')

class DeviceDataDesc(Descriptor):
    def __init__(self, characteristic):
        Descriptor.__init__(
            self,
            uuid='04cb0eb1-8b58-44d0-91e4-080af33438ba',
            flags=['read', 'write'],
            characteristic=characteristic)

class DeviceData(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(
            self,
            uuid='04cb0eb1-8b58-44d0-91e4-080af33438bb',
            flags=['read', 'notify'],
            service=service)
        self.add_descriptor(DeviceDataDesc(self))

class DeviceStatusDesc(Descriptor):
    def __init__(self, characteristic):
        Descriptor.__init__(
            self,
            uuid='04cb0eb1-8b58-44d0-91e4-080af33438bc',
            flags=['read', 'write'],
            characteristic=characteristic)

class DeviceStatus(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(
            self,
            uuid='04cb0eb1-8b58-44d0-91e4-080af33438bd',
            flags=['read', 'notify'],
            service=service)
        self.add_descriptor(DeviceStatusDesc(self))

class DeviceActionDesc(Descriptor):
    def __init__(self, characteristic):
        Descriptor.__init__(
            self,
            uuid='04cb0eb1-8b58-44d0-91e4-080af33438be',
            flags=['read', 'write'],
            characteristic=characteristic)

class DeviceAction(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(
            self,
            uuid='04cb0eb1-8b58-44d0-91e4-080af33438bf',
            flags=['read', 'notify'],
            service=service)
        self.add_descriptor(DeviceActionDesc(self))