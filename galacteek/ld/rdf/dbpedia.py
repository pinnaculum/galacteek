import traceback
from SPARQLWrapper import SPARQLWrapper, JSON


def requestJson(query: str):
    sparql = SPARQLWrapper("http://dbpedia.org/sparql")
    sparql.addDefaultGraph("http://dbpedia.org")
    sparql.setQuery(query)
    try:
        sparql.setReturnFormat(JSON)
        return sparql.query().convert()
    except Exception:
        traceback.print_exc()
