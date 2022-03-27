from aiosparql.client import SPARQLClient
from aiosparql.client import SPARQLRequestFailed

from galacteek import log
from galacteek.ld.rdf import BaseGraph


class Sparkie(SPARQLClient):
    async def query(self, query: str, *args,
                    **keywords) -> dict:
        ctype = keywords.get('content_type', 'application/json')
        headers = {"Accept": ctype}
        full_query = self._prepare_query(query, *args, **keywords)

        try:
            async with self.session.post(
                self.endpoint, data={"query": full_query}, headers=headers
            ) as resp:
                await self._raise_for_status(resp)

                if ctype == 'application/json':
                    return await resp.json()
                else:
                    return await resp.read()
        except SPARQLRequestFailed as rerr:
            log.debug(f'{self.endpoint}: Request failed: {rerr}')
        except Exception as err:
            log.debug(f'{self.endpoint}: unknown error: {err}')

    async def qBindings(self, query: str, *args,
                        **keywords) -> dict:
        try:
            reply = await self.query(query, *args, **keywords)
            assert reply is not None

            for res in reply['results']['bindings']:
                yield res
        except Exception as err:
            log.debug(f'qBindings error: {err}')

    async def queryConstructGraph(self, query: str, *args,
                                  **keywords) -> dict:
        """
        Run a CONSTRUCT query and get an rdflib Graph as result
        """

        keywords.update(content_type='text/turtle')

        try:
            data = await self.query(query, *args, **keywords)
            assert data is not None

            graph = BaseGraph()
            graph.parse(data=data, format='ttl')
        except Exception as err:
            log.debug(f'queryGraph error: {err}')
        else:
            return graph
