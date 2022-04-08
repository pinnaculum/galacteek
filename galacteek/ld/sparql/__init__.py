from SPARQLBurger.SPARQLQueryBuilder import *

T = Triple


def select(vars=None, w=None, distinct=True, limit=10000,
           commonPrefixes=True):
    s = SPARQLSelectQuery(distinct=distinct, limit=limit)
    s.add_prefix(
        prefix=Prefix(
            prefix='gs', namespace='ips://galacteek.ld/')
    )

    if commonPrefixes:
        s.add_prefix(
            prefix=Prefix(
                prefix='sec',
                namespace='https://w3id.org/security#'
            )
        )

        s.add_prefix(
            prefix=Prefix(
                prefix='ontoloChain',
                namespace='ips://galacteek.ld/OntoloChain#'
            )
        )

        s.add_prefix(
            prefix=Prefix(
                prefix='ontoloChainRecord',
                namespace='ips://galacteek.ld/OntoloChainRecord#'
            )
        )

        s.add_prefix(
            prefix=Prefix(
                prefix='dc',
                namespace='http://purl.org/dc/terms/'
            )
        )

        s.add_prefix(
            prefix=Prefix(
                prefix='didv',
                namespace='https://w3id.org/did#'
            )
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
