import re
import csv
import time
from datetime import datetime

import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

SERIAL_PORT = "COM5"       # z.B. "/dev/ttyUSB0"
BAUDRATE = 9600
LOGFILE = f"uart_log_{datetime.now().strftime('%Y%m%d')}.csv"

LINE_RE = re.compile(r"^\s*(?P<name>[A-Za-z0-9_]+)\[(?P<unit>[^\]]+)\]\s*:\s*(?P<value>[-+0-9.]+)\s*$")
MAX_POINTS = 500

# Linienstile (können nach Wunsch erweitert werden)
LINE_STYLES = ['-', '--', '-.', ':']

def parse_line(line: str):
    m = LINE_RE.match(line)
    if not m:
        return None
    try:
        value = float(m.group("value"))
    except ValueError:
        return None
    return m.group("name"), m.group("unit"), value


def main():
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    time.sleep(2.0)
    ser.reset_input_buffer()

    logfile = open(LOGFILE, "w", newline="", encoding="utf-8")
    csv_writer = csv.writer(logfile)
    csv_writer.writerow(["timestamp_iso", "signal_name", "unit", "value"])

    # Datenspeicher: Signalname -> Zeiten, Werte, Einheit, Plot-Linie
    data = {}

    # Dictionary Einheit -> Achse
    unit_axes = {}

    plt.style.use("ggplot")
    fig, ax_primary = plt.subplots()
    ax_primary.set_xlabel("Zeit (s)")
    ax_primary.grid(True)
    ax_primary.set_title("UART Signale mit je einer Achse pro Einheit")

    ax_primary.set_ylabel("(Primärachse)")
    unit_axes_list = []  # für Achsenfarbenzuordnung und Offset

    def get_axis_for_unit(unit):
        # Wie bisher + jetzt auch Linienstil zuweisen
        if unit in unit_axes:
            return unit_axes[unit]

        if not unit_axes:
            ax_primary.set_ylabel(f"{unit} [{LINE_STYLES[0]}]")
            unit_axes[unit] = {"axis": ax_primary, "linestyle": LINE_STYLES[0]}
            unit_axes_list.append(ax_primary)
            return unit_axes[unit]
        else:
            ax_new = ax_primary.twinx()
            offset = 0.1 * (len(unit_axes) - 1)
            ax_new.spines["right"].set_position(("axes", 1 + offset))
            ax_new.set_frame_on(True)
            ax_new.patch.set_visible(False)
            color = "black"
            ax_new.yaxis.label.set_color(color)
            ax_new.tick_params(axis='y', colors=color)
            linestyle = LINE_STYLES[len(unit_axes) % len(LINE_STYLES)]
            unit_axes[unit] = {"axis": ax_new, "linestyle": linestyle}
            ax_new.set_ylabel(f"{unit} [{linestyle}]")
            unit_axes_list.append(ax_new)
            return unit_axes[unit]

    def update_plot(frame):
        for _ in range(20):
            if ser.in_waiting == 0:
                break

            raw = ser.readline()
            try:
                text = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                continue

            if not text:
                continue

            parsed = parse_line(text)
            if not parsed:
                print("Ungültige Zeile:", text)
                continue

            name, unit, value = parsed
            now = datetime.now()
            iso_ts = now.isoformat(timespec="milliseconds")

            csv_writer.writerow([iso_ts, name, unit, value])
            logfile.flush()

            if name not in data:
                # Neues Signal anlegen
                data[name] = {"times": [], "values": [], "unit": unit, "line": None}

            times = data[name]["times"]
            values = data[name]["values"]

            t_rel = 0.0 if not times else now.timestamp() - times[0]
            times.append(now.timestamp())
            values.append(value)

            if len(times) > MAX_POINTS:
                times.pop(0)
                values.pop(0)

        if not data:
            return []

        # Linien pro Signal anlegen, falls noch nicht geschehen
        for name, entry in data.items():
            if entry["line"] is None:
                ax_info = get_axis_for_unit(entry["unit"])
                ax = ax_info["axis"]
                linestyle = ax_info["linestyle"]
                color_idx = len(ax.lines) % 10
                color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
                color = color_cycle[color_idx]
                entry["line"], = ax.plot([], [], label=name, color=color, linestyle=linestyle)

        # Achsen skalieren
        for ax_info in unit_axes.values():
            ax_info["axis"].relim()
            ax_info["axis"].autoscale_view()

        # Daten setzen
        for entry in data.values():
            ax = get_axis_for_unit(entry["unit"])["axis"]
            t0 = entry["times"][0] if entry["times"] else 0
            xdata = [t - t0 for t in entry["times"]]
            entry["line"].set_data(xdata, entry["values"])

        # Alle Linien sammeln für Legende
        all_lines = [entry["line"] for entry in data.values()]
        all_labels = [entry["line"].get_label() for entry in data.values()]
        ax_primary.legend(all_lines, all_labels, loc="upper left")

        return all_lines

    ani = FuncAnimation(fig, update_plot, interval=100, blit=True)

    print(f"Logging nach: {LOGFILE}")
    print("Fenster schließen oder Strg+C zum Beenden.")

    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        logfile.close()
        ser.close()


if __name__ == "__main__":
    main()
