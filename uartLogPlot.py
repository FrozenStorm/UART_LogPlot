import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import serial
import math

# === User prompt ===
print("Welcome to UART Data Logger and Plotter")
print("\nExpected Format: <group>/<signal>[unit]: <value>")
print("Example: Temperature/SHT41 Temperature[°C]: 22.36")
print("\nConfiguration:")
port = input("Serieller Port (z.B. COM3 oder /dev/ttyUSB0) [COM5]: ").strip() or "COM5"
baud = int(input("Baudrate (z.B. 115200) [9600]: ").strip() or "9600")
logfile = input("Logfile Name (z.B. logfile.txt) [uart.log]: ").strip() or "uart.log"
window_sec = float(input("Anzahl Sekunden im Plotfenster [60]: ").strip() or "60")


# === Data structures ===
# {group: {unit: {signal_name: deque[(timestamp, value)]}}}
data_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: deque())))
start_time = time.time()
legend_positions = ['upper left', 'upper right', 'lower left', 'lower right', 'upper center', 'lower center']


def parse_line(line):
    """
    Parsere die Zeile nach dem Format: <group>/<signal>[<unit>]: <value>
    """
    match = re.match(r"([^/]+)/([^\[]+)\[([^\]]+)\]:\s*(-?\d+(\.\d+)?(?:[eE][-+]?\d+)?)", line.strip())
    if not match:
        return None  # Zeile passt nicht
    group, signal, unit, value = match.group(1), match.group(2).strip(), match.group(3), float(match.group(4))
    return group, signal, unit, value


def uart_reader():
    """
    Liest kontinuierlich Daten von der seriellen Schnittstelle und schreibt sie ins Logfile
    """
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"Fehler beim Öffnen des Ports {port}: {e}")
        return

    with open(logfile, 'a', encoding='utf-8') as log:
        print(f"Starte Datenerfassung auf {port} @ {baud} baud")
        while True:
            try:
                rawline = ser.readline()
                if not rawline:
                    continue
                try:
                    line = rawline.decode("utf-8").strip()
                except UnicodeDecodeError:
                    continue  # Ignorieren ungültiger UTF-8-Zeilen

                if not line:
                    continue

                ts = time.time() - start_time
                parsed = parse_line(line)
                if parsed:
                    group, signal, unit, value = parsed
                    dq = data_dict[group][unit][signal]
                    dq.append((ts, value))
                    # Logging mit Zeitstempel
                    log.write(f"{datetime.now().isoformat()}: {line}\n")
                    log.flush()
            except Exception as e:
                print(f"Fehler beim Lesen: {e}")
                continue


def dynamic_plot():
    """
    Plottet die Daten dynamisch mit separaten Y-Achsen pro Unit
    """
    plt.ion()
    fig = plt.figure(figsize=(14, 6))
    fig.canvas.manager.set_window_title("UART Data Logger and Plotter")
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']

    while True:
        groups = sorted(data_dict.keys())
        n_groups = len(groups)
        fig.clf()

        for idx, group in enumerate(groups, start=1):
            # Erstelle primäre Achse
            ax_primary = plt.subplot(math.ceil(n_groups/2), 2 if n_groups > 1 else 1 , idx)
            units = sorted(data_dict[group].keys())

            # Speichere alle Achsen pro Unit
            axes_dict = {units[0]: ax_primary}  # Erste Unit auf primärer Achse

            # Erstelle zusätzliche Achsen für weitere Units
            for unit_idx, unit in enumerate(units[1:], start=1):
                # Neue Y-Achse auf der rechten Seite
                ax_new = ax_primary.twinx()
                # Verschiebe die Achse nach rechts (bei mehreren Achsen)
                if unit_idx == 1:
                    offset = 0
                else:
                    offset = 60 * (unit_idx-1)
                ax_new.spines['right'].set_position(('outward', offset))
                axes_dict[unit] = ax_new

            color_idx = 0
            # Sammle alle Y-Werte pro Unit für Min/Max Berechnung
            unit_values = {unit: [] for unit in units}

            for unit_idx, unit in enumerate(units):
                ax = axes_dict[unit]
                for signal, dq in data_dict[group][unit].items():
                    # Werte für Plotfenster filtern
                    xs, ys = zip(*[(t, v) for t, v in dq if t > time.time() - start_time - window_sec]) if dq else (
                        [], [])
                    if xs:
                        ax.plot(xs, ys, label=f"{signal}", color=color_cycle[color_idx % len(color_cycle)])
                        unit_values[unit].extend(ys)
                        color_idx += 1

                # Berechne Y-Limits für diese Unit
                if unit_values[unit]:
                    y_min = min(unit_values[unit])
                    y_max = max(unit_values[unit])
                    y_range = y_max - y_min if y_max != y_min else 1
                    y_min -= 0.1 * y_range
                    y_max += 0.1 * y_range
                    ax.set_ylim([y_min, y_max])

                ax.set_ylabel(unit, rotation=270, labelpad=10)
                pos = legend_positions[unit_idx % len(legend_positions)]
                ax.legend(loc=pos, fontsize=9)

            # X-Achse und Titel nur auf primärer Achse
            ax_primary.set_xlabel("Zeit [s]")
            ax_primary.set_title(group)
            ax_primary.set_xlim([max(0, time.time() - start_time - window_sec), time.time() - start_time])

        plt.tight_layout()
        plt.pause(0.1)

        # Entferne alte Werte aus dem Fenster
        tmin = time.time() - start_time - window_sec
        for group in data_dict:
            for unit in data_dict[group]:
                for signal in data_dict[group][unit]:
                    dq = data_dict[group][unit][signal]
                    while dq and dq[0][0] < tmin:
                        dq.popleft()


if __name__ == "__main__":
    # Starte den Serial-Reader-Thread
    t = threading.Thread(target=uart_reader, daemon=True)
    t.start()
    try:
        dynamic_plot()
    except KeyboardInterrupt:
        print("\nBeendet.")
