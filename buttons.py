#!/usr/bin/env python

from button import *
import RPi.GPIO as GPIO
import logging
import time
from threading import Event, Thread

PUSH_BUTTON_BLINK_COUNT = 5
PUSH_BUTTON_BLINK_DURATION = 0.2
PREV_BUTTON_PIN = 31 # GPIO Board Mode
NEXT_BUTTON_PIN = 37 # GPIO Board Mode

class ButtonManager():

    def __init__(self, callback):
        self.callback = callback
        self.prevButtonCancelEvent = Event()
        self.prevButtonThread = None
        self.nextButtonCancelEvent = Event()
        self.nextButtonThread = None

        logging.info("Setting up push buttons")
        GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(PREV_BUTTON_PIN, GPIO.OUT)
        GPIO.output(PREV_BUTTON_PIN, 0)
        self.prevButton = ButtonCallback(29, GPIO.RISING, self.prevButtonPressed)
        GPIO.setup(36, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(NEXT_BUTTON_PIN, GPIO.OUT)
        GPIO.output(NEXT_BUTTON_PIN, 0)
        self.nextButton = ButtonCallback(36, GPIO.RISING, self.nextButtonPressed)

    def prevButtonPressed(self, unused):
        self.blinkPrev(PUSH_BUTTON_BLINK_COUNT, PUSH_BUTTON_BLINK_DURATION)
        self.callback.prevButtonPressed()
    
    def nextButtonPressed(self, unused):
        self.blinkNext(PUSH_BUTTON_BLINK_COUNT, PUSH_BUTTON_BLINK_DURATION)
        self.callback.nextButtonPressed()

    def blinkPrev(self, times, duration, delay=0, autostart=True):
        self.clearPrev()
        self.prevButtonThread = Thread(target=self.__blinkPrevButton, args=([times, duration, delay]))
        if autostart:
            self.prevButtonThread.start()
    
    def blinkNext(self, times, duration, delay=0, autostart=True):
        self.clearNext()
        self.nextButtonThread = Thread(target=self.__blinkNextButton, args=([times, duration, delay]))
        if autostart:
            self.nextButtonThread.start()
    
    def blinkBoth(self, times, duration, delay=0):
        self.blinkPrev(times, duration, delay, False)
        self.blinkNext(times, duration, delay, False)
        self.prevButtonThread.start()
        self.nextButtonThread.start()
    
    def blinkAlternating(self, times, duration, delay=0):
        self.blinkPrev(times, duration, delay)
        self.blinkNext(times, duration, delay + duration)
    
    def clearPrev(self):
        if self.prevButtonThread is not None and self.prevButtonThread.is_alive():
            self.prevButtonCancelEvent.set()
            self.prevButtonThread.join()
            self.prevButtonCancelEvent.clear()
    
    def clearNext(self):
        if self.nextButtonThread is not None and self.nextButtonThread.is_alive():
            self.nextButtonCancelEvent.set()
            self.nextButtonThread.join()
            self.nextButtonCancelEvent.clear()
    
    def clearBoth(self):
        self.clearPrev()
        self.clearNext()

    def __blinkPrevButton(self, times, duration, delay=0):
        flag = self.prevButtonCancelEvent.wait(delay)
        if flag:
            return
        for i in range(times):
            GPIO.output(PREV_BUTTON_PIN, 1)
            flag = self.prevButtonCancelEvent.wait(duration)
            if flag:
                GPIO.output(PREV_BUTTON_PIN, 0)
                return
            GPIO.output(PREV_BUTTON_PIN, 0)
            flag = self.prevButtonCancelEvent.wait(duration)
            if flag:
                return

    def __blinkNextButton(self, times, duration, delay=0):
        flag = self.nextButtonCancelEvent.wait(delay)
        if flag:
            return
        for i in range(times):
            GPIO.output(NEXT_BUTTON_PIN, 1)
            flag = self.nextButtonCancelEvent.wait(duration)
            if flag:
                GPIO.output(NEXT_BUTTON_PIN, 0)
                return
            GPIO.output(NEXT_BUTTON_PIN, 0)
            flag = self.nextButtonCancelEvent.wait(duration)
            if flag:
                return

    def cleanup(self):
        self.clearBoth()


class Test():
    def prevButtonPressed(self):
        logging.info("PREV")
    
    def nextButtonPressed(self):
        logging.info("NEXT")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    GPIO.setmode(GPIO.BOARD)
    buttons = ButtonManager(Test())
    buttons.blinkPrev(5, 0.2)
    time.sleep(7)
    buttons.blinkNext(5, 0.2)
    time.sleep(7)
    buttons.blinkBoth(5, 0.2, 1)
    time.sleep(7)
    logging.info("Alternating. Delay 2 Seconds")
    buttons.blinkAlternating(5, 0.5, 2)
    time.sleep(7)
    logging.info("Both. Delay 2 Seconds")
    buttons.blinkBoth(100, 0.1, 2)
    time.sleep(3)
    buttons.cleanup()