#!/usr/bin/env python

import logging
from threading import Thread, Event
from smbus2 import SMBus, i2c_msg

CHECK_INTERVAL = 15 # Seconds
CRITICAL_VOLTAGE = 3.4 # Volts

class Power(Thread):
    
    def __init__(self, callback, debug=False):
        Thread.__init__(self, daemon=True)
        self.shutdown = Event()
        self.channelAVoltage = None
        self.channelCVoltage = None
        self.runningOnBackup = False
        self.criticalVoltage = False
        self.callback = callback
        self.debug = debug

    def run(self):
        while True:
            flag = self.shutdown.wait(CHECK_INTERVAL)
            if flag:
                return
        
            self.readChannelA()
            self.readChannelC()

            if self.channelAVoltage > self.channelCVoltage:
                if not self.runningOnBackup:
                    self.runningOnBackup = True
                    self.callback.runningOnBackup(True)
            else:
                if self.runningOnBackup:
                    self.runningOnBackup = False
                    self.callback.runningOnBackup(False)

            if max(self.channelAVoltage, self.channelCVoltage) <= CRITICAL_VOLTAGE:
                if not self.criticalVoltage:
                    self.criticalVoltage = True
                    self.callback.powerLevelCritical(True)
            else:
                if self.criticalVoltage:
                    self.criticalVoltage = False
                    self.callback.powerLevelCritical(False)

            logging.debug("Channel A Voltage: " + str(self.channelAVoltage))
            logging.debug("Channel C Voltage: " + str(self.channelCVoltage))
            logging.debug("Running on backup: " + str(self.runningOnBackup))
            logging.debug("Voltage critical: " + str(self.criticalVoltage))

    def readChannelA(self):
        with SMBus(1) as bus:
            i = bus.read_byte_data(0x29, 1)
            d = bus.read_byte_data(0x29, 2)
            self.channelAVoltage = (i * 100 + d) / 100
    
    def readChannelC(self):
        with SMBus(1) as bus:
            i = bus.read_byte_data(0x29, 5)
            d = bus.read_byte_data(0x29, 6)
            self.channelCVoltage = (i * 100 + d) / 100

    def cleanup(self):
        self.shutdown.set()