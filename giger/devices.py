
from threading import Thread
from typing import Tuple

from bleak import BleakClient, BleakScanner
from loguru import logger
from pycycling.tacx_trainer_control import TacxTrainerControl

# Define your device UUIDs
TRAINER_UUID = "EA71FD11-431B-3749-30C7-AF3717508D38"
# TRAINER_UUID = "5058AE50-D605-4CE1-1D84-7F8A10DBDC78"
TACX_UART_BLE_UUID = "6e40fec1-b5a3-f393-e0a9-e50e24dcca9e"

HR_MONITOR_UUID = "AC9BB01F-731A-FF9A-A51F-3483EC6F638E"
# HR_MONITOR_UUID = "E990CA57-5D7B-089E-11EE-54FB2E917B38"
# Define characteristic UUIDs
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


class TacXWrapper:
    user_weight = 75
    bicycle_weight = 15
    wheel_diameter = 2.1
    gear_ratios = {
        1: 0.75,
        2: 0.87,
        3: 0.99,
        4: 1.11,
        5: 1.23,
        6: 1.38,
        7: 1.53,
        8: 1.68,
        9: 1.86,
        10: 2.04,
        11: 2.22,
        12: 2.40,
        13: 2.61,
        14: 2.82,
        15: 3.03,
        16: 3.24,
        17: 3.49,
        18: 3.74,
        19: 3.99,
        20: 4.24,
        21: 4.54,
        22: 4.84,
        23: 5.14,
        24: 5.49
    }

    def __init__(self, client):
        self._client = client
        self._trainer_control = TacxTrainerControl(client)
        self._gear = 12

    async def set_target_power(self, power):
        await self._trainer_control.set_target_power(power)

    async def set_gear(self, gear):
        try:
            ratio = self.gear_ratios[gear]
            await self._trainer_control.set_user_configuration(
                self.user_weight, self.bicycle_weight, self.wheel_diameter,
                self.gear_ratios[gear]
            )
            self._gear = gear
        except KeyError:
            logger.info(f"Invalid gear number: {gear}")
            return

    async def increment_gear(self):
        await self.set_gear(self._gear + 1)

    async def decrement_gear(self):
        await self.set_gear(self._gear - 1)


async def set_up_devices(trainer_device_uuid: str, hr_device_uuid: str) -> Tuple[TacxTrainerControl, BleakClient]:
    trainer_client = BleakClient(trainer_device_uuid)
    hr_client = BleakClient(hr_device_uuid)
    
    logger.info("Connecting to heart rate monitor")
    await hr_client.connect()
    if not hr_client.is_connected:
        raise RuntimeError("Failed to connect to Heart Rate Monitor.")
    logger.info("Heart rate monitor connected!")

    logger.info("Connecting to trainer")
    await trainer_client.connect()
    if not trainer_client.is_connected:
        raise RuntimeError("Failed to connect to trainer")
    logger.info("Trainer connected!")
    trainer_control = TacxTrainerControl(trainer_client)
    return trainer_control, hr_client

async def set_up_hr(uuid=HR_MONITOR_UUID):
    logger.info("Connecting to heart rate monitor")
    hr_client = BleakClient(uuid)
    await hr_client.connect()
    if not hr_client.is_connected:
        raise RuntimeError("Failed to connect to Heart Rate Monitor.")
    logger.info("Heart rate monitor connected!")
    return hr_client

async def set_up_trainer(uuid=TRAINER_UUID):
    trainer_client = BleakClient(uuid)
    logger.info("Connecting to trainer")
    await trainer_client.connect()
    if not trainer_client.is_connected:
        raise RuntimeError("Failed to connect to trainer")
    logger.info("Trainer connected!")
    trainer_control = TacxTrainerControl(trainer_client)
    return trainer_control
    
async def set_up_trainer_wrapper():
    trainer_client = BleakClient(TRAINER_UUID)
    logger.info("Connecting to trainer")
    await trainer_client.connect()
    if not trainer_client.is_connected:
        raise RuntimeError("Failed to connect to trainer")
    logger.info("Trainer connected!")
    trainer_control_wrapper = TacXWrapper(trainer_client)
    return trainer_control_wrapper

async def get_devices():
    trainer_control, hr_client = await set_up_devices(TRAINER_UUID, HR_MONITOR_UUID)
    return trainer_control, hr_client
