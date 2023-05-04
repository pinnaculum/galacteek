
from pathlib import Path
from galacteek import log
from galacteek.core import pkgResourcesRscFilename


def get(name: str, *args) -> str:
    """
    Get a SparQL query (as string) from an .rq file stored
    inside this module

    :param str name: Name of the query to retrieve (without the .rq suffix)
    :rtype: str
    """

    try:
        filep = Path(
            pkgResourcesRscFilename(__name__, f'{name}.rq')
        )

        assert filep.is_file()

        with open(filep, 'rt') as fd:
            if len(args) > 0:
                return fd.read() % args

            return fd.read()
    except Exception as err:
        log.warning(f'rq rqGET: {name} error: {err}')

        # Raise (callers need to always use a rq in the db)
        raise err


__all__ = ['get']
