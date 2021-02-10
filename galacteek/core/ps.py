import aiopubsub
import functools

from galacteek import log

gHub = aiopubsub.Hub()

publisher = aiopubsub.Publisher(gHub, prefix=aiopubsub.Key('g'))


def makeKey(*args):
    return aiopubsub.Key(*args)


def makeKeyChatChannel(channel):
    return aiopubsub.Key('g', 'chat', 'channels', channel)


@functools.lru_cache(maxsize=1)
def makeKeyChatUsersList(channel):
    return aiopubsub.Key('g', 'pubsub', 'chatuserslist', channel)


@functools.lru_cache(maxsize=1)
def makeKeyPubChatTokens(channel):
    return aiopubsub.Key('g', 'pubsub', 'tokens', 'pubchat', channel)


@functools.lru_cache(maxsize=1)
def makeKeyService(name: str):
    return aiopubsub.Key('g', 'services', name)


def makeKeySmartContract(cname: str, address: str):
    return aiopubsub.Key('g', 'smartcontracts', cname, address)


def psSubscriber(sid):
    return aiopubsub.Subscriber(gHub, sid)


keyAll = aiopubsub.Key('*')

keyPsJson = aiopubsub.Key('g', 'pubsub', 'json')
keyPsEncJson = aiopubsub.Key('g', 'pubsub', 'enc', 'json')

keyChatAll = aiopubsub.Key('g', 'pubsub', 'chat', '*')
keyChatChannels = aiopubsub.Key('g', 'pubsub', 'chat', 'channels')

keyChatChanList = aiopubsub.Key('g', 'pubsub', 'userchanlist')
keyChatChanListRx = aiopubsub.Key('g', 'pubsub', 'userchanlist', 'rx')

keyChatChanUserList = aiopubsub.Key('g', 'pubsub', 'chatuserlist', 'rx')
keyChatTokens = aiopubsub.Key('g', 'pubsub', 'chattokens')

keyTokensDagExchange = aiopubsub.Key('g', 'tokens', 'dagexchange')
keySnakeDagExchange = aiopubsub.Key('g', 'dagexchange', 'snake')
keyTokensIdent = aiopubsub.Key('g', 'tokens', 'ident')

keyServices = aiopubsub.Key('g', 'services')
keySmartContracts = aiopubsub.Key('g', 'smartcontracts', '*')

# The answer to everything
key42 = aiopubsub.Key('g', '42')

mSubscriber = psSubscriber('main')


def hubPublish(key, message):
    log.debug(f'hubPublish ({key}) : {message}')

    gHub.publish(key, message)


class KeyListener:
    listenTo = []

    def __init__(self):
        for key in self.listenTo:
            try:
                varName = '_'.join([c for c in key if c != '*'])
                coro = getattr(self, f'event_{varName}')
                log.debug(f'KeyListener for key {key}: binding to {coro}')
                mSubscriber.add_async_listener(key, coro)
            except Exception as err:
                log.debug(f'KeyListener: could not connect key {key}: {err}')
                continue
