import orjson
import aioipfs

from galacteek.core.asynclib import async_enterable
from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ld.ldloader import aioipfs_document_loader
from galacteek.ld import asyncjsonld as jsonld


class LDOpsContext(object):
    def __init__(self, operator, ldDocLoader):
        self.operator = operator
        self.ldLoader = ldDocLoader

    async def __aenter__(self):
        return self

    async def expandDocument(self, doc):
        """
        Perform a JSON-LD expansion on a JSON document
        """

        try:
            expanded = await jsonld.expand(
                await self.operator.ldInline(doc), {
                    'documentLoader': self.ldLoader
                }
            )

            if isinstance(expanded, list) and len(expanded) > 0:
                return expanded[0]
        except jsonld.SyntaxError as serr:
            self.operator.debug(f'JSON-LD syntax error: {serr}')
            raise serr
        except Exception as err:
            self.operator.debug('Error expanding document: {}'.format(
                str(err)))

    async def expandDagAggressive(self, ipfsPath: IPFSPath):
        """
        Aggressive expansion

        This is not a regular IPLD+JSON-LD expansion (hell no)

        The difference is that it allows JSON-LD contexts
        (the @object key) to be referenced as interplanetary
        schema URLS:

            ips://galacteek.ld.contexts/dweb/DwebBlogPost

        galacteek.ld.contexts is the name of the IPNS key pointing
        to the UnixFS folder containing the JSON-LD contexts.

        When the expander finds such a reference, it will fetch
        the context from the IPS catalog.

        Expand a DAG using its @context
        """
        try:
            dag = await self.operator.dagGet(str(ipfsPath))

            self.operator.debug(f'EXPANDING: {dag}')

            expanded = await jsonld.expand(
                await self.operator.ldInline(dag), {
                    'documentLoader': self.ldLoader
                }
            )

            if 0:
                expanded = await jsonld.expand(dag, {
                    'documentLoader': self.ldLoader
                })

            # if isinstance(expanded, list) and len(expanded) > 0:
            if not isinstance(expanded, list):
                raise Exception('Empty expand')
        except Exception as err:
            self.operator.debug(f'Error expanding : {err}')
            raise err
        except aioipfs.APIError as err:
            self.operator.debug(f'IPFS error expanding : {err.message}')
            raise err
        else:
            return expanded

    async def __aexit__(self, *args):
        pass


class LinkedDataOps(object):
    @ async_enterable
    async def ldOps(self):
        if not self._ldDocLoader:
            self._ldDocLoader = await aioipfs_document_loader(self.client)

        return LDOpsContext(
            self,
            self._ldDocLoader
        )

    async def ldInline(self, dagData):
        # In-line the JSON-LD contexts for JSON-LD usage
        #
        # XXX: FFS this is almost certainly wrong

        async def processDict(data):
            link = data.get('/')
            if isinstance(link, str) and cidValid(link):
                try:
                    ctx = await self.client.cat(link)
                    if ctx:
                        data.update(orjson.loads(ctx.decode()))
                except Exception as err:
                    self.debug('ldInline error: {}'.format(
                        str(err)))
            else:
                for key, val in data.items():
                    print('Pdict', key, val)

        async def process(data):
            if isinstance(data, dict):
                for objKey, objValue in data.copy().items():
                    if objKey == '@context' and isinstance(objValue, dict):
                        await processDict(objValue)

                        if 0:
                            link = objValue.get('/')
                            if not isinstance(link, str) or not cidValid(link):
                                continue

                            try:
                                ctx = await self.client.cat(link)
                                if ctx:
                                    data.update(orjson.loads(ctx.decode()))
                            except Exception as err:
                                self.debug('ldInline error: {}'.format(
                                    str(err)))
                    else:
                        await process(objValue)
            elif isinstance(data, list):
                for node in data:
                    await process(node)

            return data

        return await process(dagData)

    async def ldContext(self, cName: str, source=None,
                        key=None):
        specPath = os.path.join(
            ldContextsRootPath(),
            '{context}'.format(
                context=cName
            )
        )

        if not os.path.isfile(specPath):
            return None

        try:
            with open(specPath, 'r') as fd:
                data = fd.read()

            entry = await self.addString(data)
        except Exception as err:
            self.debug(str(err))
        else:
            return self.ipld(entry)

    async def ldContextJson(self, cName: str):
        specPath = os.path.join(
            ldContextsRootPath(),
            '{context}'.format(
                context=cName
            )
        )

        if not os.path.isfile(specPath):
            return None

        try:
            data = await asyncReadFile(specPath, mode='rt')
            return orjson.loads(data)
        except Exception as err:
            self.debug(str(err))


