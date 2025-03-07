import asyncio
from collections import OrderedDict

from bleak import BleakScanner, BleakClient, BLEDevice
from customtkinter import CTkFrame, CTkToplevel, CTkScrollableFrame, CTkButton
from devices import HR_SERVICE_UUID, TACX_UART_BLE_UUID
from loguru import logger
from pycycling.tacx_trainer_control import TacxTrainerControl
from tkinter import ttk


class DevicePicker(CTkToplevel):

    def __init__(self, *args, done_callback=None, loop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("550x475")
        self.bind("<Configure>", lambda x: print(x))
        self._done_callback = done_callback or (lambda *args, **kwargs: None)
        self._loop = loop or asyncio.get_event_loop()
        self._scan_stop_event = asyncio.Event()
        self._hrm_devices = OrderedDict()
        self._trainer_devices = OrderedDict()
        self._setup_ui()
        self._scan_future = asyncio.run_coroutine_threadsafe(
            self._device_scan(), self._loop
        )

    def _setup_ui(self):
        self._table_frame = CTkFrame(master=self)
        self._table_frame.grid(column=0, row=0, rowspan=3, columnspan=4)

        self._hr_scroll = CTkScrollableFrame(
            master=self._table_frame, width=530, height=200
        )
        self._hr_scroll.grid(row=0, sticky="nsew")
        self._hr_table: ttk.Treeview = ttk.Treeview(master=self._hr_scroll)
        self._hr_table.heading("#0", text="Heart Rate Monitors")
        self._hr_table.pack(expand=True, fill="both")

        self._trainer_scroll = CTkScrollableFrame(
            master=self._table_frame, width=530, height=200
        )
        self._trainer_scroll.grid(row=1, sticky="nsew")
        self._trainer_table = ttk.Treeview(master=self._trainer_scroll)
        self._trainer_table.heading("#0", text="Smart Trainers")
        self._trainer_table.pack(expand=True, fill="both")

        self._button_frame = CTkFrame(master=self)  # , bg_color=self.cget("bg"))
        self._button_frame.grid(row=3, column=0, columnspan=4, pady=10)
        self._ok_button = CTkButton(master=self._button_frame, text="OK")
        self._ok_button.configure(command=self._ok_button_callback)
        self._cancel_button = CTkButton(master=self._button_frame, text="Cancel")
        self._cancel_button.configure(command=self._cancel_button_callback)
        self._ok_button.grid(column=0, row=0, ipadx=5, padx=5)
        self._cancel_button.grid(column=1, row=0, ipadx=5, padx=5)

    # def _device_scan(self):
    #     logger.info("Scanning for devices")
    #     hrm_future = asyncio.run_coroutine_threadsafe(self._scan_for_hrm(), self._loop)
    #     hrm_future.add_done_callback(self._list_discovered_hrms)
    #     trainer_future = asyncio.run_coroutine_threadsafe(self._scan_for_trainers(), self._loop)
    #     trainer_future.add_done_callback(self._list_discovered_trainers)
    #     self.after(10000, self._device_scan)

    async def _device_scan(self):
        def callback(device, advertising_data):
            if HR_SERVICE_UUID in advertising_data.service_uuids:
                self._add_hrm_device(device)
            if TACX_UART_BLE_UUID in advertising_data.service_uuids:
                self._add_trainer_device(device)

        async with BleakScanner(callback):
            await self._scan_stop_event.wait()

    async def _scan_for_hrm(self):
        logger.info("Scanning for HRMs")
        hrms = await BleakScanner.discover(service_uuids=[HR_SERVICE_UUID])
        logger.info("Finished scanning for HRMs")
        return hrms

    async def _scan_for_trainers(self):
        logger.info("Scanning for trainers")
        trainers = await BleakScanner.discover(
            service_uuids=[TACX_UART_BLE_UUID], timeout=10
        )
        logger.info("Finished scanning for trainers")
        return trainers

    def _add_hrm_device(self, device: BLEDevice):
        if device.address not in self._hrm_devices:
            table_id = self._hr_table.insert(
                "", "end", device.address, text=device.name
            )
            self._hrm_devices[device.address] = (table_id, device.name)

    def _add_trainer_device(self, device: BLEDevice):
        if device.address not in self._trainer_devices:
            table_id = self._trainer_table.insert(
                "", "end", device.address, text=device.name
            )
            self._trainer_devices[device.address] = (table_id, device.name)

    def _list_discovered_hrms(self, future):
        hrms = future.result()
        for device in hrms:
            self._add_hrm_device(device)

    def _list_discovered_trainers(self, future):
        trainers = future.result()
        for device in trainers:
            self._add_trainer_device(device)

    def _ok_button_callback(self):
        self._scan_stop_event.set()
        hrm_device = self._hr_table.focus()
        hrm_client = BleakClient(hrm_device) if hrm_device else None

        trainer_device = self._trainer_table.focus()
        if trainer_device:
            trainer_client = BleakClient(trainer_device)
            tacx_client = TacxTrainerControl(trainer_client)
        else:
            tacx_client = None
        self._done_callback(hrm_client, tacx_client)
        self.destroy()

    def _cancel_button_callback(self):
        self._scan_stop_event.set()
        self.destroy()
