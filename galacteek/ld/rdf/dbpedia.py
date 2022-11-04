import asyncio
import traceback
from SPARQLWrapper import SPARQLWrapper, JSON

from galacteek.ld.sparql import querydb


def dbpediaConnector():
    wrapper = SPARQLWrapper("https://dbpedia.org/sparql")
    wrapper.addDefaultGraph("http://dbpedia.org")
    return wrapper


def requestJson(query: str):
    sparql = dbpediaConnector()
    sparql.setQuery(query)
    try:
        sparql.setReturnFormat(JSON)
        return sparql.query().convert()
    except Exception:
        traceback.print_exc()


async def requestGraph(rq: str, *args):
    loop = asyncio.get_event_loop()
    query = querydb.get(rq, *args)

    try:
        assert query is not None

        sparql = dbpediaConnector()
        sparql.setQuery(query)

        return await loop.run_in_executor(
            None,
            sparql.queryAndConvert
        )
    except AssertionError:
        pass
    except Exception:
        traceback.print_exc()
