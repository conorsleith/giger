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
        

app = customtkinter.CTk()
app.geometry("1600x1080")
app.title("CustomTkinter simple_example.py")

top_frame = CTkFrame(master=app)
top_frame.pack(pady=10, padx=10, fill="both", expand=True, side="top")

bottom_frame = CTkFrame(master=app)
bottom_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

right_frame = CTkFrame(master=top_frame)
right_frame.pack(pady=10, padx=10, fill="both", expand=True, side="right")
graph_frame = CTkFrame(master=right_frame)
graph_frame.pack(fill="both", expand=True)

cycling_frame = CTkFrame(master=top_frame)
cycling_frame.pack(pady=10, padx=10, fill="both", expand=False, side="left")

kweights_frame = CTkFrame(master=top_frame)
kweights_frame.pack(pady=10, padx=10, fill="both", expand=False, side="left")

kweights_frame_label = CTkLabel(master=kweights_frame, text="K weights", justify='left')
kweights_frame_label.pack(pady=10, padx=10)

kp_frame = CTkFrame(master=kweights_frame)
kp_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

ki_frame = CTkFrame(master=kweights_frame)
ki_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

kd_frame = CTkFrame(master=kweights_frame)
kd_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")


cycling_frame_label = CTkLabel(master=cycling_frame, text="Cycling Metrics", justify='left')
cycling_frame_label.pack(pady=10, padx=10)

cycling_metrics_frame = CTkFrame(master=cycling_frame)
cycling_metrics_frame.pack(pady=10, padx=10, fill="both", expand=True, side="top")

control_frame = CTkFrame(master=cycling_frame)
control_frame.pack(pady=10, padx=10, fill="both", expand=False, side="top")

log_box = CTkTextbox(master=bottom_frame, width=1920, height=760, font=("Monaco", 12))
log_box.pack(pady=10, padx=20, side="top")
log_box_handler = TextBoxLogger(log_box)
logger.add(log_box_handler, # type: ignore
           format=('<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
                   '<level>{level: <8}</level> | '
                   '<level>{message}</level>')) 

# Create 3 pairs of sliders and labels
kp_sliders = SliderPair(master=kp_frame, logscale=True)
kp_sliders.pack(pady=5, padx=20)
ki_sliders = SliderPair(master=ki_frame, logscale=True)
ki_sliders.pack(pady=5, padx=20)
kd_sliders = SliderPair(master=kd_frame, logscale=True)
kd_sliders.pack(pady=5, padx=20)

kp, ki, kd = KPID
kp_sliders.set(kp, do_callback=True)
ki_sliders.set(ki, do_callback=True)
kd_sliders.set(kd, do_callback=True)

#METRICS_WIDGETS    

# Cycling metrics widgets
hr_setpoint_label = CTkLabel(master=cycling_metrics_frame, text="Heart Rate Setpoint")
hr_setpoint_slider = CTkSlider(master=cycling_metrics_frame, from_=60, to=200)
hr_setpoint_value_label = CTkLabel(master=cycling_metrics_frame, text=f"{STARTING_HR_SETPOINT_VALUE}")
hr_setpoint_slider.set(STARTING_HR_SETPOINT_VALUE)

min_watts_label = CTkLabel(master=cycling_metrics_frame, text="Min Watts")
min_watts_slider = CTkSlider(master=cycling_metrics_frame, from_=0, to=600)
min_watts_value_label = CTkLabel(master=cycling_metrics_frame, text=f"{STARTING_MIN_WATTS_VALUE}")
min_watts_slider.set(STARTING_MIN_WATTS_VALUE)

max_watts_label = CTkLabel(master=cycling_metrics_frame, text="Max Watts")
max_watts_slider = CTkSlider(master=cycling_metrics_frame, from_=0, to=600)
max_watts_value_label = CTkLabel(master=cycling_metrics_frame, text=f"{STARTING_MAX_WATTS_VALUE}")
max_watts_slider.set(STARTING_MAX_WATTS_VALUE)

set_current_watts_label = CTkLabel(master=cycling_metrics_frame, text="Set Current Watts")
set_current_watts_slider = CTkSlider(master=cycling_metrics_frame, from_=0, to=600)
set_current_watts_value_label = CTkLabel(master=cycling_metrics_frame, text=f"{STARTING_MIN_WATTS_VALUE}")
set_current_watts_slider.set(STARTING_MIN_WATTS_VALUE)
set_current_watts_slider.configure(command=lambda val: set_current_watts_value_label.configure(text=f"{val:.0f}"))

current_hr_label = CTkLabel(master=cycling_metrics_frame, text="Current Heart Rate")
current_hr_value_label = CTkLabel(master=cycling_metrics_frame, text="0")

current_watts_label = CTkLabel(master=cycling_metrics_frame, text="Current Watts")
current_watts_value_label = CTkLabel(master=cycling_metrics_frame, text="0")

def grid_metrics_slider_group(row, label: CTkLabel, slider, value):
    label.grid(row=row, column=0, sticky="w", padx=5, pady=5, ipadx=5)
    slider.grid(row=row, column=1, sticky="ew", padx=5, pady=5, ipadx=5)
    value.grid(row=row, column=2, sticky="e", padx=5, pady=5, ipadx=5)
    
def grid_metrics_label_group(row, label, value):
    label.grid(row=row, column=0, sticky="w", padx=5, pady=5, ipadx=5)
    value.grid(row=row, column=2, sticky="e", padx=5, pady=5, ipadx=5)

