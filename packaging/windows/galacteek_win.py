import sys
import faulthandler
import ctypes


def hideConsoleWindow():
    whnd = ctypes.windll.kernel32.GetConsoleWindow()

    if whnd != 0:
        ctypes.windll.user32.ShowWindow(whnd, 0)


print("Starting galacteek ..")

faulthandler.enable(sys.stderr)

if '-d' not in sys.argv:
    hideConsoleWindow()

from galacteek_starter.entrypoint import start
start()
