from PyQt5.QtCore import QUrl

from galacteek.browser.schemes import NativeIPFSSchemeHandler
from galacteek.browser.schemes import SCHEME_MAGNET


class WebTorrentSchemeHandler(NativeIPFSSchemeHandler):
    async def handleRequest(self, request, uid):
        rUrl = request.requestUrl()

        tmpl = self.app.jinjaEnv.get_template(
            'webtorrent/magnet_render.jinja2'
        )

        if not tmpl:
            return self.reqFailed(request)

        # Force url scheme and empty path
        mUrl = QUrl(rUrl)
        mUrl.setPath('')
        mUrl.setScheme(SCHEME_MAGNET)

        try:
            webTorrentId = mUrl.toString()
            self.serveContent(
                uid,
                request,
                'text/html',
                (await tmpl.render_async(
                    webTorrentId=webTorrentId
                )).encode()
            )
        except Exception:
            self.reqFailed(request)
