#!/usr/bin/env python

import os
import time
import errno
import logging
from threading import RLock, Event, Thread

PIPE = '/home/comitup/meter'
POLLING_INTERVAL = 0.033

class Meter():

    def __init__(self, callback, smooth=False):
        self.pipe = os.open(PIPE, os.O_RDONLY | os.O_NONBLOCK)
        self.lock = RLock()
        self.callback = callback
        self.cancel_event = Event()
        self.smooth = smooth
        self.latest_data = [0, 0, 0, 0]

    def __flush_pipe(self):
        try:
            os.read(self.pipe, 1048576)
        except Exception as e:
            logging.warning(e)

    def __get_pipe_value(self):
        """ Read from the named pipe until it's empty """
        data = None
        while True:
            try:
                data = os.read(self.pipe, 4)
                if len(data) != 0:
                    self.latest_data = [data[0], data[1], data[2], data[3]]
            except:
                break
    
    def startMeter(self):
        self.meterThread = Thread(target=self.__run, daemon = True)
        self.meterThread.start()
        return self.meterThread
    
    def stopMeter(self):
        self.cancel_event.set()

    def __run(self):
        with self.lock:
            self.__flush_pipe()
        while True:
            previous_data = self.latest_data[:]
            with self.lock:
                self.__get_pipe_value()

            # The 45 in the end should actually be set to the alsa master level to scale the volume level to 100% when the master max volume is reached
            length = 4
            if self.smooth:
                left = int(100 * ((((previous_data[length - 4] + (previous_data[length - 3] << 8)) + (self.latest_data[length - 4] + (self.latest_data[length - 3] << 8))) / 2) / 45))
                right = int(100 * ((((previous_data[length - 2] + (previous_data[length - 1] << 8)) + (self.latest_data[length - 2] + (self.latest_data[length - 1] << 8))) / 2) / 45))
            else:
                left = int(100 * ((self.latest_data[length - 4] + (self.latest_data[length - 3] << 8)) / 45))
                right = int(100 * ((self.latest_data[length - 2] + (self.latest_data[length - 1] << 8)) / 45))

            if self.cancel_event.wait(POLLING_INTERVAL):
                break

            self.callback(left, right)
