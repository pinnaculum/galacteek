import orjson
import asyncio
import aioipfs

from cachetools import cached
from cachetools import TTLCache

from urllib.parse import urlparse

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import joinIpns
from galacteek import log

from pyld.jsonld import JsonLdError


@cached(TTLCache(2, 20))
async def keysList(client):
    return await client.key.list()


contextsCache = TTLCache(32, 180)


async def aioipfs_document_loader(ipfsClient: aioipfs.AsyncIPFS,
                                  ldSchemas,
                                  loop=None,
                                  secure=False, **kwargs):
    if loop is None:
        loop = asyncio.get_event_loop()

    async def async_loader(client, url, options={}):
        """
        :param url: the URL to retrieve.

        :return: the RemoteDocument.
        """
        try:
            o = urlparse(url)
            if o.scheme in ['ipschema', 'ips']:
                ipsKey = o.netloc

                if not ipsKey:
                    raise Exception(f'Invalid context url: {url}')

                if ipsKey == 'galacteek.ld.contexts':
                    # Compat
                    ipsKey = 'galacteek.ld'

                if not o.path or o.path == '/':
                    return {
                        'contentType': 'application/ld+json',
                        'document': {},
                        'documentUrl': url,
                        'contextUrl': None
                    }

                    raise JsonLdError(
                        f'Invalid context path for URL: {url}',
                        'jsonld.InvalidUrl', {'url': url},
                        code='loading document failed'
                    )

                if url in contextsCache:
                    # In cache already

                    return {
                        'contentType': 'application/ld+json',
                        'document': contextsCache[url],
                        'documentUrl': url,
                        'contextUrl': None
                    }

                sIpfsPath = await ldSchemas.nsToIpfs(ipsKey)
                path = None if sIpfsPath is None else sIpfsPath.child(o.path)
            else:
                path = IPFSPath(url)
                if not path.valid:
                    raise Exception(f'Not a valid path: {url}')

            if path and path.valid:
                data = await asyncio.wait_for(
                    client.cat(path.objPath), 10
                )

                obj = orjson.loads(data.decode())
                assert obj is not None

                if url not in contextsCache and len(data) < 4096:
                    # Cache contexts <4kb
                    contextsCache[url] = obj

                return {
                    'contentType': 'application/ld+json',
                    'document': obj,
                    'documentUrl': url,
                    'contextUrl': None
                }
            else:
                raise ValueError(
                    f'Cannot determine the object path for '
                    f'ips schema URL: {url}'
                )
        except asyncio.TimeoutError as terr:
            log.debug(f'Timeout error while loading context: {terr}')
            raise terr
        except aioipfs.APIError as e:
            log.debug(f'IPFS error while loading context {url}: {e}')
            raise e
        except JsonLdError as e:
            log.debug(str(e))
            raise e
        except ValueError as verr:
            raise verr
        except Exception as cause:
            raise JsonLdError(
                'Could not retrieve a JSON-LD document from the URL.',
                'jsonld.LoadDocumentError', code='loading document failed',
                cause=cause)

    async def loader(url, options={}):
        """
        Retrieves JSON-LD at the given URL.

        :param url: the URL to retrieve.

        :return: the RemoteDocument.
        """

        return await async_loader(ipfsClient, url, options)

    return loader


async def aioipfs_ipns_document_loader(ipfsClient: aioipfs.AsyncIPFS,
                                       loop=None,
                                       secure=False, **kwargs):
    if loop is None:
        loop = asyncio.get_event_loop()

    async def async_loader(client, url, options={}):
        """
        :param url: the URL to retrieve.

        :return: the RemoteDocument.
        """
        try:
            o = urlparse(url)
            if o.scheme in ['ipschema', 'ips']:
                ipsKey = o.netloc

                if ipsKey == 'galacteek.ld.contexts':
                    # Compat
                    ipsKey = 'galacteek.ld'

                if not o.path or o.path == '/':
                    return {
                        'contentType': 'application/ld+json',
                        'document': {},
                        'documentUrl': url,
                        'contextUrl': None
                    }

                    raise JsonLdError(
                        f'Invalid context path for URL: {url}',
                        'jsonld.InvalidUrl', {'url': url},
                        code='loading document failed'
                    )

                kList = await client.key.list()

                ipnsKey = None
                for key in kList['Keys']:
                    if key['Name'] == ipsKey:
                        ipnsKey = key['Id']

                path = None if ipnsKey is None else IPFSPath(
                    joinIpns(ipnsKey)).child(o.path)
            else:
                path = IPFSPath(url)
                if not path.valid:
                    raise Exception(f'Not a valid path: {url}')

            if path and path.valid:
                data = await asyncio.wait_for(
                    client.cat(path.objPath), 10
                )

                obj = orjson.loads(data.decode())
                assert obj is not None

                return {
                    'contentType': 'application/ld+json',
                    'document': obj,
                    'documentUrl': url,
                    'contextUrl': None
                }
        except asyncio.TimeoutError as terr:
            log.debug(str(terr))
            raise terr
        except aioipfs.APIError as e:
            log.debug(str(e))
            raise e
        except JsonLdError as e:
            log.debug(str(e))
            raise e
        except Exception as cause:
            raise JsonLdError(
                'Could not retrieve a JSON-LD document from the URL.',
                'jsonld.LoadDocumentError', code='loading document failed',
                cause=cause)

    async def loader(url, options={}):
        """
        Retrieves JSON-LD at the given URL.

        :param url: the URL to retrieve.

        :return: the RemoteDocument.
        """

        return await async_loader(ipfsClient, url, options)

    return loader
