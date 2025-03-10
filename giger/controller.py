import struct

from collections import deque
from typing import Callable, Optional, Union

from bleak import BleakClient
from devices import HR_MEASUREMENT_UUID
from loguru import logger
from settings import settings
from simple_pid import PID
from pycycling.tacx_trainer_control import TacxTrainerControl

# Safety limits
MAX_POWER = 500  # Maximum power in watts
MIN_POWER = 50  # Minimum power in watts


class Giger:
    def __init__(
        self,
        trainer_control: Optional[TacxTrainerControl],
        hr_client: Optional[BleakClient],
        max_power: int = 600,
        min_power: int = 50,
        hr_setpoint: int = 135,
        starting_power: int = 180,
        update_hr_callback: Optional[Callable] = None,
        update_power_callback: Optional[Callable] = None,
    ):
        """
        Initialize the Giger class.

        Parameters:
        trainer_control (TacxTrainerControl): The trainer control interface.
        hr_client (BleakClient): The BLE client for heart rate monitoring.
        hr_setpoint (int, optional): Desired heart rate in bpm. Default is 135.
        hr_tolerance (int, optional): Acceptable deviation in bpm. Default is 3.
        power_step (int, optional): Watts to adjust per step. Default is 5.
        max_power (int, optional): Maximum power in watts. Default is 600.
        min_power (int, optional): Minimum power in watts. Default is 50.
        """

        # Set up attributes
        self.trainer_control: Union[TacxTrainerControl, None] = None
        self.hr_client: Union[BleakClient, None] = None
        self.hr_setpoint: int = hr_setpoint
        self.max_power: int = max_power
        self.min_power: int = min_power
        self._update_hr_callback: Callable = update_hr_callback or (lambda hr: None)
        self._update_power_callback: Callable = update_power_callback or (
            lambda power: None
        )
        self._is_running: bool = False
        self._never_started: bool = True
        self._instant_power_deque = deque(maxlen=3)

        self.pid = PID(1, 0.1, 0.05, setpoint=self.hr_setpoint, sample_time=5)
        self.pid.output_limits = (self.min_power, self.max_power)

        self.pid.auto_mode = False

        self.current_pid_control_power: int = starting_power
        self.current_hr: int = 0

        if trainer_control is not None:
            self.trainer_control = trainer_control

        if hr_client is not None:
            self.hr_client = hr_client

    @property
    def current_trainer_power(self):
        if not self._instant_power_deque:
            return 0
        return sum(self._instant_power_deque) / len(self._instant_power_deque)

    async def hr_subscribe(self):
        await self.hr_client.start_notify(
            HR_MEASUREMENT_UUID, self.hr_notification_callback
        )
        logger.info("hr subscribed")
        settings.last_used_hrm_uuid = self.hr_client.address

    def start(self):
        if self.trainer_control is None or self.hr_client is None:
            logger.info("Trainer control and HR client must be added to start")
            return False
        self._is_running = True
        self.pid.auto_mode = True
        self._never_started = False
        return True

    def stop(self):
        self._is_running = False
        # self.pid.auto_mode = False
        logger.info("stopping")

    def pause(self):
        self._is_running = False

    def reset(self):
        self.pid.reset()

    def set_kp(self, value):
        # logger.info(f"Setting Kp to {value}")
        self.pid.Kp = value

    def set_ki(self, value):
        # logger.info(f"Setting Ki to {value}")
        self.pid.Ki = value

    def set_kd(self, value):
        # logger.info(f"Setting Kd to {value}")
        self.pid.Kd = value

    def set_target_hr(self, value):
        self.hr_setpoint = value

    def set_min_power(self, watts):
        self.min_power = watts
        self.pid.output_limits = (self.min_power, self.max_power)

    def set_max_power(self, watts):
        self.max_power = watts
        self.pid.output_limits = (self.min_power, self.max_power)

    async def set_hr_client(self, hr_client):
        if self.hr_client is not None:
            await self.hr_client.disconnect()
        self.hr_client = hr_client
        await self.hr_client.connect()
        await self.hr_subscribe()

    async def set_trainer_control(self, trainer_control):
        self.pause()
        if self.trainer_control is not None:
            await self.trainer_control._client.disconnect()
        self.trainer_control = trainer_control
        if not self.trainer_control._client.is_connected:
            await self.trainer_control._client.connect()
        # self.trainer_control.set_general_fe_data_page_handler(lambda x: print(x))
        self.trainer_control.set_specific_trainer_data_page_handler(
            self._specific_trainer_data_page_handler
        )
        await self.trainer_control.enable_fec_notifications()
        await self.set_current_power(self.current_pid_control_power)
        settings.last_used_trainer_uuid = self.trainer_control._client.address

        ## not sure why this was here, but let's leave it for now, commented out
        # if not self._never_started:
        #     self.start()

    def _specific_trainer_data_page_handler(self, data):
        self._instant_power_deque.append(data.instantaneous_power)
        self._update_power_callback(self.current_trainer_power)

    @staticmethod
    def parse_hr_data(data: bytearray) -> int:
        hr: int
        flags = data[0]
        hr_format = flags & 0x01
        if hr_format:
            hr = struct.unpack("<H", data[1:3])[0]
        else:
            hr = data[1]
        return hr

    async def hr_notification_callback(self, _, data: bytearray):
        hr: int = self.parse_hr_data(data)
        self.current_hr = hr
        logger.info(f"Received new HR value {hr}")
        self._update_hr_callback(hr)
        control = self.pid(hr)
        try:
            logstr = f"PID control value changing from {self.current_pid_control_power:.2f} to {control: .2f}"
            if not self._is_running:
                logstr += " (but doing nothing because PID control disabled)"
            logger.info(logstr)
        except (TypeError, ValueError):
            pass
        if not self._is_running:
            return
        if control is not None:
            new_power = int(control)
            await self.set_current_power(new_power)

    async def set_current_power(self, watts):
        await self.trainer_control.set_target_power(watts)
        self.current_pid_control_power = watts
        # self._update_power_callback(watts)
