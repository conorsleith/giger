
from typing import Tuple

from bleak import BleakClient
from loguru import logger
from tacx_trainer_control import TacxTrainerControl

# Define your device UUIDs
TRAINER_UUID = "EA71FD11-431B-3749-30C7-AF3717508D38"
HR_MONITOR_UUID = "AC9BB01F-731A-FF9A-A51F-3483EC6F638E"

# Define characteristic UUIDs
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

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

async def set_up_hr():
    logger.info("Connecting to heart rate monitor")
    hr_client = BleakClient(HR_MONITOR_UUID)
    await hr_client.connect()
    if not hr_client.is_connected:
        raise RuntimeError("Failed to connect to Heart Rate Monitor.")
    logger.info("Heart rate monitor connected!")
    return hr_client

async def set_up_trainer():
    trainer_client = BleakClient(TRAINER_UUID)
    logger.info("Connecting to trainer")
    await trainer_client.connect()
    if not trainer_client.is_connected:
        raise RuntimeError("Failed to connect to trainer")
    logger.info("Trainer connected!")
    trainer_control = TacxTrainerControl(trainer_client)
    return trainer_control
    

async def get_devices():
    trainer_control, hr_client = await set_up_devices(TRAINER_UUID, HR_MONITOR_UUID)
    return trainer_control, hr_client
