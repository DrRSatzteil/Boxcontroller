#!/usr/bin/env python

import logging
import time
import sys
from meter import Meter
from rpi_ws281x import PixelStrip, Color
from threading import Thread, Event

LED_COUNT = 24        # Number of LED pixels.
LED_PIN = 12          # GPIO pin connected to the pixels
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 128   # Set to 0 for darkest and 255 for brightest
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

class Led():
    
    def __init__(self, withMeter=True):
        # LED strip configuration:
        self.programmingMode = False
        self.lowPowerMode = False
        self.lowPowerCancelEvent = Event()
        self.lowPowerSignalThread = None
        self.strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()
        self.cancel_event = Event()
        self.currentThread = None
        if withMeter:
            self.meter = Meter(self.volumeLevel, smooth=True)
            self.meter.startMeter()

    def __volume(self, volume, fade_delay_ms=3000):
        """Draw volume visualization. 70% -> green, 20% -> yellow, 10% -> red"""
        for i in range(self.strip.numPixels()):
            percentage = ((self.strip.numPixels() - i) / self.strip.numPixels()) * 100
            if percentage > volume:
                self.strip.setPixelColor(i, Color(0,0,0))
            elif (percentage <= 70):
                self.strip.setPixelColor(i, Color(round(255*(percentage / 70)),255,0))
            elif (percentage <= 90):
                self.strip.setPixelColor(i, Color(255,255-round(255*((percentage-70)/20)),0))
            else:
                self.strip.setPixelColor(i, Color(255,0,0))
        self.strip.show()
        flag = self.cancel_event.wait(fade_delay_ms / 1000.0)
        if not flag:
            self.__fadeOut()
    
    def __fadeOut(self, wait_ms=40):
        while self.strip.getBrightness() > 0:
            self.strip.setBrightness(self.strip.getBrightness() - 1)
            self.strip.show()
            flag = self.cancel_event.wait(wait_ms / 1000.0)
            if flag:
                self.strip.setBrightness(LED_BRIGHTNESS)
                self.clear()
                return
        self.clear()
        self.strip.setBrightness(LED_BRIGHTNESS)

    def __wheel(self, pos):
        """Generate rainbow colors across 0-255 positions."""
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    def __skip(self, invert, trail=6, wait_ms=50):
        """Left to right or right to left swipe."""
        lightsArray = [[19], [18, 20], [17, 21], [16, 22], [15, 23], [14, 24], [13, 1], [12, 2], [11, 3], [10, 4], [9, 5], [8, 6], [7]]
        if invert:
            lightsArray = lightsArray[::-1]
        for lights in range(12 + trail):
            if lights <= 12:
                for light in lightsArray[lights]:
                    self.strip.setPixelColor(light, Color(0,255,0))
            if lights - (trail - 1) >= 0:
                for light in lightsArray[lights - (trail - 1)]:
                    self.strip.setPixelColor(light, Color(0,0,0))
            self.strip.show()
            sleep_multi = abs(lights - 7) / 7
            flag = self.cancel_event.wait((wait_ms * sleep_multi) / 1000.0)
            if flag:
                self.clear()
                return

    def volumeLevel(self, leftChannel, rightChannel):
        if self.currentThread is not None and self.currentThread.is_alive():
            return

        greenPercentage = 40
        yellowPercentage = 60
        redPercentage = 75
        rightChannelLeds = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0]
        leftChannelLeds = [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
        
        steps = 100 / (len(leftChannelLeds) + 1)

        for i in range(len(leftChannelLeds)):

            red = round(255 * min(1, (max(0, (i * steps - greenPercentage)) / (yellowPercentage - greenPercentage))))
            green = round(255 - (255 * min(1, max(0, (i * steps - yellowPercentage)) / (redPercentage - yellowPercentage))))
            blue = 0
            
            color = Color(red, green, blue)
            leftLed = leftChannelLeds[i]
            rightLed = rightChannelLeds[i]
            if leftLed == rightLed:
                if i * steps < max(leftChannel, rightChannel):
                    self.strip.setPixelColor(leftLed, color)
                else:
                    self.strip.setPixelColor(leftLed, Color(0,0,0))
            else:
                if i * steps < leftChannel:
                    self.strip.setPixelColor(leftLed, color)
                else:
                    self.strip.setPixelColor(leftLed, Color(0,0,0))
                if i * steps < rightChannel:
                    self.strip.setPixelColor(rightLed, color)
                else:
                    self.strip.setPixelColor(rightLed, Color(0,0,0))
                    
        self.strip.setBrightness(25)
        self.strip.show()
        self.strip.setBrightness(LED_BRIGHTNESS)

    def __theaterChaseRainbow(self, wait_ms=50):
        """Rainbow movie theater light style chaser animation."""
        for j in range(256):
            for q in range(3):
                for i in range(0, self.strip.numPixels(), 3):
                    self.strip.setPixelColor(i + q, self.__wheel((i + j) % 255))
                self.strip.show()
                flag = self.cancel_event.wait(wait_ms / 1000.0)
                if flag:
                    return
                for i in range(0, self.strip.numPixels(), 3):
                    self.strip.setPixelColor(i + q, 0)

    def __rainbowCycle(self, wait_ms=10, iterations=10000):
        """Draw rainbow that uniformly distributes itself across all pixels."""
        for j in range(256 * iterations):
            for i in range(self.strip.numPixels()):
                self.strip.setPixelColor(i, self.__wheel(
                    (int(i * 256 / self.strip.numPixels()) + j) & 255))
            self.strip.show()
            flag = self.cancel_event.wait(wait_ms / 1000.0)
            if flag:
                return
    
    # iterations == 0 means infinite
    def __pulse(self, color, iterations=0, wait_ms=15):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, color)
        self.strip.setBrightness(0)
        self.strip.show()
        if iterations == 0:
            remainingIterations = sys.maxsize
        else:
            remainingIterations = iterations
        while self.strip.getBrightness() < LED_BRIGHTNESS:
            self.strip.setBrightness(self.strip.getBrightness() + 1)
            self.strip.show()
            sleep_multi = self.strip.getBrightness() / LED_BRIGHTNESS
            flag = self.cancel_event.wait(sleep_multi* (wait_ms / 1000.0))
            if flag:
                return
            if self.strip.getBrightness() == LED_BRIGHTNESS:
                remainingIterations = remainingIterations - 1
                while self.strip.getBrightness() > 0:
                    self.strip.setBrightness(self.strip.getBrightness() - 1)
                    self.strip.show()
                    sleep_multi = self.strip.getBrightness() / LED_BRIGHTNESS
                    flag = self.cancel_event.wait(sleep_multi* (wait_ms / 1000.0))
                    if flag:
                        return
                    if self.strip.getBrightness() == 0 and remainingIterations == 0:
                        self.clear()
                        self.strip.setBrightness(LED_BRIGHTNESS)
                        return

    def __flash(self, color, wait_ms=0.1):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, color)
        self.strip.setBrightness(0)
        self.strip.show()
        while self.strip.getBrightness() < LED_BRIGHTNESS:
            sleep_multi = self.strip.getBrightness() / LED_BRIGHTNESS
            flag = self.cancel_event.wait(wait_ms / 1000.0)
            if flag:
                self.strip.setBrightness(LED_BRIGHTNESS)
                return
            self.strip.setBrightness(self.strip.getBrightness() + 1)
            self.strip.show()
        while self.strip.getBrightness() > 0:
            sleep_multi = self.strip.getBrightness() / LED_BRIGHTNESS
            flag = self.cancel_event.wait(wait_ms / 1000.0)
            if flag:
                self.strip.setBrightness(LED_BRIGHTNESS)
                return
            self.strip.setBrightness(self.strip.getBrightness() - 1)
            self.strip.show()
        self.strip.setBrightness(LED_BRIGHTNESS)
        self.clear()

    def clear(self):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0,0,0))
            self.strip.show()
    
    def engageLowPowerMode(self, powerIsLow):
        if powerIsLow and not self.lowPowerMode:
            logging.info("Entering low power mode")
            self.lowPowerMode = True
            self.lowPowerSignalThread = Thread(target=self.__signalLowPower, daemon = True)
            self.lowPowerSignalThread.start()
        if not powerIsLow:
            logging.info("Stopping low power mode")
            self.lowPowerMode = False
            if self.lowPowerSignalThread is not None and self.lowPowerSignalThread.is_alive():
                self.lowPowerCancelEvent.set()
                self.lowPowerSignalThread.join()
                self.lowPowerCancelEvent.clear()
    
    def __signalLowPower(self):
        while True:
            # Wait for 20 seconds: since we update the power state every 15 seconds
            # we need two consecutive low power values before we start signalling
            flag = self.lowPowerCancelEvent.wait(20)

            if flag:
                return

            # Skip signaling when something else is currently going on
            if self.currentThread is None or not self.currentThread.is_alive():
                self.currentThread = Thread(target=self.__pulse, args=([Color(255,0,0), 3, 3]))
                self.currentThread.start()
            
    
    def engageProgrammingMode(self):
        logging.info("Entering programming mode")
        self.programmingMode = True
        self.cancel()
        self.currentThread = Thread(target=self.__pulse, args=([Color(0,255,0)]))
        self.currentThread.start()

    def programmingSucessful(self):
        logging.info("Programming was successful. Stopping animation...")
        # Assume that the current animation is the "programming pulse"
        self.cancel()
        self.currentThread = Thread(target=self.__pulse, args=([Color(0,255,0), 3, 1]))
        self.currentThread.start()
        self.programmingMode = False

    def programmingFailed(self):
        logging.info("Programming was not successful. Stopping animation...")
        # Assume that the current animation is the "programming pulse"
        self.cancel()
        self.currentThread = Thread(target=self.__pulse, args=([Color(255,0,0), 3, 1]))
        self.currentThread.start()
        self.programmingMode = False

    def signalVolumeChange(self, newVolume):
        if not self.programmingMode:
            self.cancel()
            self.currentThread = Thread(target=self.__volume, args=([newVolume]))
            self.currentThread.start()
    
    def startWaitAninmation(self):
        self.cancel()
        self.currentThread = Thread(target=self.__rainbowCycle)
        self.currentThread.start()

    def stopWaitAninmation(self):
        self.cancel()
        self.currentThread = Thread(target=self.__fadeOut)
        self.currentThread.start()

    def cancel(self):
        if self.currentThread is not None and self.currentThread.is_alive():
            self.cancel_event.set()
            self.currentThread.join()
            self.currentThread = None
        self.cancel_event.clear()
    
    def cleanup(self):
        self.lowPowerCancelEvent.set()
        self.meter.stopMeter()
        self.cancel()
        self.clear()

