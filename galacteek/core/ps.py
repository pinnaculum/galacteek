import aiopubsub
import functools

from galacteek import log
from galacteek.core import runningApp

gHub = aiopubsub.Hub()

publisher = aiopubsub.Publisher(gHub, prefix=aiopubsub.Key('g'))


@functools.lru_cache(maxsize=256)
def makeKey(*args):
    if isinstance(args, str):
        return aiopubsub.Key(args)
    elif isinstance(args, tuple):
        return aiopubsub.Key(*args)


def makeKeyChatChannel(channel):
    return makeKey('g', 'chat', 'channels', channel)


def makeKeyChatUsersList(channel):
    return makeKey('g', 'pubsub', 'chatuserslist', channel)


def makeKeyPubChatTokens(channel):
    return makeKey('g', 'pubsub', 'tokens', 'pubchat', channel)


def makeKeyService(*names):
    return makeKey(*(('g', 'services') + tuple(names)))


def makeKeyServiceAll(*names):
    return makeKey(*(('g', 'services') + tuple(names) + tuple('*')))


def makeKeySmartContract(cname: str, address: str):
    return makeKey('g', 'smartcontracts', cname, address)


def psSubscriber(sid):
    return aiopubsub.Subscriber(gHub, sid)


keyAll = makeKey('*')

keyPsJson = makeKey('g', 'pubsub', 'json')
keyPsEncJson = makeKey('g', 'pubsub', 'enc', 'json')

keyChatAll = makeKey('g', 'pubsub', 'chat', '*')
keyChatChannels = makeKey('g', 'pubsub', 'chat', 'channels')

keyChatChanList = makeKey('g', 'pubsub', 'userchanlist')
keyChatChanListRx = makeKey('g', 'pubsub', 'userchanlist', 'rx')

keyChatChanUserList = makeKey('g', 'pubsub', 'chatuserlist', 'rx')
keyChatTokens = makeKey('g', 'pubsub', 'chattokens')

keyTokensDagExchange = makeKey('g', 'tokens', 'dagexchange')
keySnakeDagExchange = makeKey('g', 'dagexchange', 'snake')
keyTokensIdent = makeKey('g', 'tokens', 'ident')

keyServices = makeKey('g', 'services')
keyServicesAll = makeKey('g', 'services', '*')
keySmartContracts = makeKey('g', 'smartcontracts', '*')

# The answer to everything
key42 = makeKey('g', '42')

mSubscriber = psSubscriber('main')


def hubPublish(key, message):
    log.debug(f'hubPublish ({key}) : {message}')

    # Hub publishing should now always happen in the main loop
    app = runningApp()
    app.loop.call_soon_threadsafe(gHub.publish, key, message)


class KeyListener(object):
    # Default PS keys we'll listen to
    psListenKeysDefault = [
        makeKeyService('app'),
        key42
    ]

    # User-defined keys, change this in descendant
    psListenKeys = []

    def __init__(self):
        # self.subscriberR = psSubscriber(uid4())

        self.psListenL(self.psListenKeysDefault)
        self.psListenL(self.psListenKeys)

    def psListen(self, key, receiver=None):
        rcv = receiver if receiver else self
        try:
            def tr(comp):
                if comp == '*':
                    return 'all'

                return comp

            varName = '_'.join([tr(c) for c in key])

            coro = getattr(rcv, f'event_{varName}')
            log.debug(f'KeyListener for key {key}: binding to {coro}')

            # We use the global subscriber by default
            mSubscriber.add_async_listener(key, coro)
        except AttributeError:
            pass
        except Exception as err:
            log.debug(f'KeyListener: could not connect key {key}: {err}')

    def psListenL(self, keys: list, receiver=None):
        for key in keys:
            self.psListen(key, receiver=receiver)

    def psListenFromConfig(self, cfg, receiver=None):
        for keyPath in cfg.psKeysListen:
            try:
                keyName = tuple(keyPath.split('/'))
                self.psListen(makeKey(keyName))
            except Exception as err:
                log.debug(
                    f'KeyListener: could not connect key {keyPath}: {err}')
                continue
