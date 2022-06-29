#!/usr/bin/env python

from button import *
import signal
import RPi.GPIO as GPIO
import json
import sys
import logging
import traceback
import os
import time
from buttons import ButtonManager, PUSH_BUTTON_BLINK_COUNT, PUSH_BUTTON_BLINK_DURATION
from cardreader import Cardreader
from connection import Connection
from database import Database
from encoder import Encoder
from player import Player
from led import Led
from power import Power
from shutdown import ShutdownController
from threading import Thread, Event, Timer, Lock

PROGRAMMING_MODE_TIMEOUT = 2 # In Minutes

class Box():

    def __init__(self):
        GPIO.setmode(GPIO.BOARD)
        self.networkMode = "UNKNOWN"
        self.networkModeLock = Lock()
        self.programmingMode = False
        self.programmingModeThread = None
        self.programmingModeCancelEvent = Event()
        self.programmingUid = None
        self.__setupLed()
        self.__setupButtons()
        self.__setupPlayer()
        self.__setupDatabase()
        self.__setupCardReader()
        self.__setupVolumeControl()
        self.__setupPowerControl()
        self.__setupShutdownManager()
        self.__setupConnectionManager()
    
    def start(self):
        self.led.startWaitAninmation()
        self.player.start()
        self.reader.start()
        self.power.start()
        self.shutdownManager.start()

    def cardDetected(self, uid):
        logging.info("Detected card with UID " + str(uid) + ". Trying to retrieve playlist url.")
        playlist = self.database.readPlaylist(uid)
        if playlist is not None:
            logging.info("UID matches playlist " + playlist)
            self.player.play(playlist)
        else:
            logging.info("Engaging programming mode")
            self.startProgrammingMode(uid)

    def encoderChanged(self, value, direction):
        logging.info("Detected volume change event. Current value: " + str(value) + " and direction: " + direction)
        if direction == "R":
            self.player.increaseVolume()
        if direction == "L":
            self.player.decreaseVolume()

    def prevButtonPressed(self):
        self.player.prev()

    def nextButtonPressed(self):
        self.player.next()

    def runningOnBackup(self, backup):
        if backup:
            logging.info("Now running on backup power!")
        else:
            logging.info("Now running on main power!")

    def powerLevelCritical(self, critical):
        if critical:
            logging.info("Power level critical!")
        else:
            logging.info("Power level back to normal!")
        self.led.engageLowPowerMode(backup)

    def startProgrammingMode(self, uid):
        if not self.programmingUid == uid:
            logging.info("Starting programming mode for uid " + uid)
            if self.programmingModeThread is not None and self.programmingModeThread.is_alive():
                self.programmingModeCancelEvent.set()
                self.programmingModeThread.join()
                self.programmingModeCancelEvent.clear()
            self.programmingMode = True
            self.programmingUid = uid
            self.led.engageProgrammingMode()
            self.programmingModeThread = Thread(target=self.programmingModeTimeout, daemon=True)
            self.programmingModeThread.start()

    def programmingModeTimeout(self):
        logging.info("Programming mode will be cancelled in " + str(PROGRAMMING_MODE_TIMEOUT * 60) + " seconds")
        flag = self.programmingModeCancelEvent.wait(PROGRAMMING_MODE_TIMEOUT * 60)
        logging.info("Waking up to cancel programming mode: " + str(not flag))
        if not flag:
            self.stopProgrammingMode(False)

    def stopProgrammingMode(self, success=True):
        self.programmingMode = False
        self.programmingUid = None
        if success:
            self.led.programmingSucessful()
        else:
            self.led.programmingFailed()

    def __setupLed(self):
        logging.info("Init main LED and start waiting animation until player connection is established...")
        self.led = Led()

    def __setupPlayer(self):
        logging.info("Trying to connect to librespot-java...")
        self.player = Player(self.playerMessageReceived, self.playerConnected)
    
    def __setupDatabase(self):
        logging.info("Loading playlist database")
        self.database = Database()
    
    def __setupCardReader(self):
        logging.info("Setting up card reader")
        # pi-rc522 sets board mode GPIO. Thats why it used everywhere else as well.
        self.reader = Cardreader(self.cardDetected)

    def __setupVolumeControl(self):
        logging.info("Setting up volume control")
        self.encoder = Encoder(13, 16, self.encoderChanged)
    
    def __setupButtons(self):
        self.buttonManager = ButtonManager(self)

    def __setupPowerControl(self):
        self.power = Power(self)
    
    def __setupShutdownManager(self):
        self.shutdownManager = ShutdownController()

    def connectionStateChanged(self, state):
        logging.debug("Network state " + state + " received. Current state: " + self.networkMode)
        with self.networkModeLock:
            if state == "HOTSPOT" and state != self.networkMode:
                logging.debug("Network entered HOTSPOT mode")
                # Add a bit of delay here since during boot the modes
                # change pretty rapidly which leads to some flickering
                self.buttonManager.blinkBoth(sys.maxsize, 1, 1)
            elif state == "CONNECTING" and state != self.networkMode:
                logging.debug("Network entered CONNECTING mode")
                # Add a bit of delay here since during boot the modes
                # change pretty rapidly which leads to some flickering
                self.buttonManager.blinkAlternating(sys.maxsize, 0.5, 1)
            elif state == "UNKNOWN" and state != self.networkMode:
                logging.debug("Network entered UNKNOWN mode")
                self.buttonManager.clearBoth()
            elif state == "CONNECTED" and state != self.networkMode:
                logging.debug("Network entered CONNECTED mode")
                self.buttonManager.clearBoth()
            self.networkMode = state
    
    def __setupConnectionManager(self):
        self.connectionManager = Connection(self.connectionStateChanged)
    
    def playerConnected(self, connected):
        if connected:
            logging.info("Player connection established")
            self.led.stopWaitAninmation()
            self.buttonManager.blinkBoth(PUSH_BUTTON_BLINK_COUNT, PUSH_BUTTON_BLINK_DURATION)
        else:
            self.led.startWaitAninmation()

    def playerMessageReceived(self, message):
        messageDict = json.loads(message)
        eventType = messageDict["event"]
        if eventType == "volumeChanged":
            self.led.signalVolumeChange(round(messageDict["value"] * 100))
        if eventType == "contextChanged":
            if self.programmingMode:
                if self.programmingModeThread is not None and self.programmingModeThread.is_alive():
                    self.programmingModeCancelEvent.set()
                    self.programmingModeThread.join()
                    self.programmingModeCancelEvent.clear()
                try:
                    self.database.setPlaylist(self.programmingUid, messageDict["uri"])
                    self.stopProgrammingMode()
                except Exception as e:
                    logging.warning(e)
                    self.stopProgrammingMode(False)
        logging.info(message)

    def shutdown(self):
        logging.info("Shutdown sequence started...")
        self.programmingModeCancelEvent.set()
        self.connectionManager.cleanup()
        self.buttonManager.cleanup()
        self.led.cancel()
        self.led.clear()
        self.shutdownManager.cleanup()
        self.power.cleanup()
        self.player.cleanup()
        self.reader.cleanup()

def shutdown(signum, frame):
    logging.debug("Received signal " + str(signum))
    box.shutdown()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    GPIO.setwarnings(False)
    box = Box()
    box.start()
    logging.info("Setting signal handlers for shutdown")
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.pause()