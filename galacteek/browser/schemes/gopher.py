import traceback

from galacteek.browser.schemes import BaseURLSchemeHandler


try:
    import pituophis
except ImportError:
    haveGopherLib = False
else:
    haveGopherLib = True


class GopherSchemeHandler(BaseURLSchemeHandler):
    async def handleRequest(self, request, uid):
        rUrl = request.requestUrl()

        if not haveGopherLib:
            return self.reqFailed(request)

        if not rUrl.host():
            return self.urlInvalid(request)

        try:
            requrl = pituophis.parse_url(rUrl.toString())

            if not requrl:
                return self.urlInvalid(request)

            req = await self.app.rexec(requrl.get)

            comps = rUrl.path().lstrip('/').split('/')
            itemType = comps[0] if comps else '0'

            if itemType in ['p', 'g', '4', '5', 'I', '9']:
                # Serve as binary

                self.serveContent(
                    request.reqUid,
                    request,
                    'application/octet-stream',
                    req.binary
                )
            else:
                title = None
                body, bodyl = None, None

                # pituophis assumes utf-8 in .text() and .menu() ..
                # Instead, try a list of encodings

                for encoding in ['utf-8',
                                 'iso8859-1',
                                 'ascii',
                                 'iso-8859-2',
                                 'iso-8859-3',
                                 'iso-8859-4',
                                 'iso-8859-5',
                                 'iso-8859-6']:
                    try:
                        body = req.binary.decode(encoding)
                        menu = pituophis.parse_menu(body)
                    except Exception:
                        continue
                    else:
                        bodyl = body.split('\n')
                        break

                for item in menu:
                    if item.type == 'i' and item.text.strip() != '':
                        title = item.text
                        break

                for line in bodyl:
                    if line.startswith('i') and not title:
                        title = line[1:]
                        break

                await self.serveTemplate(
                    request,
                    'gopher_render.html',
                    url=rUrl,
                    itemType=itemType,
                    req=req,
                    bodytext=body,
                    bodylines=bodyl,
                    menu=menu,
                    charset=encoding.upper(),
                    title=title if title else rUrl.toString()
                )
        except Exception:
            traceback.print_exc()

            return self.reqFailed(request)
