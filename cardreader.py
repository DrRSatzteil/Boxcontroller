#!/usr/bin/env python

import logging
import signal
import sys
from threading import Thread

from pirc522 import RFID


class Cardreader(Thread):

    def __init__(self, callback):
        logging.info("Initializing card reader. Use start() to begin reading for cards.")
        Thread.__init__(self, daemon=True)
        self.rdr = RFID()
        self.util = self.rdr.util()
        self.util.debug = True
        self.callback = callback

    def run(self):
        logging.info("Waiting for cards. Use cleanup() to stop waiting.")
        self.run = True
        while self.run:
            self.rdr.wait_for_tag()
            if self.run == False:
                logging.info("Stopping waiting for cards.")
                return
            logging.info("Detected a card. Trying to acquire uid and call callback")
            (error, data) = self.rdr.request()
            if not error:
                (error, uid) = self.rdr.anticoll()
                if not error:
                    self.callback(str(uid[0])+str(uid[1]) +
                                  str(uid[2])+str(uid[3]))

    def cleanup(self):
        logging.info("Received cleanup command.")
        if self.is_alive():
            logging.info("Trying to interrupt cardreader...")
            self.run = False
            self.rdr.irq.set()
        logging.info("Cleaning up cardreader.")
        self.rdr.cleanup()
