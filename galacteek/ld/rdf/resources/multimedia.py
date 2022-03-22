from rdflib import RDF
from rdflib import XSD
from rdflib import URIRef
from rdflib import Literal

from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ld import ipsTermUri as term

from . import IPR


class MusicRecordingOrVideoResource(IPR):
    @property
    def url(self):
        return self.value(term('url'))

    @property
    def ipfsPath(self):
        return IPFSPath(self.url, autoCidConv=True)

    @property
    def name(self):
        return self.value(term('name'))

    def setMediaType(self, mtype: URIRef):
        self.remove(RDF.type, None)
        self.add(RDF.type, mtype)

    def updateMetadata(self, key, value):
        # Qt metadata to RDF triples
        mapping = {
            'Title': 'name',
            'ContributingArtist': 'byArtist',
            'AlbumTitle': 'inAlbum',
            'Genre': 'genre',
            'Year': 'copyrightYear',
            'Duration': 'duration'
        }

        if key in mapping:
            try:
                if isinstance(value, int):
                    dtype = XSD.integer
                elif isinstance(value, str):
                    dtype = XSD.string
                else:
                    raise ValueError('Unhandled metadata type')

                self.replace(term(mapping[key]),
                             Literal(value, datatype=dtype))
            except Exception:
                pass


class MusicRecordingResource(MusicRecordingOrVideoResource):
    pass


class VideoObjectResource(MusicRecordingOrVideoResource):
    pass


class MultimediaPlaylistResource(IPR):
    @property
    def track(self):
        return list(self.objects(term('track')))

    @property
    def trackResource(self):
        return self.value(term('track'))

    @property
    def name(self):
        return self.value(term('name'))

    def addTrack(self, rsc):
        self.add(term('track'), rsc)
        self.remove(term('numTracks'), None)
        self.add(term('numTracks'), Literal(len(self.track)))

    def removeTrack(self, rsc):
        self.remove(term('track'), rsc)

        self.replace(term('numTracks'), Literal(len(self.track)))

    def findByPath(self, path: IPFSPath):
        for trsc in self.track:
            r = MusicRecordingOrVideoResource(
                self.graph, trsc.identifier)

            if r.ipfsPath and path == r.ipfsPath:
                return r