grid_metrics_slider_group(0, hr_setpoint_label, hr_setpoint_slider, hr_setpoint_value_label)
grid_metrics_slider_group(1, min_watts_label, min_watts_slider, min_watts_value_label)
grid_metrics_slider_group(2, max_watts_label, max_watts_slider, max_watts_value_label)
grid_metrics_slider_group(3, set_current_watts_label, set_current_watts_slider, set_current_watts_value_label)
grid_metrics_label_group(4, current_hr_label, current_hr_value_label)
grid_metrics_label_group(5, current_watts_label, current_watts_value_label)

# Create control widgets
on_off_switch = CTkSwitch(master=control_frame, text="PID on/off")
on_off_switch.pack(pady=5, padx=10, side='top')

reset_button = CTkButton(master=control_frame, text="Reset PID")
reset_button.pack(pady=5, padx=10, side='top')


# Tuple of elements which can be disabled/enabled
stateful_ui_elements = (
    kp_sliders._int_slider,
    kp_sliders._float_slider,
    ki_sliders._int_slider,
    ki_sliders._float_slider,
    ki_sliders._int_slider,
    ki_sliders._float_slider,
    kd_sliders._int_slider,
    kd_sliders._float_slider,
    hr_setpoint_slider,
    min_watts_slider,
    max_watts_slider,
    set_current_watts_slider,
    on_off_switch,
    reset_button,
)

# Callbacks for giger controller instantiation
def current_watts_callback(watts):
    current_watts_value_label.configure(text=f"{watts:.0f}")
    set_current_watts_value_label.configure(text=f"{watts:.0f}")
    set_current_watts_slider.set(watts)
    graph.add_power_measurement(Measurement(time(), watts))
    # update draw
    
def current_hr_callback(hr):
    current_hr_value_label.configure(text=f"{hr:.0f}")
    graph.add_hr_measurement(Measurement(time(), hr))
    # update draw
    
def get_measurements() -> Tuple[Measurement, Measurement, Measurement]:
    global giger
    ts = time()
    return Measurement(ts, giger.current_hr), Measurement(ts, giger.current_power), Measurement(ts, giger.hr_setpoint)
    
# Instantiate giger controller
giger = controller.Giger(None, None, max_power=STARTING_MAX_WATTS_VALUE, min_power=STARTING_MIN_WATTS_VALUE,
                         hr_setpoint=STARTING_HR_SETPOINT_VALUE,
                        update_hr_callback=current_hr_callback,
                        update_power_callback=current_watts_callback)
    
graph = Graph(graph_frame, 600, 300, get_measurements)

# Callbacks which use giger methods
def on_off_switch_command():
    global loop, giger
    if on_off_switch.get():
        giger.start()
    else:
        asyncio.run_coroutine_threadsafe(giger.stop(), loop)
        
def reset_button_command():
    global giger
    giger.pid.reset()

def hr_setpoint_callback(hr):
    global giger
    hr_setpoint_value_label.configure(text=f"{hr:.0f}")
    giger.hr_setpoint = hr
    giger.pid.setpoint = hr
    graph.hr_setpoint = hr
    
def min_watts_callback(watts):
    global giger
    giger.set_min_power(watts)
    min_watts_value_label.configure(text=f"{watts:.0f}")
    
def max_watts_callback(watts):
    global giger
    giger.set_max_power(watts)
    max_watts_value_label.configure(text=f"{watts:.0f}")
    
def set_current_watts_callback(event):
    global loop, giger
    if on_off_switch.get():
        on_off_switch.toggle()
    watts = set_current_watts_slider.get()
    future = asyncio.run_coroutine_threadsafe(giger.set_current_power(watts), loop)
    future.add_done_callback(lambda *args, **kwargs: current_watts_callback(watts))
    
def enable_interface(future):
    for element in stateful_ui_elements:
        element.configure(state='normal')
    
# Add callbacks
on_off_switch.configure(command=lambda: on_off_switch_command())
hr_setpoint_slider.configure(command=lambda value: hr_setpoint_callback(value))
min_watts_slider.configure(command=lambda value: min_watts_callback(value))
max_watts_slider.configure(command=lambda value: max_watts_callback(value))
set_current_watts_slider.bind("<ButtonRelease-1>", set_current_watts_callback)
reset_button.configure(command=reset_button_command)
kp_sliders.callback = giger.set_kp
ki_sliders.callback = giger.set_ki
kd_sliders.callback = giger.set_kd

def update_graph():
    graph.update()
    app.after(33, update_graph)
    
# We run the controller in a separate thread
async def run_controller():
    async def set_up_hr():
        hr_client = await devices.set_up_hr()
        await giger.set_hr_client(hr_client)
        
    async def set_up_trainer():
        trainer_control = await devices.set_up_trainer()
        await giger.set_trainer_control(trainer_control)
    
    future = asyncio.gather(
        set_up_hr(),
        set_up_trainer()
    )
    future.add_done_callback(enable_interface)

    while True:
            await asyncio.sleep(1)
        
        
if __name__ == "__main__":
    import sys
    def main():
        # UI Elements start disabled    
        for element in stateful_ui_elements:
            element.configure(state='disabled')
        
        loop = asyncio.new_event_loop()
        thread = Thread(target=loop.run_until_complete, args=(run_controller(),))
        thread.start()
        app.focus_force()
        update_graph()
        app.mainloop()
        loop.stop()
        thread.join()
    main()
    # import cProfile
    # cProfile.run('main()')
