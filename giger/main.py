import asyncio
import math
import random
from threading import Thread
from time import time
from typing import Tuple

from _types import Measurement
import controller
import customtkinter
import devices
from graph import Graph
from customtkinter import CTkSlider, CTkLabel, CTkFrame, CTkSwitch, CTkButton, CTkTextbox, CTkTabview
from loguru import logger
from settings import settings
from tkinter import Canvas, Frame

customtkinter.set_appearance_mode("system")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

STARTING_HR_SETPOINT_VALUE = 140
STARTING_MIN_WATTS_VALUE = 180
STARTING_MAX_WATTS_VALUE = 300

KPID = (.5, .01, 0.05)

class SliderPair:
    def __init__(self, master, logscale=False, callback=None):
        self._int_slider = CTkSlider(master=master, from_=0, to=100, number_of_steps=100)
        self._float_slider = CTkSlider(master=master, from_=0, to=100, number_of_steps=100)
        self._sum_label = CTkLabel(master=master, text="Value: 0.0")
        self.logscale = logscale
        self.callback = callback or (lambda *args, **kwargs: None)
        self._int_slider.configure(command=self._internal_callback)
        self._float_slider.configure(command=self._internal_callback)
        self._int_slider.bind("<ButtonRelease-1>", self._external_callback_wraper)
        self._float_slider.bind("<ButtonRelease-1>", self._external_callback_wraper)
        
    def pack(self, *args, **kwargs):
        self._int_slider.pack(*args, **kwargs)
        self._float_slider.pack(*args, **kwargs)
        self._sum_label.pack(*args, **kwargs)

    def _internal_callback(self, _):
        val = self._int_value + self._float_value
        self._sum_label.configure(text=f"Value: {val:.02f}")

    def _external_callback_wraper(self, *args, **kwargs):
        self.callback(self._int_value + self._float_value)

    @property
    def _int_value(self):
        value = self._int_slider.get()
        if self.logscale:
            value = int((value/10)**2)
        return value
    
    @_int_value.setter
    def _int_value(self, value):
        if self.logscale:
            value = math.sqrt(value) * 10
        self._int_slider.set(value)
        
    @property
    def _float_value(self):
        value = self._float_slider.get()
        if self.logscale:
            value = value**2 / 10000.0
        return value
    
    @_float_value.setter
    def _float_value(self, value):
        if self.logscale:
            value = math.sqrt(value) * 100
        self._float_slider.set(value)
        
    def get(self):
        return self._int_value + self._float_value
    
    def set(self, value, do_callback=False):
        f, i = math.modf(value)
        self._int_value = i
        self._float_value = f
        if do_callback:
            self._internal_callback(None)
            
class TextBoxLogger:
    def __init__(self, textbox):
        self._textbox = textbox
        
    def write(self, writeable):
        self._textbox.configure(state="normal")
        self._textbox.insert("end", writeable)
        self._textbox.configure(state="disabled")
        self._textbox._textbox.see("end")
        
