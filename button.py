#!/usr/bin/env python
#
########################################################################################################################
########################################################################################################################
##
##      Copyright (C) 2019 Peter Walsh, Milford, NH 03055
##      All Rights Reserved under the MIT license as outlined below.
##
##  FILE
##      Button.py
##
##  DESCRIPTION
##
##      GPIO Button interface for debounce
##
##  DATA
##
##      None.
##
##  FUNCTIONS
##
##      Desc = ButtonCallback(GPIO_BUTTON,CallbackFunc)         # Make a button callback descriptor
##
##  ISA
##
##      None.
##
########################################################################################################################
########################################################################################################################
##
##  MIT LICENSE
##
##  Permission is hereby granted, free of charge, to any person obtaining a copy of
##    this software and associated documentation files (the "Software"), to deal in
##    the Software without restriction, including without limitation the rights to
##    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
##    of the Software, and to permit persons to whom the Software is furnished to do
##    so, subject to the following conditions:
##
##  The above copyright notice and this permission notice shall be included in
##    all copies or substantial portions of the Software.
##
##  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
##    INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
##    PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
##    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
##    OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
##    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
##
########################################################################################################################
########################################################################################################################

import RPi.GPIO as GPIO 
import threading

########################################################################################################################
########################################################################################################################
##
## Data Declarations
##

DEBOUNCE_MS = 50                        # Debounce time, in ms
UPDATE_MS   = 5                         # Update/check time, in ms

##
## Endo of user configurable options
##
########################################################################################################################
########################################################################################################################

#
# Implement a software debounce for the trigger button
#
class ButtonHandler(threading.Thread):
    def __init__(self, pin, func, edge='both', bouncetime=200):
        super().__init__(daemon=True)

        self.edge = edge
        self.func = func
        self.pin = pin
        self.bouncetime = bouncetime
        self.bounceleft = bouncetime
        self.bouncing   = 0
        self.prevpinval = GPIO.input(self.pin)

    def __call__(self, *args):
        if self.bouncing:
            return

        self.bouncing   = 1
        self.bounceleft = self.bouncetime
        self.prevpinval = GPIO.input(self.pin)
        self.timer = threading.Timer(UPDATE_MS/1000.0, self.Tick, args=args)
        self.timer.start()

    def Tick(self, *args):
        pinval = GPIO.input(self.pin)

        if self.edge == GPIO.RISING  and pinval == 0:
            self.bouncing = 0
            return

        if self.edge == GPIO.FALLING and pinval == 1:
            self.bouncing = 0
            return

        if pinval != self.prevpinval:
            self.bounceleft = self.bouncetime

        self.bounceleft -= UPDATE_MS

        if self.bounceleft <= 0:
            self.bouncing   = 0
            self.func(*args)
            self.prevpinval = pinval
            return

        self.prevpinval = pinval
        self.timer = threading.Timer(UPDATE_MS/1000.0, self.Tick, args=args)
        self.timer.start()


########################################################################################################################
########################################################################################################################
##
## ButtonCallback - Setup a GPIO button with debounce and callback
##
## Inputs:      Connector GPIO pin to use
##              Direction of pin change (one of: GPIO.RISING, GPIO.FALLING, or GPIO.BOTH)
##              Callback to call when button pressed
##
## Outputs:     Descriptor of callback
##
def ButtonCallback(GPIO_PIN,GPIO_DIR,CallbackFunc):

    Desc = ButtonHandler(GPIO_PIN, CallbackFunc, edge=GPIO_DIR, bouncetime=DEBOUNCE_MS)
    Desc.start()

    GPIO.add_event_detect(GPIO_PIN, GPIO_DIR, callback=Desc)

    return Desc