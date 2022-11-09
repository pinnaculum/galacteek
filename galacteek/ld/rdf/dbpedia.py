import asyncio
import traceback
from urllib.error import HTTPError

from SPARQLWrapper import SPARQLWrapper
from SPARQLWrapper import SPARQLWrapper2
from SPARQLWrapper import JSON
from SPARQLWrapper.SPARQLExceptions import EndPointInternalError

from galacteek.ld.sparql import querydb


def dbpediaConnector(wrapper=SPARQLWrapper):
    wrapper = wrapper("https://dbpedia.org/sparql")
    wrapper.addDefaultGraph("http://dbpedia.org")
    return wrapper


def wikidataConnector(wrapper=SPARQLWrapper):
    return wrapper('https://query.wikidata.org/sparql')


def requestJson(query: str):
    sparql = dbpediaConnector()
    sparql.setQuery(query)
    try:
        sparql.setReturnFormat(JSON)
        return sparql.query().convert()
    except Exception:
        traceback.print_exc()


async def request(rq: str, *args,
                  returnFormat='graph',
                  db='dbpedia'):
    loop = asyncio.get_event_loop()
    query = querydb.get(rq, *args)

    try:
        assert query is not None
        w = SPARQLWrapper2 if returnFormat == 'json' else SPARQLWrapper

        if db == 'dbpedia':
            sparql = dbpediaConnector(wrapper=w)
        elif db == 'wikidata':
            sparql = wikidataConnector(wrapper=w)

        sparql.setQuery(query)

        if returnFormat == 'json':
            sparql.setReturnFormat(JSON)

        return await loop.run_in_executor(
            None,
            sparql.query if returnFormat == 'json' else sparql.queryAndConvert
        )
    except AssertionError:
        pass
    except asyncio.CancelledError:
        pass
    except HTTPError as err:
        # TODO: raise a custom exception here and handle 429
        raise err
    except EndPointInternalError:
        raise
    except Exception:
        traceback.print_exc()
