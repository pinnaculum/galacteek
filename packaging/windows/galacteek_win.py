import sys
import faulthandler
import ctypes


def hideConsoleWindow():
    whnd = ctypes.windll.kernel32.GetConsoleWindow()

    if whnd != 0:
        ctypes.windll.user32.ShowWindow(whnd, 0)


print("Starting galacteek ..")

hideConsoleWindow()
faulthandler.enable(sys.stderr)

from galacteek.guientrypoint import start
start()
