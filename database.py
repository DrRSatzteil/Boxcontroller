#!/usr/bin/env python

import json
import logging

DB_FILE_NAME = 'database.json'

class Database():

    def __init__(self):
        self.refreshDatabase()

    def refreshDatabase(self):
        try:
            with open(DB_FILE_NAME, 'r') as db:
                self.database = json.load(db)
            logging.info("Successfully loaded database file")
        except:
            self.database = {}
            logging.info("Could not load database file. Creating new database")
    
    def readPlaylist(self, uid):
        try:
            return self.database[uid]
        except:
            return None

    def setPlaylist(self, uid, playlist):
        logging.info("Adding entry for " + uid + " to database")
        self.database[uid] = playlist
        with open(DB_FILE_NAME, 'w') as db:
            json.dump(self.database, db)
            logging.info("Successfully saved database file")