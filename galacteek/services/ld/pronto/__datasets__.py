import asyncio
import tarfile
import traceback

from pathlib import Path
from rdflib import URIRef

from yarl import URL

from galacteek import log

from galacteek.core.asynclib import asyncReadFile
from galacteek.core.asynclib.fetch import assetFetch
from galacteek.core.asynclib.fetch import httpFetch

from galacteek.ld.rdf import BaseGraph

from galacteek.ld.rdf.terms import DATASET


class ProntoDataSetsManagerMixin:
    async def graphDataSetPullTask(self,
                                   graph,
                                   opSubject: URIRef,
                                   url: URL,
                                   checksumUrl: URL,
                                   revisionUrl: URL,
                                   upgradeStrategy: str = 'mergeReplace',
                                   format=None):
        sleepMain = 60 * 10
        sleepAlreadyDone = 60 * 20
        sleepAfterUpdate = 60 * 5
        sleepInvalidDs = 60 * 10
        sleepCannotFetch = 60 * 5

        async def dsTarProcess(ograph, tarfp: Path):
            lastRevision = ograph.value(
                subject=opSubject,
                predicate=DATASET.revision
            )

            try:
                tar = tarfile.open(str(tarfp))
                names = tar.getnames()
                g = BaseGraph()

                for name in names:
                    if not name.endswith('.nt'):
                        continue

                    try:
                        file = tar.extractfile(name)
                        g.parse(file)
                    except Exception as err:
                        log.debug(f'dsProcess: {name} failed: {err}')
                        continue

                assert len(g) > 0

                tar.close()

                thisRevision = g.value(
                    subject=opSubject,
                    predicate=DATASET.revision
                )

                if lastRevision and thisRevision == lastRevision:
                    log.debug(f'Dataset {opSubject}: same revision')
                    return False

                if upgradeStrategy in ['mergeReplace', 'replace']:
                    await ograph.guardian.mergeReplace(
                        g,
                        ograph
                    )
                elif upgradeStrategy in ['mergeForward', 'forward']:
                    await ograph.guardian.mergeForward(
                        g,
                        ograph
                    )
                elif upgradeStrategy in ['purge', 'purgefirst']:
                    for s, p, o in ograph:
                        ograph.remove((s, p, o))

                    await ograph.guardian.mergeReplace(
                        g,
                        ograph
                    )

                ograph.add((
                    opSubject,
                    DATASET.processedRevision,
                    thisRevision
                ))

                ograph.commit()
            except asyncio.CancelledError:
                pass
            except Exception:
                log.warning(traceback.format_exc())
            else:
                log.info(
                    f'Dataset {opSubject}: upgraded to '
                    f'revision: {thisRevision}'
                )
                return True

        while not self.should_stop:
            fp = None

            try:
                checksum = None
                remoteRev = None

                lastProcessedRev = graph.value(
                    subject=opSubject,
                    predicate=DATASET.processedRevision
                )

                if revisionUrl:
                    rfp, _s = await httpFetch(revisionUrl)
                    if rfp:
                        contents = await asyncReadFile(
                            str(rfp), mode='rt')
                        if contents:
                            remoteRev = contents.split()[0]

                        rfp.unlink()

                if lastProcessedRev and remoteRev == str(lastProcessedRev):
                    # Already processed
                    log.debug(f'Dataset {url}: already processed '
                              f'revision: {remoteRev}')

                    await asyncio.sleep(sleepAlreadyDone)
                    continue

                if checksumUrl:
                    cfp, _s = await httpFetch(checksumUrl)
                    if cfp:
                        contents = await asyncReadFile(
                            str(cfp), mode='rt')
                        if contents:
                            checksum = contents.split()[0]

                        cfp.unlink()

                # Use assetFetch (will pull from IPFS if the redirection
                # points to an IPFS file)
                fp, _sum = await assetFetch(url)
                if not fp:
                    log.warning(f'Dataset {url}: failed to retrieve')
                    await asyncio.sleep(sleepCannotFetch)
                    continue

                if checksumUrl and _sum != checksum:
                    log.warning(f'Dataset {url}: checksum mismatch!')
                    await asyncio.sleep(sleepInvalidDs)
                    continue

                if fp.name.endswith('.tar.gz'):
                    if await dsTarProcess(graph, fp):
                        if fp and fp.is_file():
                            fp.unlink()

                        await asyncio.sleep(sleepAfterUpdate)
                else:
                    log.debug('Unsupported dataset format')
                    await asyncio.sleep(60)
                    continue
            except asyncio.CancelledError:
                pass
            except Exception:
                traceback.print_exc()

                if fp and fp.is_file():
                    fp.unlink()

            await asyncio.sleep(sleepMain)
