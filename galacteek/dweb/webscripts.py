from PyQt5.QtWebEngineWidgets import QWebEngineScript
from PyQt5.QtCore import QFile


def ipfsClientScripts(connParams):
    scripts = []
    jsFile = QFile(':/share/js/ipfs-http-client/index.min.js')
    if not jsFile.open(QFile.ReadOnly):
        return
    scriptJsIpfs = QWebEngineScript()
    scriptJsIpfs.setName('ipfs-http-client')
    scriptJsIpfs.setSourceCode(jsFile.readAll().data().decode('utf-8'))
    scriptJsIpfs.setWorldId(QWebEngineScript.MainWorld)
    scriptJsIpfs.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scriptJsIpfs.setRunsOnSubFrames(True)
    scripts.append(scriptJsIpfs)

    script = QWebEngineScript()
    script.setSourceCode('\n'.join([
        "document.addEventListener('DOMContentLoaded', function () {",
        "window.ipfs = window.IpfsHttpClient('{host}', '{port}');".format(
            host=connParams.host,
            port=connParams.apiPort),
        "})"]))
    script.setWorldId(QWebEngineScript.MainWorld)
    script.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scripts.append(script)
    return scripts


def web3ClientScripts():
    scripts = []
    jsFile = QFile(':/share/js/web3.min.js')
    if not jsFile.open(QFile.ReadOnly):
        return
    scriptJsIpfs = QWebEngineScript()
    scriptJsIpfs.setName('web3')
    scriptJsIpfs.setSourceCode(jsFile.readAll().data().decode('utf-8'))
    scriptJsIpfs.setWorldId(QWebEngineScript.MainWorld)
    scriptJsIpfs.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scriptJsIpfs.setRunsOnSubFrames(True)
    scripts.append(scriptJsIpfs)

    script = QWebEngineScript()
    script.setSourceCode(
        '''
        document.addEventListener('DOMContentLoaded', function () {
            const web3 = new Web3(
                new Web3.providers.HttpProvider("http://localhost:7545")
            );
            web3.eth.defaultAccount = web3.eth.accounts[0];
            window.web3 = web3;
        });
        ''')
    script.setWorldId(QWebEngineScript.MainWorld)
    script.setInjectionPoint(QWebEngineScript.DocumentCreation)
    scripts.append(script)
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