# Used for testing
if __name__ == "__main__":
    led = Led()
    # led.engageLowPowerMode(True)
    # time.sleep(25)
    # led.engageLowPowerMode(False)

    #led.engageProgrammingMode()
    #time.sleep(20)
    #led.programmingFailed()

    # led.test()

    # led.cleanup()

    # for i in range(255):
    #     c = Color(255,0,0,i)
    #     for i in range(led.strip.numPixels()):
    #         led.strip.setPixelColor(i + 1, c)
    #     led.strip.show()
    #     time.sleep(0.1)


    #led.test()

    # time.sleep(0.5)

    logging.basicConfig(level=logging.DEBUG)

    # led.volumeLevel(100, 0)

    time.sleep(100)

    # led.volumeLevel(0,100)

    # time.sleep(15)

    # led.volumeLevel(0, 0)

    # led.signalVolumeChange(100)

    #time.sleep(15)

    #led.__volume(0)


    # led.volumeLevel(200, 200)

    # for i in range(101):
    #     led.volumeLevel(i, 0)
    #     time.sleep(0.05)
    
    # for i in range(101):
    #     led.volumeLevel(100 - i, 0)
    #     time.sleep(0.05)
    
    # for i in range(101):
    #     led.volumeLevel(0, i)
    #     time.sleep(0.05)
    
    # for i in range(101):
    #     led.volumeLevel(0, 100 - i)
    #     time.sleep(0.05)

    #led.engageProgrammingMode()
    #time.sleep(20)
    #led.programmingSucessful()

    #time.sleep(10)
