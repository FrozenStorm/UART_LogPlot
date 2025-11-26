import serial
import matplotlib.pyplot as plt
from collections import defaultdict
import time
import threading
import re

class UARTPlotter:
    def __init__(self, port, baudrate, logfile):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.logfile = logfile
        self.data = defaultdict(list)  # {signal_name: [(timestamp, value), ...]}
        self.units = {}  # {signal_name: unit}
        self.lock = threading.Lock()
        self.fig, self.axes = plt.subplots()
        self.unit_axes = {}  # {unit: axes}
        self.lines = {}  # {(signal_name): line_plot}

    def log(self, msg):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        with open(self.logfile, 'a') as f:
            f.write(f'{timestamp}: {msg}\n')

    def parse_line(self, s):
        pattern = r"(?P<name>[^\[]+)\[(?P<unit>[^\]]+)\]:\s*(?P<value>[0-9]+\.?[0-9]*)"
        match = re.match(pattern, s)
        if match:
            name = match.group('name')
            unit = match.group('unit')
            value = float(match.group('value'))
            return name, unit, value
        else:
            return None, None, None

    def read_uart(self):
        while True:
            line = self.ser.readline().decode('utf-8').strip()
            if line:
                self.log(line)
                name, unit, values = self.parse_line(line)
                if name is None:
                    continue
                with self.lock:
                    if name not in self.units:
                        self.units[name] = unit
                    now = time.time()
                    self.data[name].append((now, values))

    def update_plot(self):
        while True:
            with self.lock:
                unique_units = set(self.units.values())
                if not unique_units:
                    plt.pause(0.1)
                    continue

                # Achsen entsprechend der Einheiten erzeugen oder aktualisieren
                if len(self.unit_axes) != len(unique_units):
                    self.fig.clf()
                    if len(unique_units) == 1:
                        self.unit_axes = {unit: self.fig.add_subplot(111) for unit in unique_units}
                    else:
                        self.unit_axes = {}
                        unit_list = list(unique_units)
                        ax_left = self.fig.add_subplot(111)
                        self.unit_axes[unit_list[0]] = ax_left
                        for i, unit in enumerate(unit_list[1:], start=1):
                            self.unit_axes[unit] = ax_left.twinx() if i == 1 else self.fig.add_subplot(111, frame_on=False)
                        self.fig.subplots_adjust(right=0.75)

                # Achsen leeren und Signale plotten
                for ax in self.unit_axes.values():
                    ax.clear()

                for name, unit in self.units.items():
                    if self.data[name]:
                        times, vals = zip(*self.data[name])
                        ax = self.unit_axes[unit]
                        if name not in self.lines:
                            line, = ax.plot(times, vals, label=name)
                            self.lines[name] = line
                        else:
                            self.lines[name].set_data(times, vals)
                        ax.set_ylabel(unit)
                        ax.legend(loc='upper left')
                        ax.relim()
                        ax.autoscale_view()

            plt.pause(0.5)

    def run(self):
        reader_thread = threading.Thread(target=self.read_uart, daemon=True)
        reader_thread.start()
        self.update_plot()

# Beispiel zur Verwendung:
plotter = UARTPlotter('COM5', 9600, 'uart_log.txt')
plotter.run()
