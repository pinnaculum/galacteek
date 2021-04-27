from SPARQLBurger.SPARQLQueryBuilder import *

T = Triple


def select(vars=None, w=None, distinct=True, limit=10000):
    s = SPARQLSelectQuery(distinct=distinct, limit=limit)
    s.add_prefix(
        prefix=Prefix(
            prefix='gs', namespace='ips://galacteek.ld/')
    )

    if isinstance(vars, list):
        s.add_variables(vars)

    if w:
        s.set_where_pattern(graph_pattern=w)

    return s


def where(triples):
    wpattern = SPARQLGraphPattern()
    wpattern.add_triples(triples=triples)
    return wpattern


"""
SELECT DISTINCT ?type WHERE {
  [] a ?type
  FILTER( regex(str(?type), "^(?!http://dbpedia.org/class/yago/).+"))
}
ORDER BY ASC(?type)
LIMIT 10
"""


def uri_regex(ureg):
    return select(
        w=where([
            T(subject="[]", predicate="a", object="?type")
        ])
    )


def uri_objtype(uri):
    return select(
        vars=['?type'],
        w=where([
            T(subject=f'<{uri}>', predicate="a", object="?type")
        ])
    )


def uri_search(uri):
    return select(
        vars=['?p', '?o'],
        w=where([
            T(subject=f'<{uri}>', predicate="?p", object="?o")
        ])
    )
