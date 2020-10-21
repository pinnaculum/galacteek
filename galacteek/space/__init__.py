from .solarsystem import SolarSystem
from .its42 import Planets42


def allPlanetsNames():
    for p in SolarSystem().planetsNames + Planets42().planetsNames:
        yield p
