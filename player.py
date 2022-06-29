#!/usr/bin/env python

import requests
import json
import time
import asyncio
import websockets
from threading import Thread

WS_URI = "ws://127.0.0.1:8082/events"

class Player(Thread):

    async def __wsOpen(self):
        self.connected = True
        self.connectionCallback(True)

    async def __wsClose(self):
        self.connected = False
        self.connectionCallback(False)

    async def __wsMessage(self, message):
        messageDict = json.loads(message)
        eventType = messageDict["event"]
        if eventType == "contextChanged":
            self.nowplaying = messageDict["uri"]
        self.messageCallback(message)

    def __init__(self, messageCallback, connectionCallback):
        Thread.__init__(self, daemon=True)
        self.nowplaying = ""
        self.messageCallback = messageCallback
        self.connectionCallback = connectionCallback
        self.connected = False

    def run(self):
        asyncio.run(self.listenToPlayer())

    async def listenToPlayer(self):
        try:
            self.listeningTask = asyncio.create_task(self.__listen(WS_URI))
            await self.listeningTask
        except asyncio.exceptions.CancelledError:
            # shutting down
            return

    async def __listen(self, uri):
        async for websocket in websockets.connect(uri, ping_interval=None, ping_timeout=None):
            await self.__wsOpen()
            try:
                async for message in websocket:
                    await self.__wsMessage(message)
            except websockets.ConnectionClosed:
                await self.__wsClose()
                continue
            except asyncio.exceptions.CancelledError:
                print("Shutting down. Disconnecting websocket")
                await websocket.close()
                raise

    def play(self, uri):
        if self.nowplaying != uri:
            if self.connected:
                requests.post("http://127.0.0.1:8082/player/load?uri=" + uri + "&play=true&shuffle=false")

    def pause(self):
        if self.connected:
            print("Pausing playback")
            requests.post("http://127.0.0.1:8082/player/pause")

    def next(self):
        if self.connected:
            print("Playing next song")
            requests.post("http://127.0.0.1:8082/player/next")

    def prev(self):
        if self.connected:
            print("Playing previous song")
            requests.post("http://127.0.0.1:8082/player/prev")

    def increaseVolume(self):
        if self.connected:
            print("Increasing volume by 1 step")
            requests.post("http://127.0.0.1:8082/player/set-volume?step=1")

    def decreaseVolume(self):
        if self.connected:
            print("Dereasing volume by 1 step")
            requests.post("http://127.0.0.1:8082/player/set-volume?step=-1")

    def cleanup(self):
        self.listeningTask.cancel()
        self.pause()

# class Callback():
#     def onConnection(self, connected):
#         print("Connected: " + str(connected))
    
#     def onMessage(self, message):
#         print("Message: " + message)

# if __name__ == '__main__':

#     cb = Callback()
#     p = Player(cb.onMessage, cb.onConnection)
#     p.start()

#     print("Sleeping for half a minute")
#     time.sleep(30)

#     print("Cleaning up")
#     p.cleanup()
    
