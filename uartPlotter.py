import re
import time
from datetime import datetime
import serial
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.animation import FuncAnimation
import threading


class UARTPlotter:
    LINE_RE = re.compile(
        r"^\s*"
        r"(?P<group>[A-Za-z0-9_ /\-]+)"  # Gruppe, erlaubt auch Leerzeichen und Bindestriche
        r"/"
        r"(?P<name>[A-Za-z0-9_ /\-]+)"  # Signalname, erlaubt auch Leerzeichen und Bindestriche
        r"\["
        r"(?P<unit>[^\]]+)"  # Einheit, alles außer schließende Klammer
        r"\]\s*:\s*"
        r"(?P<value>[-+0-9.eE]+)"  # Wert, erlaubt Zahlen mit Dezimalpunkten, Vorzeichen, expon.
        r"\s*$"
    )

    def __init__(self, port, baudrate, logfile):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.logfile = logfile
        self.lock = threading.Lock()
        self.data = {}
        plt.ion()  # Interaktiver Modus für dynamische Updates
        self.fig, self.axs = plt.subplots()
        self.ax = {}

    def parse_line(self, line: str):
        m = self.LINE_RE.match(line)
        if not m:
            return None, None, None, None
        try:
            value = float(m.group("value"))
        except ValueError:
            return None, None, None, None
        return m.group("group"), m.group("name"), m.group("unit"), value

    def log(self, msg):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        with open(self.logfile, 'a') as f:
            f.write(f'{timestamp}: {msg}\n')

    def read_log_plot_uart(self):
        while True:
            line = self.ser.readline().decode('utf-8').strip()
            if line:
                self.log(line)
                group, name, unit, value = self.parse_line(line)
                now = time.time()
                # print(f"group: {group}, name: {name}, unit: {unit}, value: {value}")
                if group is None:
                    continue
                with self.lock:
                    if group+unit not in self.data:
                        self.data[group+unit] = {}
                        self.ax[group+unit] = {}
                    if name not in self.data[group+unit]:
                        self.data[group+unit][name] = []
                    self.data[group+unit][name].append((now, value))



    def plot(self):
        while True:
            with self.lock:
                self.fig.clf()

                for i, axis in enumerate(self.ax):
                    self.ax[axis] = self.fig.add_subplot(len(self.ax) + 1, 1, i + 1)
                    self.ax[axis].set_title(f"Group: ")
                    self.ax[axis].set_xlabel("Time [s]")
                    self.ax[axis].set_ylabel(f"Unit: ")

                for axis in self.ax:
                    for dataName in self.data[axis]:
                        times, vals = zip(*self.data[axis][dataName])
                        self.ax[axis].plot(times, vals)

                plt.tight_layout()
                self.fig.canvas.draw()
                self.fig.canvas.flush_events()
                plt.pause(0.1)

    def run(self):
        reader_thread = threading.Thread(target=self.read_log_plot_uart, daemon=True)
        reader_thread.start()
        self.plot()


# Beispiel zur Verwendung:
plotter = UARTPlotter('COM5', 9600, 'uart_log.txt')
plotter.run()
