from rdflib import XSD
from rdflib import Literal

from galacteek.core import utcDatetimeIso


def literalDtNow():
    return Literal(utcDatetimeIso(), datatype=XSD.dateTime)
