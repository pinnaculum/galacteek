import traceback
import tarfile
import io
import time
import hashlib
import os
from pathlib import Path

from rdflib import RDF
from rdflib import Literal

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
    outp = Path(args.outpath)
    outg = BaseGraph()

    async def yamlLdProcess(fullp: Path):
        fullp = Path(root).joinpath(inputf)

        log.debug(f'Processing {inputf}')
        try:
            data = await asyncReadFile(str(fullp), mode='rt')
            if not data:
                log.debug(f'Cannot read {inputf}')
                return

            graph = await ld.rdfify(data)
            if graph is None:
                log.debug(f'Impossible to rdfify: {inputf}')
                return

            log.debug(f'{inputf}: built graph size: {len(graph)}')
            return graph
        except Exception:
            traceback.print_exc()

    async with ipfsop.ldOps() as ld:
        for path in args.yldpaths:
            for root, dirs, files in os.walk(path):
                for inputf in files:
                    fullp = Path(root).joinpath(inputf)

                    if inputf.endswith('yaml-ld'):
                        graph = await yamlLdProcess(fullp)
                    elif inputf.endswith('.nt') or \
                            inputf.endswith('.ttl'):
                        try:
                            graph = BaseGraph()
                            graph.parse(str(fullp))
                        except Exception:
                            traceback.print_exc()

                    if graph:
                        outg += graph

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

    outg.add((
        subj,
        DATASET.revision,
        Literal(args.datasetrev)
    ))

    nt = await outg.ntize()
    if not nt:
        return None

    if outp.name.endswith('.tar.gz'):
        h = hashlib.sha512()
        revfp = f'{outp}.dsrev'
        digestfp = f'{outp}.sha512'

        tar = tarfile.open(str(outp), mode='w:gz')
        ntf = io.BytesIO(nt)

        info = tarfile.TarInfo(f'dataset/{args.datasetname}.nt')
        info.mtime = time.time()
        info.size = len(nt)
        info.gid = 1000
        info.uid = 1000
        info.uname = 'galacteek'
        info.gname = 'galacteek'

        tar.addfile(info, fileobj=ntf)
        tar.close()

        with open(str(outp), 'rb') as fd:
            h.update(fd.read())

        with open(digestfp, 'w+t') as dfd:
            dfd.write(h.hexdigest())

        with open(revfp, 'w+t') as revfd:
            revfd.write(str(args.datasetrev))

    elif outp.name.endswith('.ttl'):
        await asyncWriteFile(str(outp), await outg.ttlize(),
                             mode='w+b')


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
        dest='yldpaths'
    )
    parser.add_argument(
        '--output',
        dest='outpath'
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
    parser.add_argument(
        '--dataset-revision',
        dest='datasetrev',
        default=str(t)
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
