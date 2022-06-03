__version__ = "2.0.0"
__updateNote__ = """
08/06/2021: re-organize folder structure. 
All folders are under /
Adde M355 support.
05/24/2021: updated multiple data calling algorithms.
05/11/2021: updated to restart after firmware update
03/14/2021: 1.4.0 version removed httpServer, use auto measurement.
09/22: from 1.3.xx forwards, only works with v2 board.
09/22: last update of 1.2.xx version that works on v1 board.
09/14: encapsulated all pico functions to picoLibrary Pico class.
Added run test page.
dataStorageModule added password encryption for meta information.
Peripheral Module added button input and LED status indicator.
Peripheral Mode added AccessPoint Switch.
Updated dataStore module to save data periodically.
Read result from pico now timeouts. 
Optimized flush function, added 3 attempts to measurement task.
"""