class HRTrainer(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self._geometry = (820, 800)
        self._graph_geometry = (780, 300)
        width, height = self._geometry
        self.geometry(f"{width}x{height}")
        self.title("CustomTkinter simple_example.py")
        self._topmost = False
        # Instantiate giger controller
        self._giger = controller.Giger(None, None, max_power=STARTING_MAX_WATTS_VALUE, min_power=STARTING_MIN_WATTS_VALUE,
                                hr_setpoint=STARTING_HR_SETPOINT_VALUE,
                                update_hr_callback=self._current_hr_callback,
                                update_power_callback=self._current_watts_callback)
        self._loop = asyncio.new_event_loop()
        self._setup_ui()
        for element in self._stateful_ui_elements:
            element.configure(state='disabled')
            
   
    # Callbacks for giger controller instantiation
    def _current_watts_callback(self, watts):
        self._current_watts_value_label.configure(text=f"{watts:.0f}")
        # self._set_current_watts_value_label.configure(text=f"{watts:.0f}")
        # self._set_current_watts_slider.set(watts)
        # self._graph.add_power_measurement(Measurement(time(), watts))
        # update draw
        
    def _current_hr_callback(self, hr):
        self._current_hr_value_label.configure(text=f"{hr:.0f}")
        # self._graph.add_hr_measurement(Measurement(time(), hr))
        # update draw
        
    def _get_measurements(self) -> Tuple[Measurement, Measurement, Measurement]:
        global giger
        ts = time()
        return Measurement(ts, self._giger.current_hr), Measurement(ts, self._giger.current_trainer_power), Measurement(ts, self._giger.hr_setpoint)
    
    def _grid_metrics_slider_group(self, row, label: CTkLabel, slider, value):
        label.grid(row=row, column=0, sticky="w", padx=5, pady=5, ipadx=5)
        slider.grid(row=row, column=1, sticky="ew", padx=5, pady=5, ipadx=5)
        value.grid(row=row, column=2, sticky="e", padx=5, pady=5, ipadx=5)
        
    def _grid_metrics_label_group(self, row, label, value):
        label.grid(row=row, column=0, sticky="w", padx=5, pady=5, ipadx=5)
        value.grid(row=row, column=2, sticky="e", padx=5, pady=5, ipadx=5)

    # Callbacks which use giger methods
    def _on_off_switch_command(self):
        global loop, giger
        if self._on_off_switch.get():
            if not self._giger.start():
                self._on_off_switch.deselect()
        else:
            # asyncio.run_coroutine_threadsafe(self._giger.stop(), self._loop)
            self._giger.stop()
            
    def _reset_button_command(self):
        self._giger.pid.reset()

    def _hr_setpoint_callback(self, hr):
        self._hr_setpoint_value_label.configure(text=f"{hr:.0f}")
        self._giger.hr_setpoint = hr
        self._giger.pid.setpoint = hr
        self._graph.hr_setpoint = hr
        
    def _min_watts_callback(self, watts):
        self._giger.set_min_power(watts)
        self._min_watts_value_label.configure(text=f"{watts:.0f}")
        
    def _max_watts_callback(self, watts):
        self._giger.set_max_power(watts)
        self._max_watts_value_label.configure(text=f"{watts:.0f}")
        
    ### TODO call _current_watts_callback w/ actual watts from _giger
    ### TODO maybe throw an error if above doesn't mattch slider watts
    def _set_current_watts_callback(self, event):
        if self._on_off_switch.get():
            self._on_off_switch.toggle()
        watts = self._set_current_watts_slider.get()
        future = asyncio.run_coroutine_threadsafe(self._giger.set_current_power(watts), self._loop)
        # future.add_done_callback(lambda *args, **kwargs: self._current_watts_callback(watts))
        
    def _enable_interface(self):
        # future.result()
        for element in self._stateful_ui_elements:
            element.configure(state='normal')
            
    def _open_device_picker(self):
        from device_picker import DevicePicker
        if self._device_picker_window is None or not self._device_picker_window.winfo_exists():
            self._device_picker_window = DevicePicker(loop=self._loop, done_callback=self._change_devices)
            self._device_picker_window.attributes("-topmost", True)
        else:
            self._device_picker_window.focus()
        self._device_picker_window.lift(aboveThis=self)
        
    def _change_devices(self, hrm_device, trainer_device):
        future = asyncio.run_coroutine_threadsafe(
            self._async_change_devices(hrm_device, trainer_device),
            self._loop
        )
    
    async def _async_change_devices(self, hrm_device, trainer_device):
        future = asyncio.gather(
            self._change_hrm_device(hrm_device),
            self._change_trainer_device(trainer_device)
        )
        future.add_done_callback(lambda *args, **kwargs: self._giger.start())
        
    async def _change_hrm_device(self, hrm_device):
        if hrm_device is not None:
            await self._giger.set_hr_client(hrm_device)
        
    async def _change_trainer_device(self, trainer_device):
        if trainer_device is not None:
            await self._giger.set_trainer_control(trainer_device)
        
    def _topmost_switch_callback(self):
        if self._topmost_switch.get():
            self._topmost = True
        else:
            self._topmost = False
        self.attributes('-topmost', self._topmost)
        
    def _increment_power(self, delta):
        watts = self._set_current_watts_slider.get() + delta
        self._set_current_watts_slider.set(watts)
        self._set_current_watts_value_label.configure(text=f"{watts}")
        self._set_current_watts_callback(None)
        
    def _watts_up_callback(self):
        self._increment_power(10)
        
    def _watts_down_callback(self):
        self._increment_power(-10)
        
    def _show_graph_switch_callback(self):
        width, height = self._geometry
        if self._show_graph_switch.get():
            self._graph_frame.pack(fill="both", expand=True)
            self.geometry(f"{width+self._graph.width}x{height}")
        else:
            self._graph_frame.pack_forget()
            self.geometry(f"{width}x{height}")
            
        
    def _setup_ui(self):
        # self.bind("<Configure>", lambda x: print(x))
        self._top_frame = CTkFrame(master=self)
        self._top_frame.pack(pady=10, padx=10, fill="both", expand=True, side="top")

        self._bottom_frame = CTkFrame(master=self)
        self._bottom_frame.pack(pady=10, padx=10, expand=True, side="bottom", fill="both")

        self._cycling_frame = CTkFrame(master=self._top_frame)
        self._cycling_frame.pack(pady=10, padx=10, fill="both", expand=False, side="left")

        self._weights_favorites_tab = CTkTabview(master=self._top_frame)
        self._weights_favorites_tab.pack(pady=10, padx=10, fill="both", expand=False, side="left")

        self._right_frame = CTkFrame(master=self._top_frame)
        self._right_frame.pack(pady=10, padx=10, fill="both", expand=True, side="left")
        self._graph_frame = CTkFrame(master=self._right_frame)
        self._graph_frame.pack(fill="both", expand=True)
        width, height = self._graph_geometry
        self._graph = Graph(self._graph_frame, width, height, self._get_measurements)

        self._hr_favorites_frame = self._weights_favorites_tab.add("HR Favs")
        self._hr_favorites_frame.grid_columnconfigure(1, weight=1)
        self._watt_favorites_frame = self._weights_favorites_tab.add("Pwr Favs")
        self._kweights_frame = self._weights_favorites_tab.add("K-Weights")
        self._weights_favorites_tab.set("HR Favs")

        self._kweights_frame_label = CTkLabel(master=self._kweights_frame, text="K weights", justify='left')
        self._kweights_frame_label.pack(pady=10, padx=10)

        self._kp_frame = CTkFrame(master=self._kweights_frame)
        self._kp_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._ki_frame = CTkFrame(master=self._kweights_frame)
        self._ki_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._kd_frame = CTkFrame(master=self._kweights_frame)
        self._kd_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")
        
        for idx, watts in enumerate(reversed(range(150, 450, 25))):
            def callback_factory(_watts):
                def callback():
                    self._set_current_watts_slider.set(_watts)
                    self._set_current_watts_value_label.configure(text=f"{_watts}")
                    self._set_current_watts_callback(None)
                return callback
            column = idx % 2
            button = CTkButton(master=self._watt_favorites_frame, text=f"{watts}", command=callback_factory(watts))
            button.grid(row=idx//2, column=column, padx=5, pady=10)
        
        updown_row = (idx + 1) // 2
        self._watts_down_button = CTkButton(master=self._watt_favorites_frame, text="-10", command=self._watts_down_callback)
        self._watts_down_button.grid(row=updown_row, column=0, padx=5, pady=10)
        self._watts_up_button = CTkButton(master=self._watt_favorites_frame, text="+10", command=self._watts_up_callback)
        self._watts_up_button.grid(row=updown_row, column=1, padx=5, pady=10)
        
        for idx, hr in enumerate(reversed([130, 140, 150, 160, 170, 180])):
            def callback_factory(_hr):
                def callback():
                    self._hr_setpoint_slider.set(_hr)
                    self._hr_setpoint_value_label.configure(text=f"{_hr}")
                    self._hr_setpoint_callback(_hr)
                return callback
            button = CTkButton(master=self._hr_favorites_frame, text=f"{hr}", command=callback_factory(hr))
            button.grid(row=idx, column=1, padx=5, pady=10)
        
        self._device_picker_window = None
        self._cycling_metrics_frame = CTkFrame(master=self._cycling_frame)
        self._cycling_metrics_frame.pack(pady=10, padx=10, fill="both", expand=True, side="top")

        self._control_frame = CTkFrame(master=self._cycling_frame)
        self._control_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._log_box = CTkTextbox(master=self._bottom_frame, font=("Monaco", 12))
        self._log_box.pack(pady=10, padx=20, side="top", expand=True, fill="both")
        self._log_box_handler = TextBoxLogger(self._log_box)
        logger.add(self._log_box_handler, # type: ignore
                format=('<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
                        '<level>{level: <8}</level> | '
                        '<level>{message}</level>')) 

        # Create 3 pairs of sliders and labels
        self._kp_sliders = SliderPair(master=self._kp_frame, logscale=True)
        self._kp_sliders.pack(pady=5, padx=20)
        self._ki_sliders = SliderPair(master=self._ki_frame, logscale=True)
        self._ki_sliders.pack(pady=5, padx=20)
        self._kd_sliders = SliderPair(master=self._kd_frame, logscale=True)
        self._kd_sliders.pack(pady=5, padx=20)

        kp, ki, kd = KPID
        self._kp_sliders.set(kp, do_callback=True)
        self._ki_sliders.set(ki, do_callback=True)
        self._kd_sliders.set(kd, do_callback=True)

        #METRICS_WIDGETS    

        # Cycling metrics widgets
        self._hr_setpoint_label = CTkLabel(master=self._cycling_metrics_frame, text="Heart Rate Setpoint")
        self._hr_setpoint_slider = CTkSlider(master=self._cycling_metrics_frame, from_=60, to=200)
        self._hr_setpoint_value_label = CTkLabel(master=self._cycling_metrics_frame, text=f"{STARTING_HR_SETPOINT_VALUE}")
        self._hr_setpoint_slider.set(STARTING_HR_SETPOINT_VALUE)
        self._hr_setpoint_slider.configure(command=lambda val: self._hr_setpoint_value_label.configure(text=f"{val:.0f}"))

        self._min_watts_label = CTkLabel(master=self._cycling_metrics_frame, text="Min Watts")
        self._min_watts_slider = CTkSlider(master=self._cycling_metrics_frame, from_=0, to=600)
        self._min_watts_value_label = CTkLabel(master=self._cycling_metrics_frame, text=f"{STARTING_MIN_WATTS_VALUE}")
        self._min_watts_slider.set(STARTING_MIN_WATTS_VALUE)
        self._min_watts_slider.configure(command=lambda val: self._min_watts_value_label.configure(text=f"{val:.0f}"))

        self._max_watts_label = CTkLabel(master=self._cycling_metrics_frame, text="Max Watts")
        self._max_watts_slider = CTkSlider(master=self._cycling_metrics_frame, from_=0, to=600)
        self._max_watts_value_label = CTkLabel(master=self._cycling_metrics_frame, text=f"{STARTING_MAX_WATTS_VALUE}")
        self._max_watts_slider.set(STARTING_MAX_WATTS_VALUE)
        self._max_watts_slider.configure(command=lambda val: self._max_watts_value_label.configure(text=f"{val:.0f}"))

        self._set_current_watts_label = CTkLabel(master=self._cycling_metrics_frame, text="Set Current Watts")
        self._set_current_watts_slider = CTkSlider(master=self._cycling_metrics_frame, from_=0, to=600)
        self._set_current_watts_value_label = CTkLabel(master=self._cycling_metrics_frame, text=f"{STARTING_MIN_WATTS_VALUE}")
        self._set_current_watts_slider.set(STARTING_MIN_WATTS_VALUE)
        self._set_current_watts_slider.configure(command=lambda val: self._set_current_watts_value_label.configure(text=f"{val:.0f}"))

        self._current_hr_label = CTkLabel(master=self._cycling_metrics_frame, text="Current Heart Rate")
        self._current_hr_value_label = CTkLabel(master=self._cycling_metrics_frame, text="0")

        self._current_watts_label = CTkLabel(master=self._cycling_metrics_frame, text="Current Watts")
        self._current_watts_value_label = CTkLabel(master=self._cycling_metrics_frame, text="0")

        self._grid_metrics_slider_group(0, self._hr_setpoint_label, self._hr_setpoint_slider, self._hr_setpoint_value_label)
        self._grid_metrics_slider_group(1, self._min_watts_label, self._min_watts_slider, self._min_watts_value_label)
        self._grid_metrics_slider_group(2, self._max_watts_label, self._max_watts_slider, self._max_watts_value_label)
        self._grid_metrics_slider_group(3, self._set_current_watts_label, self._set_current_watts_slider, self._set_current_watts_value_label)
        self._grid_metrics_label_group(4, self._current_hr_label, self._current_hr_value_label)
        self._grid_metrics_label_group(5, self._current_watts_label, self._current_watts_value_label)
        
        self._device_picker_button = CTkButton(master=self._cycling_metrics_frame, text="Devices")
        self._device_picker_button.configure(command=self._open_device_picker)
        self._device_picker_button.grid(row=6, column=0)

        # Create control widgets
        self._on_off_switch = CTkSwitch(master=self._control_frame, text="PID on/off")
        self._on_off_switch.grid(row=0, column=0, pady=5, padx=10)#, side='top')

        self._topmost_switch = CTkSwitch(master=self._control_frame, text="Stay on top")
        self._topmost_switch.grid(row=0, column=1, pady=5, padx=10)
        if self._topmost:
            self._topmost_switch.select()
            
        self._show_graph_switch = CTkSwitch(master=self._control_frame, text="Show graph")
        self._show_graph_switch.grid(row=0, column=2, pady=5, padx=10)
        self._show_graph_switch.select()

        reset_button = CTkButton(master=self._control_frame, text="Reset PID")
        reset_button.grid(row=1, column=0,pady=5, padx=10)#, side='top')

        # Tuple of elements which can be disabled/enabled
        self._stateful_ui_elements = (
            self._kp_sliders._int_slider,
            self._kp_sliders._float_slider,
            self._ki_sliders._int_slider,
            self._ki_sliders._float_slider,
            self._ki_sliders._int_slider,
            self._ki_sliders._float_slider,
            self._kd_sliders._int_slider,
            self._kd_sliders._float_slider,
            self._hr_setpoint_slider,
            self._min_watts_slider,
            self._max_watts_slider,
            self._set_current_watts_slider,
            self._on_off_switch,
            reset_button,
        )
        
        # Add callbacks
        self._on_off_switch.configure(command=lambda: self._on_off_switch_command())
        self._topmost_switch.configure(command=self._topmost_switch_callback)
        self._show_graph_switch.configure(command=self._show_graph_switch_callback)
        self._hr_setpoint_slider.configure(command=lambda value: self._hr_setpoint_callback(value))
        self._min_watts_slider.configure(command=lambda value: self._min_watts_callback(value))
        self._max_watts_slider.configure(command=lambda value: self._max_watts_callback(value))
        self._set_current_watts_slider.bind("<ButtonRelease-1>", self._set_current_watts_callback)
        reset_button.configure(command=self._reset_button_command)
        self._kp_sliders.callback = self._giger.set_kp
        self._ki_sliders.callback = self._giger.set_ki
        self._kd_sliders.callback = self._giger.set_kd

    def _update_graph(self):
        self._graph.update()
        self.after(self._graph.update_period_ms, self._update_graph)
        
    # We run the controller in a separate thread
    async def _run_controller(self):
        ### TODO load hr and trainer UUIDs from file written at exit
        async def set_up_hr(hrm_uuid):
            if hrm_uuid is not None:
                hr_client = await devices.set_up_hr(hrm_uuid)
                await self._giger.set_hr_client(hr_client)
            
        async def set_up_trainer(trainer_uuid):
            if trainer_uuid is not None:
                trainer_control = await devices.set_up_trainer(trainer_uuid)
                await self._giger.set_trainer_control(trainer_control)

        # logger.warning("UNCOMMENT THE STUFF BELOW")
        hrm_uuid = settings.last_used_hrm_uuid
        trainer_uuid = settings.last_used_trainer_uuid
        future = asyncio.gather(
            set_up_hr(hrm_uuid),
            set_up_trainer(trainer_uuid)
        )

        while self._giger.trainer_control is None or self._giger.hr_client is None:
            await asyncio.sleep(1)
            
        self._enable_interface()

        while True:
                await asyncio.sleep(1)
    
    def run(self):
        thread = Thread(target=self._loop.run_until_complete, args=(self._run_controller(),))
        thread.start()
        self.focus_force()
        self.attributes('-topmost', self._topmost)
        self._update_graph()
        self.after_idle(self._show_graph_switch_callback)
        self.mainloop()
        self._loop.stop()
        thread.join()
            
if __name__ == "__main__":
    app = HRTrainer()
    app.run()