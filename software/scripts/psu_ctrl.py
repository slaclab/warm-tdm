#!/usr/bin/env python3
import socket
import sys
import time
import fcntl
import os
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "psu_ctrl.log")
LOCK_FILE = os.path.join(SCRIPT_DIR, ".psu_ctrl.lock")

PSU1 = "192.168.99.10"
PSU2 = "192.168.99.11"


def send_scpi(ip, cmd, port=5025, timeout=2):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((ip, port))
        s.sendall((cmd + "\n").encode())
        if "?" in cmd:
            return s.recv(4096).decode().strip()


def read_channels(ip):
    readings = []
    for ch in (1, 2, 3):
        v = float(send_scpi(ip, f"MEAS:VOLT? (@{ch})"))
        i = float(send_scpi(ip, f"MEAS:CURR? (@{ch})"))
        readings.append((ch, v, i))
    return readings


def report(ip, name):
    readings = read_channels(ip)
    for ch, v, i in readings:
        print(f"  {name} ch{ch}: {v:.4f} V, {i:.4f} A")
    return readings


def log_entry(action, readings=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"[{timestamp}] action={action}"]
    if readings:
        for name, channel_readings in readings:
            for ch, v, i in channel_readings:
                lines.append(f"  {name} ch{ch}: {v:.4f} V, {i:.4f} A")
    with open(LOG_FILE, "a") as f:
        f.write("\n".join(lines) + "\n")


def acquire_lock():
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_fd.close()
        return None
    lock_fd.write(str(os.getpid()))
    lock_fd.flush()
    return lock_fd


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("on", "off", "read"):
        print("Usage: psu_ctrl.py [on|off|read]")
        sys.exit(1)

    action = sys.argv[1]

    lock_fd = acquire_lock()
    if lock_fd is None:
        msg = "Another instance of psu_ctrl.py is already running. Exiting."
        print(msg)
        log_entry(f"BLOCKED ({action})")
        sys.exit(1)

    try:
        print(send_scpi(PSU1, "*IDN?"))
        print(send_scpi(PSU2, "*IDN?"))

        if action == "on":
            print("Turning on PSU1 (all outputs)...")
            send_scpi(PSU1, "OUTP ON,(@1,2,3)")
            print("Waiting 15 s...")
            time.sleep(15)
            r1 = report(PSU1, "PSU1")

            print("Turning on PSU2 (all outputs)...")
            send_scpi(PSU2, "OUTP ON,(@1,2,3)")
            print("Waiting 10 s...")
            time.sleep(10)
            r2 = report(PSU2, "PSU2")

            log_entry(action, [("PSU1", r1), ("PSU2", r2)])

        elif action == "off":
            print("Turning off PSU2 (all outputs)...")
            send_scpi(PSU2, "OUTP OFF,(@1,2,3)")
            print("Turning off PSU1 (all outputs)...")
            send_scpi(PSU1, "OUTP OFF,(@1,2,3)")
            log_entry(action)

        elif action == "read":
            r1 = report(PSU1, "PSU1")
            r2 = report(PSU2, "PSU2")
            log_entry(action, [("PSU1", r1), ("PSU2", r2)])

        print("Done.")
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
