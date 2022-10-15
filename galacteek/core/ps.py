import aiopubsub
import functools

from galacteek import log
from galacteek.core import runningApp

gHub = aiopubsub.Hub()

publisher = aiopubsub.Publisher(gHub, prefix=aiopubsub.Key('g'))


@functools.lru_cache(maxsize=256)
def makeKey(*args) -> aiopubsub.Key:
    if isinstance(args, str):
        return aiopubsub.Key(args)
    elif isinstance(args, tuple):
        return aiopubsub.Key(*args)


def makeKeyChatChannel(channel) -> aiopubsub.Key:
    return makeKey('g', 'chat', 'channels', channel)


def makeKeyChatUsersList(channel) -> aiopubsub.Key:
    return makeKey('g', 'pubsub', 'chatuserslist', channel)


def makeKeyPubChatTokens(channel) -> aiopubsub.Key:
    return makeKey('g', 'pubsub', 'tokens', 'pubchat', channel)


def makeKeyService(*names) -> aiopubsub.Key:
    """
    Create a PS key for a galacteek service
    """
    return makeKey(*(('g', 'services') + tuple(names)))


def makeKeyServiceAll(*names) -> aiopubsub.Key:
    return makeKey(*(('g', 'services') + tuple(names) + tuple('*')))


def makeKeySmartContract(cname: str, address: str) -> aiopubsub.Key:
    return makeKey('g', 'smartcontracts', cname, address)


def psSubscriber(sid) -> aiopubsub.Subscriber:
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

keyIpidServExposure = makeKey('g', 'ipid', 'services', 'exposure')

keyLdObjects = makeKey('g', 'ld', 'objects')

# The answer to everything
key42 = makeKey('g', '42')

mSubscriber = psSubscriber('main')


def hubPublish(key, message) -> None:
    # Publishing to the hub should now always happen in the main loop

    try:
        app = runningApp()
        app.loop.call_soon_threadsafe(gHub.publish, key, message)
    except Exception as err:
        log.warning(f'Hub published failed: {err}')


def hubLdPublish(key,
                 event,
                 contextName='services/GenericServiceMessage',
                 **kw) -> None:
    """
    Publish a JSON-LD service event message on the
    pubsub hub, to the service's PS key
    """

    from galacteek.ld import ipsContextUri

    msg = {
        '@context': str(ipsContextUri(contextName)),
        'event': event
    }

    msg.update(**kw)

    hubPublish(key, msg)


class KeyListener(object):
    # Default PS keys we'll listen to
    psListenKeysDefault = [
        makeKeyService('app'),
        key42
    ]

    # User-defined keys, change this in descendant
    psListenKeys = []

    def __init__(self):
        self.psListenL(self.psListenKeysDefault)

        if len(self.psListenKeys) > 0:
            self.psListenL(self.psListenKeys)

    def trkeyc(self, comp: str):
        return 'all' if comp == '*' else comp

    def psListen(self, key, receiver=None):
        rcv = receiver if receiver else self
        try:
            coro = getattr(
                rcv,
                'event_{varName}'.format(
                    varName='_'.join([self.trkeyc(c) for c in key])
                )
            )

            assert coro is not None

            # We use the global subscriber by default
            mSubscriber.add_async_listener(key, coro)
        except AttributeError:
            pass
        except KeyError:
            # TODO: some key errors occur here
            pass
        except AssertionError:
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
