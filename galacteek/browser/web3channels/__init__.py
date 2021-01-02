from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebChannel import QWebChannelAbstractTransport

from galacteek import log


class Web3Transport(QWebChannelAbstractTransport):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.messageReceived.connect(self.onMessage)

    def onMessage(self, message, transport):
        log.debug(f'Web3 transport message: {message}')


class Web3Channel(QWebChannel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setBlockUpdates(True)

    @property
    def objs(self):
        return self.registeredObjects()

    def register(self, name, obj):
        if name not in self.objs.keys():
            self.registerObject(name, obj)
        else:
            log.debug(f'{self!r}: not overwriting already existing object '
                      f'with name: {name}')

    def webChannelDebug(self):
        objects = self.registeredObjects()
        log.debug(f'{self}: web3 objects: {objects}')
        print(objects)

    def clone(self):
        nc = QWebChannel(self)

        objects = self.registeredObjects()
        print('cloning', objects)
        for objName, obj in objects:
            log.debug(f'{self}: cloning object with ID: {objName}')
            nc.registerObject(objName, obj)

        return nc
