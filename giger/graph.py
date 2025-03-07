import random
from collections import deque
from _types import Measurement
from customtkinter import CTkSlider, CTkLabel, CTkFrame
from typing import Callable, Tuple
from tkinter import Frame, Canvas


class Graph:

    _x_axis_pad = 20
    _y_axis_pad = 20
    _point_width = 1
    _hr_color = "red"
    _hr_setpoint_color = "grey"
    _power_color = "blue"
    _axis_color = "black"
    _max_hr = 220
    _max_watts = 500
    _graph_size_ms = 60000

    def __init__(
        self,
        master: Frame,
        width: int,
        height: int,
        get_data_callback: Callable[[], Tuple[Measurement, Measurement, Measurement]],
        default_pack=True,
    ):
        self._master = master
        self.width = width
        self._width = width
        self.height = height
        self._height = height
        self._hr_scaling_factor = 0
        self._power_scaling_factor = 0
        self.get_data_callback = get_data_callback
        self.update_period_ms = 33

        self._master.grid_columnconfigure(0, weight=1)
        self._master.grid_rowconfigure(0, weight=1)
        self._canvas = Canvas(master=self._master, background="white")
        self._control_frame = CTkFrame(master=self._master)
        self._update_rate_slider = CTkSlider(
            master=self._control_frame, from_=1, to=60, number_of_steps=59
        )
        self._update_rate_slider.configure(command=self._update_rate_slider_callback)
        self._update_rate_label = CTkLabel(master=self._control_frame)
        self._update_rate_value_label = CTkLabel(master=self._control_frame)
        self._update_rate_value_label.configure(text="30 hz")
        self._update_rate_slider.set(30)
        self._update_rate_label.configure(text="Graph frame rate:")
        self._canvas.pack(fill="both", expand=True, side="top", pady=5)
        self._update_rate_label.pack(
            side="left",
            padx=10,
        )
        self._update_rate_slider.pack(side="left", padx=5, ipadx=5)
        self._update_rate_value_label.pack(side="left", padx=10)
        self._control_frame.pack(side="bottom", fill="x", expand=False, pady=5)

        self._hr_vals = deque(maxlen=width)  # Tuple of (timestamp, value)
        self._power_vals = deque(maxlen=width)
        self._hr_setpoint_vals = deque(maxlen=width)
        self.hr_setpoint: int = 0
        self._canvas.bind("<Configure>", self._onsize)

    def _onsize(self, event):
        if event.width:
            self._width = event.width
            self._hr_vals = deque(self._hr_vals, maxlen=event.width)
            self._power_vals = deque(self._power_vals, maxlen=event.width)
            self._hr_setpoint_vals = deque(self._hr_setpoint_vals, maxlen=event.width)
        if event.height:
            self._height = event.height
            available_pixels = self._height - self._y_axis_pad
            self._hr_scaling_factor = available_pixels / self._max_hr
            self._power_scaling_factor = available_pixels / self._max_watts

        self._y_axis_pad = self._x_axis_pad + self._control_frame.winfo_height() + 15

    def _update_rate_slider_callback(self, value):
        self.update_period_ms = int(1000 / value)
        self._update_rate_value_label.configure(text=f"{value: .0f} hz")

    def _draw_axes(self):
        origin_x = self._x_axis_pad
        origin_y = self._height - self._y_axis_pad
        self._canvas.create_line(origin_x, 0, origin_x, origin_y, self._width, origin_y, fill=self._axis_color)  # type: ignore # draw Y axis

    def pack(self, *args, **kwargs):
        self._canvas.pack(*args, **kwargs)

    def grid(self, *args, **kwargs):
        self._canvas.grid(*args, **kwargs)

    def add_hr_measurement(self, measurement: Tuple[float, int]):
        self._hr_vals.append(measurement)

    def add_power_measurement(self, measurement: Tuple[float, int]):
        self._power_vals.append(measurement)

    def _calculate_y_value(self, measurement, scaling_factor):
        pixel_magnitude = int(measurement * scaling_factor)
        return self._height - self._y_axis_pad - pixel_magnitude

    def _calculate_hr_y_value(self, measurement):
        return self._calculate_y_value(measurement, self._hr_scaling_factor)

    def _calculate_power_y_value(self, measurement):
        return self._calculate_y_value(measurement, self._power_scaling_factor)

    def _calculate_x_value(self, timestamp):
        available_pixels = self._width - self._x_axis_pad
        scaling_factor = available_pixels / self._graph_size_ms
        pixel_magnitude = int(timestamp * 1000 * scaling_factor)
        return self._x_axis_pad + pixel_magnitude

    def _get_time_offset(self, my_vals, their_vals):
        if not their_vals:
            return 0
        my_earliest_ts = my_vals[0].timestamp
        their_earliest_ts = their_vals[0].timestamp
        delta_t = my_earliest_ts - their_earliest_ts
        if delta_t > 0:
            return delta_t
        else:
            return 0

    def _draw_plot(self, data_source, calculate_y_func, color):
        if not data_source:
            return
        first_time, first_measurement = data_source[0]
        # coords = [self._calculate_x_value(0), calculate_y_func(first_measurement)]
        coords = [self._x_axis_pad, calculate_y_func(first_measurement)]
        for idx, (timestamp, measurement) in enumerate(data_source):
            # xval = self._calculate_x_value(timestamp - first_time)
            xval = idx + self._x_axis_pad
            yval = calculate_y_func(measurement)
            coords += [xval, yval]
        self._canvas.create_line(*coords, fill=color)

    def _draw_hr_plot(self):
        if not self._hr_vals:
            return
        self._draw_plot(self._hr_vals, self._calculate_hr_y_value, self._hr_color)

    def _draw_power_plot(self):
        if not self._power_vals:
            return
        self._draw_plot(
            self._power_vals, self._calculate_power_y_value, self._power_color
        )

    def _draw_hr_setpoint(self):
        if not self._hr_setpoint_vals:
            return
        self._draw_plot(
            self._hr_setpoint_vals, self._calculate_hr_y_value, self._hr_setpoint_color
        )

    def update(self):
        hr_measurement, power_measurement, hr_setpoint = self.get_data_callback()
        self._hr_vals.append(hr_measurement)
        self._power_vals.append(power_measurement)
        self._hr_setpoint_vals.append(hr_setpoint)
        self._width = self._master.winfo_width()
        self._height = self._master.winfo_height()
        self._canvas.delete("all")
        self._draw_hr_plot()
        self._draw_power_plot()
        self._draw_hr_setpoint()
        self._draw_axes()

    # def _draw_hr_plot(self):
    #     if not len(self._hr_vals):
    #         return
    #     time_offset = self._get_time_offset()
    #     first_time, first_measurement = self._hr_vals[0]
    #     start_time = time_offset
    #     coords = [self._calculate_x_value(start_time), self._calculate_hr_y_value(first_measurement)]
    #     for timestamp, measurement in self._hr_vals:
    #         xval = self._calculate_x_value(timestamp - first_time + time_offset)
    #         yval = self._calculate_hr_y_value(measurement)
    #         coords += [xval, yval]
    #     self._canvas.create_line(*coords, fill=self._hr_color)
