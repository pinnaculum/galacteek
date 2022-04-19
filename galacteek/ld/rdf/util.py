from rdflib import XSD
from rdflib import Literal

from galacteek.core import normalizedUtcDate


def literalDtNow():
    return Literal(normalizedUtcDate(), datatype=XSD.dateTime)
