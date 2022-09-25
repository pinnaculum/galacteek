import re
from galacteek.core.asynclib import asyncReadFile
from galacteek.core import readQrcTextFile
from PyQt5.QtWebEngineWidgets import QWebEngineScript
from PyQt5.QtCore import QFile
from PyQt5.QtCore import QUrl


def scriptFromString(name, jsCode):
    script = QWebEngineScript()
    script.setName(name)
    script.setSourceCode(jsCode)
    script.setWorldId(QWebEngineScript.MainWorld)
    script.setInjectionPoint(QWebEngineScript.DocumentCreation)
    return script


async def scriptFromLocalFile(name, filePath):
    data = await asyncReadFile(filePath, mode='rt')
    return scriptFromString(name, data)


def scriptUrl(rscPath: str):
    if rscPath.startswith('qrc:'):
        return re.sub(r'^qrc:', ':', rscPath)

    return rscPath


def scriptFromQFile(name: str, rscPath: str):
    jsFile = QFile(scriptUrl(rscPath))
    if not jsFile.open(QFile.ReadOnly):
        print('Cannot open', rscPath)
        return

    try:
        libCode = jsFile.readAll().data().decode('utf-8')
        return scriptFromString(name, libCode)
    except Exception:
        return None


def ipfsClientScripts(connParams):
    jsFile = QFile(':/share/js/ipfs-http-client/index.min.js')
    if not jsFile.open(QFile.ReadOnly):
        return []

    ipfsInjTemplate = readQrcTextFile(':/share/js/ipfs/window-ipfs.js')

    ipfsInjTemplate = re.sub(
        '@HOST@',
        connParams.host,
        ipfsInjTemplate
    )

    ipfsInjTemplate = re.sub(
        '@API_PORT@',
        connParams.apiPort,
        ipfsInjTemplate

    )

    ipfsInjTemplate = re.sub(
        '@GATEWAY_URL@',
        str(connParams.gatewayUrl).rstrip('/'),
        ipfsInjTemplate
    )

    scriptJsIpfs = QWebEngineScript()
    scriptJsIpfs.setName('ipfs-http-client')

    libCode = jsFile.readAll().data().decode('utf-8')
    libCode += "\n"
    libCode += ipfsInjTemplate
    libCode += "\n"

    scriptJsIpfs.setSourceCode(libCode)
    scriptJsIpfs.setWorldId(QWebEngineScript.MainWorld)
    scriptJsIpfs.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scriptJsIpfs.setRunsOnSubFrames(True)

    return [scriptJsIpfs]


w3ScriptHttp = '''
window.web3 = new Web3(
    new Web3.providers.HttpProvider('{rpcurl}')
);
window.web3.eth.defaultAccount = window.web3.eth.accounts[0];
'''

w3ScriptWs = '''
window.web3 = new Web3(
    new Web3.providers.WebsocketProvider('{rpcurl}')
);
window.web3.eth.defaultAccount = window.web3.eth.accounts[0];
'''


def ethereumClientScripts(connParams):
    scripts = []
    jsFile = QFile(':/share/js/web3.min.js')
    if not jsFile.open(QFile.ReadOnly):
        return None

    libCode = jsFile.readAll().data().decode('utf-8')
    libCode += "\n"

    if connParams.provType == 'http':
        libCode += w3ScriptHttp.format(rpcurl=connParams.rpcUrl)
    elif connParams.provType == 'websocket':
        libCode += w3ScriptWs.format(rpcurl=connParams.rpcUrl)

    scriptWeb3 = QWebEngineScript()
    scriptWeb3.setName('web3.js')
    scriptWeb3.setSourceCode(libCode)
    scriptWeb3.setWorldId(QWebEngineScript.MainWorld)
    scriptWeb3.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scripts.append(scriptWeb3)
    return scripts


def orbitScripts(connParams):
    scripts = []
    jsFile = QFile(':/share/js/orbit-db/orbitdb.js')
    if not jsFile.open(QFile.ReadOnly):
        return
    scriptJsIpfs = QWebEngineScript()
    scriptJsIpfs.setName('orbit-db')
    scriptJsIpfs.setSourceCode(jsFile.readAll().data().decode('utf-8'))
    scriptJsIpfs.setWorldId(QWebEngineScript.MainWorld)
    scriptJsIpfs.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scriptJsIpfs.setRunsOnSubFrames(True)
    scripts.append(scriptJsIpfs)

    script = QWebEngineScript()
    script.setSourceCode('\n'.join([
        "document.addEventListener('DOMContentLoaded', function () {",
        "window.orbitdb = new OrbitDB(window.ipfs)",
        "})"]))
    script.setWorldId(QWebEngineScript.MainWorld)
    return scripts


def webTorrentScripts():
    scripts = []
    jsFile = QFile(':/share/js/webtorrent.min.js')
    if not jsFile.open(QFile.ReadOnly):
        return

    scriptWebTorrent = QWebEngineScript()
    scriptWebTorrent.setName('webtorrent')
    scriptWebTorrent.setSourceCode(jsFile.readAll().data().decode('utf-8'))
    scriptWebTorrent.setWorldId(QWebEngineScript.MainWorld)
    scriptWebTorrent.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scriptWebTorrent.setRunsOnSubFrames(True)
    scripts.append(scriptWebTorrent)
    return scripts


styleScr = """
(function() {

   css = document.createElement('style');
   css.type = 'text/css';
   css.id = '%s';

   document.head.appendChild(css);
   // document.getElementsByTagName('head')[0].appendChild(css);
   css.innerText = '%s';
})()
"""


def styleSheetScript(name: str, url: QUrl):
    scripts = []

    if url.scheme() == 'qrc':
        file = QFile(scriptUrl(url.toString()))

        if file.open(QFile.ReadOnly):
            try:
                text = file.readAll().data().decode('utf-8')
                css = text.replace("'", "\\'")

                code = styleScr % (name, ''.join(css.splitlines()))
                script = scriptFromString(name, code)

                if script is None:
                    # err
                    return scripts

                script.setRunsOnSubFrames(True)
                script.setInjectionPoint(QWebEngineScript.DocumentReady)
                script.setWorldId(QWebEngineScript.ApplicationWorld)

                scripts.append(script)
            except Exception:
                pass

    return scripts
