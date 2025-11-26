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

    def read_uart(self):
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
                    if group not in self.data:
                        self.data[group] = {}
                    if unit not in self.data[group]:
                        self.data[group][unit] = {}
                    if name not in self.data[group][unit]:
                        self.data[group][unit][name] = []
                    self.data[group][unit][name].append((now, value))

    def plot_data_thread(self, interval=0.1):
        plt.ion()  # Interaktiver Modus für dynamische Updates
        fig, axs = None, None

        while True:
            with self.lock:
                data_copy = self.data.copy()  # flache Kopie reicht für Key-Access

            if not data_copy:
                time.sleep(interval)
                continue

            # Subplots anlegen oder aktualisieren
            if fig is None:
                fig, axs = plt.subplots(len(data_copy), 1, figsize=(10, 6 * len(data_copy)))
                if len(data_copy) == 1:
                    axs = [axs]
            else:
                fig.clf()
                axs = []
                for i in range(len(data_copy)):
                    axs.append(fig.add_subplot(len(data_copy), 1, i + 1))

            for i, (group, units) in enumerate(data_copy.items()):
                ax = axs[i]
                ax.set_title(f"Group: {group}")
                ax.set_xlabel("Time [s]")
                ax.set_ylabel("Values")

                color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
                base_ax = ax

                for c, (unit, sensors) in enumerate(units.items()):
                    if c > 0:
                        ax2 = base_ax.twinx()
                        ax2.spines['right'].set_position(('outward', 60 * (c - 1)))
                    else:
                        ax2 = base_ax

                    ax2.set_ylabel(f"Unit: {unit}")
                    for sensor, values in sensors.items():
                        times, vals = zip(*values)
                        ax2.plot(times, vals, label=f"{sensor}", color=color_cycle[c % len(color_cycle)])

                base_ax.legend(loc='upper left')

            plt.tight_layout()
            plt.pause(0.1)
            time.sleep(interval)

    def run(self):
        reader_thread = threading.Thread(target=self.read_uart, daemon=True)
        reader_thread.start()
        self.plot_data_thread()
        # self.plot()


# Beispiel zur Verwendung:
plotter = UARTPlotter('COM5', 9600, 'uart_log.txt')
plotter.run()
