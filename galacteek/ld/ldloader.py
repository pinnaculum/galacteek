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


async def contextLoad(client, url: str):
    try:
        o = urlparse(url)
        if o.scheme in ['ipschema', 'ips']:
            if not o.path or o.path == '/':
                return None, None

            kList = await keysList(client)
            assert kList is not None

            ipnsKey = None
            for key in kList['Keys']:
                if key['Name'] == o.netloc:
                    ipnsKey = key['Id']

            path = None if ipnsKey is None else IPFSPath(
                joinIpns(ipnsKey)).child(o.path)
        else:
            path = IPFSPath(url)
            if not path.valid:
                raise Exception('Not a valid path')

        if path and path.valid:
            data = await asyncio.wait_for(
                client.cat(path.objPath), 10
            )
            obj = orjson.loads(data.decode())
            assert obj is not None

            return path, obj
    except asyncio.TimeoutError as terr:
        log.debug(str(terr))
        return None, None
    except aioipfs.APIError as e:
        return None, None
        log.debug(str(e))
    except JsonLdError as e:
        log.debug(str(e))
        raise e


async def aioipfs_document_loader(ipfsClient: aioipfs.AsyncIPFS,
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
                    if key['Name'] == o.netloc:
                        ipnsKey = key['Id']

                path = None if ipnsKey is None else IPFSPath(
                    joinIpns(ipnsKey)).child(o.path)
            else:
                path = IPFSPath(url)
                if not path.valid:
                    raise Exception('Not a valid path')

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
