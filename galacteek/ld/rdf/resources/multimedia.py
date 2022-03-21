from rdflib import Literal
from rdflib.resource import Resource

from galacteek.ipfs.cidhelpers import IPFSPath

from galacteek.ld import ipsTermUri as term


class MusicRecordingOrVideoResource(Resource):
    @property
    def url(self):
        return self.value(term('url'))

    @property
    def ipfsPath(self):
        return IPFSPath(self.url, autoCidConv=True)

    @property
    def name(self):
        return self.value(term('name'))

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
                self.remove(term(mapping[key]))
                self.add(term(mapping[key]), Literal(value))
            except Exception:
                pass


class MusicRecordingResource(MusicRecordingOrVideoResource):
    pass


class VideoObjectResource(MusicRecordingOrVideoResource):
    pass


class MultimediaPlaylistResource(Resource):
    @property
    def track(self):
        return list(self.objects(term('track')))

    @property
    def trackResource(self):
        return self.value(p=term('track'))

    @property
    def name(self):
        return self.value(term('name'))

    def addTrack(self, rsc):
        self.add(term('track'), rsc)
        self.remove(term('numTracks'), None)
        self.add(term('numTracks'), Literal(len(self.track)))

    def removeTrack(self, rsc):
        self.remove(term('track'), rsc)

        self.remove(term('numTracks'), None)
        self.add(term('numTracks'), Literal(len(self.track)))

    def findByPath(self, path: IPFSPath):
        for trsc in self.track:
            r = MusicRecordingOrVideoResource(
                self.graph, trsc.identifier)

            if r.ipfsPath and path == r.ipfsPath:
                return r
