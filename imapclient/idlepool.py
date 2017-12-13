from threading import RLock
from threading import Thread
from threading import Event

from selectors2 import DefaultSelector
from selectors2 import EVENT_READ

import time

import logging

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Idlepool(metaclass=Singleton):
    def __init__(self):
        self.clients = {}
        self.selector = DefaultSelector()
        self.lock = RLock()
        self.validationThread = Thread(target=self.validate)
        self.validationThread.start()
        self.logger = logging.getLogger(__name__)

    def validate(self):
        while True:
            hasClients = False
            with self.lock:
                hasClients = len(self.clients) > 0

            if not hasClients:
                time.sleep(5)
                continue

            events = self.selector.select(timeout=15)

            clientsToNofify = []
            for key, _ in events:
                clientId = key.data
                clientsToNofify.append(clientId)

            for clientId in clientsToNofify:
                self.notifyClient(clientId)

    def notifyClient(self, clientId):
        with self.lock:
            if clientId in self.clients:
                dict = self.clients[clientId]
                event = dict['event']
                event.set()

    def registerClient(self, clientId, client, event):
        if not clientId or not client or not event:
            return

        with self.lock:
            if clientId in self.clients:
                return

            try:
                self.clients[clientId] = { 'client' : client, 'event' : event }
                self.selector.register(client._imap.sock, EVENT_READ, clientId)
            except Exception as e:
                self.logger.exception('[%s] Could not register client with exception: %s', clientId, e)

    def unregisterClient(self, clientId):
        if not clientId:
            return

        with self.lock:
            if clientId in self.clients:
                dict = self.clients[clientId]
                client = dict['client']
                try:
                    self.selector.unregister(client._imap.sock)
                    del self.clients[clientId]
                except Exception as e:
                    self.logger.exception('[%s] Could not unregister client with exception: %s', clientId, e)



