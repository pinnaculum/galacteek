
from PyQt5.QtCore import QCoreApplication, QUrl, QStandardPaths, QSettings

# Settings sections
CFG_SECTION_IPFSD = 'ipfsdaemon'
CFG_SECTION_BROWSER = 'browser'
CFG_SECTION_IPFSCONN1 = 'ipfsconn1'

# Keys
CFG_KEY_HOMEURL = 'homeurl'
CFG_KEY_GOTOHOME = 'gotohomeonnewtab'
CFG_KEY_DLPATH = 'downloadspath'

CFG_KEY_ENABLED = 'enabled'

# These keys are for ipfsdaemon and ipfsconn sections
CFG_KEY_APIPORT = 'apiport'
CFG_KEY_SWARMPORT = 'swarmport'
CFG_KEY_HTTPGWPORT = 'httpgwport'
CFG_KEY_HOST = 'host'
CFG_KEY_SWARMLOWWATER = 'swarm_lowwater'
CFG_KEY_SWARMHIGHWATER = 'swarm_highwater'

# for fast access
S_HOMEURL = (CFG_SECTION_BROWSER, CFG_KEY_HOMEURL)
S_GOTOHOME = (CFG_SECTION_BROWSER, CFG_KEY_GOTOHOME)
S_DOWNLOADS_PATH = (CFG_SECTION_BROWSER, CFG_KEY_DLPATH)

class SettingsManager(object):
    # QSettings has its problems with pyqt5 regarding booleans
    trueVal = 'true'
    falseVal = 'false'

    def __init__(self, path=None):
        self.settings = QSettings(path, QSettings.IniFormat)

    def sync(self):
        return self.settings.sync()

    def eSet(self, key, value):
        return self.setSetting(key[0], key[1], value)

    def eGet(self, key, type=None):
        return self.getSetting(key[0], key[1], type=type)

    def setSetting(self, section, name, value):
        self.settings.setValue('{0}/{1}'.format(section, name), value)

    def setDefaultSetting(self, section, name, value):
        existing = self.getSetting(section, name)
        if not existing:
            self.settings.setValue('{0}/{1}'.format(section, name), value)

    def getInt(self, section, name):
        return self.getSetting(section, name, type=int)

    def getSetting(self, section, name, type=None):
        key = '{0}/{1}'.format(section, name)
        if type:
            return self.settings.value(key, type=type)
        else:
            return self.settings.value(key)

    def setTrue(self, section, name):
        return self.setSetting(section, name, self.trueVal)

    def setFalse(self, section, name):
        return self.setSetting(section, name, self.falseVal)

    def isTrue(self, section, name):
        return self.getSetting(section, name) == self.trueVal

    def isFalse(self, section, name):
        return self.getSetting(section, name) == self.falseVal
