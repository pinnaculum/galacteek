import asyncio
from pathlib import Path

from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebEngineWidgets import QWebEngineScript
from PyQt5.QtWebEngineWidgets import QWebEngineDownloadItem

from PyQt5.QtPrintSupport import *

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QUrl

from PyQt5.QtGui import QColor

from galacteek import partialEnsure
from galacteek.ipfs import cidhelpers
from galacteek.dweb.render import renderTemplate

from ..helpers import *


class BrowserDwebPage (QWebEnginePage):
    jsConsoleMessage = pyqtSignal(int, str, int, str)

    acceptedNavRequest = pyqtSignal(QUrl, int)

    def __init__(self, webProfile, parent):
        super(BrowserDwebPage, self).__init__(webProfile, parent)
        self.app = QCoreApplication.instance()
        self.fullScreenRequested.connect(self.onFullScreenRequest)
        self.featurePermissionRequested.connect(
            partialEnsure(self.onPermissionRequest))
        self.featurePermissionRequestCanceled.connect(
            partialEnsure(self.onPermissionRequestCanceled))
        self.setBgColor(self.app.theme.colors.webEngineBackground)

    @property
    def channel(self):
        return self.webChannel()

    def setBgColor(self, col):
        self.setBackgroundColor(QColor(col))

    def setBgActive(self):
        self.setBgColor(self.app.theme.colors.webEngineBackgroundActive)

    def onRenderProcessPid(self, pid):
        log.debug(f'{self.url().toString()}: renderer process has PID: {pid}')

    def acceptNavigationRequest(self,
                                url,
                                navType,
                                isMainFrame: bool) -> bool:
        self.acceptedNavRequest.emit(url, navType)

        return True

    def certificateError(self, error):
        return questionBox(
            error.url().toString(),
            f'Certificate error: {error.errorDescription()}.'
            '<b>Continue</b> ?')

    async def onPermissionRequestCanceled(self, originUrl, feature):
        pass

    async def onPermissionRequest(self, originUrl, feature):
        url = originUrl.toString().rstrip('/')

        def allow():
            self.setFeaturePermission(originUrl, feature,
                                      QWebEnginePage.PermissionGrantedByUser)

        def deny():
            self.setFeaturePermission(originUrl, feature,
                                      QWebEnginePage.PermissionDeniedByUser)

        log.debug(f'Permission request ({url}): {feature}')

        fMapping = {
            QWebEnginePage.Geolocation: ("Geolocation", 1),
            QWebEnginePage.MouseLock: ("Mouse lock", 2),
            QWebEnginePage.DesktopVideoCapture:
            ("Desktop video capture", 3),
            QWebEnginePage.DesktopAudioVideoCapture:
                ("Desktop audio and video capture", 4),
            QWebEnginePage.MediaAudioVideoCapture:
                ("Audio and video capture", 5),
            QWebEnginePage.MediaAudioCapture:
                ("Audio capture", 6),
            QWebEnginePage.MediaVideoCapture:
                ("Video capture", 7)
        }

        fmap = fMapping.get(feature, None)

        if not fmap:
            log.debug(f'Unknown feature requested: {feature}')
            deny()
            return

        featureS, fCode = fmap

        rule = await database.browserFeaturePermissionFilter(
            url, fCode)

        if rule:
            if rule.permission == database.BrowserFeaturePermission.PERM_ALLOW:
                allow()
                return
            if rule.permission == database.BrowserFeaturePermission.PERM_DENY:
                deny()
                return

        dlg = BrowserFeatureRequestDialog(url, featureS)
        await runDialogAsync(dlg)

        result = dlg.result()
        if result in [1, 2]:
            allow()

            if result == 2:
                # Add a rule to always allow this feature
                await database.browserFeaturePermissionAdd(
                    url, fCode,
                    database.BrowserFeaturePermission.PERM_ALLOW
                )
        elif result == 0:
            deny()
        else:
            log.debug(f'Unknown result from dialog: {result}')

    def onFullScreenRequest(self, req):
        # Accept fullscreen requests unconditionally
        req.accept()

    def changeWebChannel(self, channel):
        self.setWebChannel(channel)

    def registerPageHandler(self):
        self.changeWebChannel(QWebChannel(self))
        self.pageHandler = CurrentPageHandler(self)
        self.channel.registerObject('gpage', self.pageHandler)

    def registerChannelHandler(self, name, handler):
        if not self.channel:
            self.changeWebChannel(QWebChannel(self))

        self.channel.registerObject(name, handler)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        self.jsConsoleMessage.emit(level, message, lineNumber, sourceId)

    def registerProtocolHandlerRequested(self, request):
        """
        registerProtocolHandlerRequested(request) can be used to
        handle JS 'navigator.registerProtocolHandler()' calls. If
        we want to enable that in the future it'll be done here.
        """

        scheme = request.scheme()
        origin = request.origin()

        qRet = questionBox(
            'registerProtocolHandler',
            'Allow {origin} to register procotol handler for: {h} ?'.format(
                origin=origin.toString(),
                h=scheme
            )
        )

        if qRet is True:
            request.accept()
        else:
            request.reject()

    async def render(self, tmpl, url=None, **ctx):
        if url:
            self.setHtml(await renderTemplate(tmpl, **ctx), url)
        else:
            self.setHtml(await renderTemplate(tmpl, **ctx))

    async def runJs(self, script: str,
                    worldId: int = QWebEngineScript.MainWorld):
        """
        Wraps runJavaScript with an asyncio.Future
        """

        f = asyncio.Future()

        def callback(result):
            if type(result) in [str, int, float]:
                f.set_result(result)
            else:
                f.set_result(None)

        self.runJavaScript(script, worldId, callback)
        return await f

    async def getPageLanguage(self) -> str:
        """
        Return the page's language (bcp47 tag)
        """
        return await self.runJs('''
            document.getElementsByTagName('html')[0].getAttribute('lang');
        ''')

    def savePageComplete(self, dst: str = 'downloads') -> Path:
        """
        Save this QWebEnginePage as a complete html with resources
        """

        dstd = self.app.tempDirWeb if dst == 'downloads' else \
            self.app.tempDirArchive

        tmpd = Path(self.app.tempDirCreate(dstd))

        filename = self.url().fileName()

        if not filename or cidhelpers.cidValid(filename):
            filename = 'index.html'

        self.save(
            str(tmpd.joinpath(filename)),
            QWebEngineDownloadItem.CompleteHtmlSaveFormat
        )

        return tmpd
