import multihash

from galacteek.ipfs.cidhelpers import IPFSPath
from galacteek.ipfs.cidhelpers import cidValid
from galacteek.ipfs.cidhelpers import getCID


class TestCIDs:
    def test_cids(self):
        assert cidValid('bafkriqa2hf4uwu2dd2nlynbwr3kietn2ywowyzaxperhtmhmfsi5n22yv5zptvfr4o3bhicyshbmdil2qif47au4wmr4ikm3egpfvmuzpfcyc')
        assert cidValid('bafkreihszin3nr7ja7ig3l7enb7fph6oo2zx4tutw5qfaiw2kltmzqtp2i')
        assert cidValid('bafkrgqaohz2sgsv4nd2dpcugwp2lgkqzrorqdbc3btlokaig5b2divyazrtghkdmd2qslxc6sk7bpsmptihylsu5l5mv3mqbf56mgvyzixasg')
        assert cidValid('bafkr2qffyprvhimferhyfkg6af63marfiplxn6euhncxwy3izaefj3g73ilqlzo5kfgvbbyrnwwmw7nm4wwufkyxfp7htiwabn5b5hdw4rvvk')
        p = IPFSPath('bafkr2qffyprvhimferhyfkg6af63marfiplxn6euhncxwy3izaefj3g73ilqlzo5kfgvbbyrnwwmw7nm4wwufkyxfp7htiwabn5b5hdw4rvvk')
        assert p.valid

        p = IPFSPath('bafk4bzacia2aon3c3n5pkaemoij7sm4q4dt3omcr5tkc2sptmm6ifsnpbsx7h77xj4e4pjx7olxtbgsyjsg35mgl3j2q7mel3kuiz2v7ztngkdbv')
        assert p.valid

        p = IPFSPath('/ipfs/bafykbzaced4xstofs4tc5q4irede6uzaz3qzcdvcb2eedxgfakzwdyjnxgohq/')
        assert p.valid

        cid = getCID('bafykbzaced4xstofs4tc5q4irede6uzaz3qzcdvcb2eedxgfakzwdyjnxgohq')
        m = multihash.decode(cid.multihash)
        assert m.name == 'blake2b-256'
