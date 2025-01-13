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
from customtkinter import CTkSlider, CTkLabel, CTkFrame, CTkSwitch, CTkButton, CTkTextbox
from loguru import logger
from tkinter import Canvas, Frame

customtkinter.set_appearance_mode("system")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

STARTING_HR_SETPOINT_VALUE = 140
STARTING_MIN_WATTS_VALUE = 180
STARTING_MAX_WATTS_VALUE = 300

KPID = (.5, .01, 0.05)

class SliderPair:
    def __init__(self, master, logscale=False, callback=None):
        self._int_slider = CTkSlider(master=master, from_=0, to=100, number_of_steps=100, command=self._callback)
        self._float_slider = CTkSlider(master=master, from_=0, to=100, number_of_steps=100)
        self._sum_label = CTkLabel(master=master, text="Value: 0.0")
        self.logscale = logscale
        self.callback = callback or (lambda *args, **kwargs: None)
        self._int_slider.configure(command=self._callback)
        self._float_slider.configure(command=self._callback)
        
        
    def pack(self, *args, **kwargs):
        self._int_slider.pack(*args, **kwargs)
        self._float_slider.pack(*args, **kwargs)
        self._sum_label.pack(*args, **kwargs)
        
    def _callback(self, _):
        val = self._int_value + self._float_value
        self._sum_label.configure(text=f"Value: {val:.02f}")
        self.callback(val)
        
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
            self._callback(None)
            
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
        self.geometry("1600x1080")
        self.title("CustomTkinter simple_example.py")
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
        self._set_current_watts_value_label.configure(text=f"{watts:.0f}")
        self._set_current_watts_slider.set(watts)
        self._graph.add_power_measurement(Measurement(time(), watts))
        # update draw
        
    def _current_hr_callback(self, hr):
        self._current_hr_value_label.configure(text=f"{hr:.0f}")
        self._graph.add_hr_measurement(Measurement(time(), hr))
        # update draw
        
    def _get_measurements(self) -> Tuple[Measurement, Measurement, Measurement]:
        global giger
        ts = time()
        return Measurement(ts, self._giger.current_hr), Measurement(ts, self._giger.current_power), Measurement(ts, self._giger.hr_setpoint)
    
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
            self._giger.start()
        else:
            asyncio.run_coroutine_threadsafe(self._giger.stop(), self._loop)
            
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
        
    def _set_current_watts_callback(self, event):
        if self._on_off_switch.get():
            self._on_off_switch.toggle()
        watts = self._set_current_watts_slider.get()
        future = asyncio.run_coroutine_threadsafe(self._giger.set_current_power(watts), self._loop)
        future.add_done_callback(lambda *args, **kwargs: self._current_watts_callback(watts))
        
    def _enable_interface(self, future):
        for element in self._stateful_ui_elements:
            element.configure(state='normal')
            
    def _setup_ui(self):
        self._top_frame = CTkFrame(master=self)
        self._top_frame.pack(pady=10, padx=10, fill="both", expand=True, side="top")

        self._bottom_frame = CTkFrame(master=self)
        self._bottom_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._right_frame = CTkFrame(master=self._top_frame)
        self._right_frame.pack(pady=10, padx=10, fill="both", expand=True, side="right")
        self._graph_frame = CTkFrame(master=self._right_frame)
        self._graph_frame.pack(fill="both", expand=True)
        self._graph = Graph(self._graph_frame, 600, 300, self._get_measurements)

        self._cycling_frame = CTkFrame(master=self._top_frame)
        self._cycling_frame.pack(pady=10, padx=10, fill="both", expand=False, side="left")

        self._kweights_frame = CTkFrame(master=self._top_frame)
        self._kweights_frame.pack(pady=10, padx=10, fill="both", expand=False, side="left")

        self._kweights_frame_label = CTkLabel(master=self._kweights_frame, text="K weights", justify='left')
        self._kweights_frame_label.pack(pady=10, padx=10)

        self._kp_frame = CTkFrame(master=self._kweights_frame)
        self._kp_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._ki_frame = CTkFrame(master=self._kweights_frame)
        self._ki_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._kd_frame = CTkFrame(master=self._kweights_frame)
        self._kd_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")


        self._cycling_frame_label = CTkLabel(master=self._cycling_frame, text="Cycling Metrics", justify='left')
        self._cycling_frame_label.pack(pady=10, padx=10)

        self._cycling_metrics_frame = CTkFrame(master=self._cycling_frame)
        self._cycling_metrics_frame.pack(pady=10, padx=10, fill="both", expand=True, side="top")

        self._control_frame = CTkFrame(master=self._cycling_frame)
        self._control_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

        self._log_box = CTkTextbox(master=self._bottom_frame, width=1920, height=760, font=("Monaco", 12))
        self._log_box.pack(pady=10, padx=20, side="top")
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

        self._min_watts_label = CTkLabel(master=self._cycling_metrics_frame, text="Min Watts")
        self._min_watts_slider = CTkSlider(master=self._cycling_metrics_frame, from_=0, to=600)
        self._min_watts_value_label = CTkLabel(master=self._cycling_metrics_frame, text=f"{STARTING_MIN_WATTS_VALUE}")
        self._min_watts_slider.set(STARTING_MIN_WATTS_VALUE)

        self._max_watts_label = CTkLabel(master=self._cycling_metrics_frame, text="Max Watts")
        self._max_watts_slider = CTkSlider(master=self._cycling_metrics_frame, from_=0, to=600)
        self._max_watts_value_label = CTkLabel(master=self._cycling_metrics_frame, text=f"{STARTING_MAX_WATTS_VALUE}")
        self._max_watts_slider.set(STARTING_MAX_WATTS_VALUE)

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

        # Create control widgets
        self._on_off_switch = CTkSwitch(master=self._control_frame, text="PID on/off")
        self._on_off_switch.pack(pady=5, padx=10, side='top')

        reset_button = CTkButton(master=self._control_frame, text="Reset PID")
        reset_button.pack(pady=5, padx=10, side='top')

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
        async def set_up_hr():
            hr_client = await devices.set_up_hr()
            await self._giger.set_hr_client(hr_client)
            
        async def set_up_trainer():
            trainer_control = await devices.set_up_trainer()
            await self._giger.set_trainer_control(trainer_control)
        
        future = asyncio.gather(
            set_up_hr(),
            set_up_trainer()
        )
        future.add_done_callback(self._enable_interface)

        while True:
                await asyncio.sleep(1)
    
    def run(self):
        thread = Thread(target=self._loop.run_until_complete, args=(self._run_controller(),))
        thread.start()
        self.focus_force()
        self._update_graph()
        self.mainloop()
        self._loop.stop()
        thread.join()
            
if __name__ == "__main__":
    app = HRTrainer()
    app.run()