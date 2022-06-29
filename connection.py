#!/usr/bin/env python

import logging
import time
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, EVENT_TYPE_MODIFIED, EVENT_TYPE_CREATED

CONNECTION_STATE_PATH = "/home/comitup/comitup-connection-state"

def readConnectionState():
    try:
        with open(CONNECTION_STATE_PATH, "r") as f:
            state = f.read().rstrip()
            if state in ["CONNECTED", "HOTSPOT", "CONNECTING"]:
                return state
    except Exception as e:
        logging.warning("Could not read connection state: " + str(e))
    return "UNKNOWN"

class Connection():

    def __init__(self, callback):
        logging.info("Watching file system for connection events")
        self.event_handler = ConnectionEventHandler(callback)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, CONNECTION_STATE_PATH)
        self.observer.start()
        # Provide initial value for callback
        state = readConnectionState()
        callback(state)

    def cleanup(self):
        self.observer.stop()

class ConnectionEventHandler(FileSystemEventHandler):

    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        logging.debug("Caught event: " + event.event_type + " for path: " + event.src_path)
        if event.src_path == CONNECTION_STATE_PATH and event.event_type in [EVENT_TYPE_MODIFIED, EVENT_TYPE_CREATED]:
            state = readConnectionState()
            self.callback(state)

def test(state):
    logging.info("New state: " + state)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    conn = Connection(test)
    
    time.sleep(60)

    conn.cleanup()
