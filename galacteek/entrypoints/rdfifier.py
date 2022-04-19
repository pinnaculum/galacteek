import traceback
import tarfile
import io
import time
from pathlib import Path

from rdflib import RDF

from galacteek import application

from galacteek import log
from galacteek.core import glogger
from galacteek.core.asynclib import asyncReadFile
from galacteek.core.asynclib import asyncWriteFile
from galacteek.guientrypoint import buildArgsParser
from galacteek.ld.iri import superUrn
from galacteek.ld import ipsContextUri
from galacteek.ld.rdf import BaseGraph
from galacteek.ld.rdf.util import literalDtNow
from galacteek.ld.rdf.terms import DATASET


async def rdfifyInput(app, ipfsop, args):
    outp = Path(args.ttloutpath)
    outg = BaseGraph()

    async with ipfsop.ldOps() as ld:
        for inputf in args.yamlldfiles:
            try:
                data = await asyncReadFile(inputf, mode='rt')
                if not data:
                    continue

                graph = await ld.rdfify(data)
                if graph is None:
                    log.debug(f'Impossible to rdfify: {inputf}')
                    continue

                ttl = await graph.ttlize()

                outg += graph
            except Exception:
                traceback.print_exc()
                continue

    subj = superUrn(
        'glk',
        'datasets',
        args.datasetname
    )

    outg.add((
        subj,
        RDF.type,
        ipsContextUri('Dataset')
    ))

    outg.add((
        subj,
        DATASET.dateAuthored,
        literalDtNow()
    ))

    ttl = await outg.ttlize()
    if not ttl:
        return None

    if outp.name.endswith('.tar.gz'):
        tar = tarfile.open(str(outp), mode='w:gz')
        ttlf = io.BytesIO(ttl)

        info = tarfile.TarInfo(f'dataset/{args.datasetname}.ttl')
        info.mtime = time.time()
        info.size = len(ttl)
        info.gid = 1000
        info.uid = 1000
        info.uname = 'galacteek'
        info.gname = 'galacteek'

        tar.addfile(info, fileobj=ttlf)
        tar.close()
    if outp.name.endswith('.ttl'):
        await asyncWriteFile(str(outp), ttl, mode='w+b')


async def run(app, args):
    try:
        ipfsop = app.ipfsOperatorForLoop()
        await app.ldSchemas.update(ipfsop)
    except Exception:
        traceback.print_exc()
    else:
        await rdfifyInput(app, ipfsop, args)

    await app.exitApp()


def rdfifier():
    t = int(time.time())
    parser = buildArgsParser()
    parser.add_argument(
        nargs='+',
        dest='yamlldfiles'
    )
    parser.add_argument(
        '--ttl-output',
        dest='ttloutpath'
    )

    parser.add_argument(
        '--dataset-name',
        dest='datasetname',
        default=f'dataset-{t}'
    )

    parser.add_argument(
        '--dataset-uri',
        dest='dataseturi',
        default=f'urn:glk:datasets:{t}'
    )

    args = parser.parse_args()

    app = application.GalacteekApplication(
        profile='rdfifier',
        debug=True,
        cmdArgs=args
    )
    app.configure(full=False)

    if args.debug:
        glogger.basicConfig(level='DEBUG', colorized=args.logcolorized,
                            loop=app.loop)

    with app.loop as loop:
        loop.run_until_complete(run(app, args))
