#!/usr/bin/env python

import logging
import os
import subprocess
import time
from threading import Thread, Event, Lock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, EVENT_TYPE_MODIFIED, EVENT_TYPE_CREATED

SHUTDOWN_WAIT_TIME = 420 # In seconds
TIME_SYNC_CHECK_INTERVAL = 3 # In seconds

AUDIO_OUTPUT_STATE_PATH = "/home/comitup/audio-output-state"

def readAudioOutputState():
    try:
        with open(AUDIO_OUTPUT_STATE_PATH, "r") as f:
            state = f.read().rstrip()
            if state in ["RUNNING", "SILENT"]:
                return state
    except Exception as e:
        logging.warning("Could not read connection state: " + str(e))
    return "UNKNOWN"

class ShutdownController(Thread):
    
    def __init__(self):
        Thread.__init__(self, daemon=True)
        self.timeSynchronized = False
        self.timeSyncCancelEvent = Event()
        self.shutdownTimerCancelEvent = Event()
        self.shutdownTimerThread = None
        self.shutdownTimerLock = Lock()

        self.event_handler = AudioOutputEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, AUDIO_OUTPUT_STATE_PATH)

    def run(self):
        while True:
            logging.info("Checking for time synchronization...")
            output = subprocess.check_output("timedatectl show -p NTPSynchronized --value", shell=True)
            if str(output) == "b\'yes\\n\'":
                logging.info("System time is synchronized now")
                self.timeSynchronized = True
                state = readAudioOutputState()
                if state != "RUNNING":
                    self.scheduleShutdown()
                self.observer.start()
                return
            if self.timeSyncCancelEvent.wait(TIME_SYNC_CHECK_INTERVAL):
                return

    def scheduleShutdown(self):
        if self.timeSynchronized:
            self.cancelScheduledShutdown()
            logging.info("Scheduling shutdown")
            with self.shutdownTimerLock:
                self.shutdownTimerThread = Thread(target=self.__waitForShutdown, args=([SHUTDOWN_WAIT_TIME]), daemon=True)
                self.shutdownTimerThread.start()
        else:
            logging.warning("Time is not synchronized. No timer has been scheduled")

    def cancelScheduledShutdown(self):
        with self.shutdownTimerLock:
            if self.shutdownTimerThread is not None and self.shutdownTimerThread.is_alive():
                self.shutdownTimerCancelEvent.set()
                self.shutdownTimerThread.join()
                self.shutdownTimerCancelEvent.clear()

    def __waitForShutdown(self, seconds):
        logging.info("Shutdown will be initiated in " + str(seconds) + " seconds")
        flag = self.shutdownTimerCancelEvent.wait(seconds)
        if not flag:
            logging.info("Shutdown timer passed by. Shutting down system")
            os.system("shutdown now")
        else:
            logging.info("Shutdown timer cancelled")

    def cleanup(self):
        self.observer.stop()
        self.timeSyncCancelEvent.set()
        self.cancelScheduledShutdown()

class AudioOutputEventHandler(FileSystemEventHandler):

    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        logging.debug("Caught event: " + event.event_type + " for path: " + event.src_path)
        if event.src_path == AUDIO_OUTPUT_STATE_PATH and event.event_type in [EVENT_TYPE_MODIFIED, EVENT_TYPE_CREATED]:
            state = readAudioOutputState()
            if state == "RUNNING":
                self.callback.cancelScheduledShutdown()
            else:
                self.callback.scheduleShutdown()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    controller = ShutdownController()
    
    controller.start()

    time.sleep(60)

    controller.cleanup()

