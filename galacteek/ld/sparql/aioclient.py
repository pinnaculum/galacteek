import io
import orjson
from aiosparql.client import SPARQLClient
from rdflib.query import Result
from galacteek.ld.rdf import BaseGraph


class Sparkie(SPARQLClient):
    async def query(self, query: str, *args,
                    **keywords) -> dict:
        ctype = keywords.get('content_type', 'application/json')
        headers = {"Accept": ctype}
        full_query = self._prepare_query(query, *args, **keywords)

        if 0:
            print(
                "Sending SPARQL query to %s: \n%s\n%s",
                self.endpoint,
                self._pretty_print_query(full_query),
                "=" * 40,
            )

        async with self.session.post(
            self.endpoint, data={"query": full_query}, headers=headers
        ) as resp:
            await self._raise_for_status(resp)
            return await resp.json()

    async def queryGraph(self, query: str, *args,
                         **keywords) -> dict:
        try:
            j = await self.query(query, *args, **keywords)
            data = io.BytesIO()
            data.write(orjson.dumps(j))
            data.seek(0, 0)
        except Exception:
            return None
        else:
            graph = BaseGraph()
            results = Result.parse(data, format='json')
            graph.parse(
                data=results.serialize(format='xml').decode(),
                format='xml'
            )
            return graph
