
import multiprocessing
import subprocess
import os, os.path
import json
import signal
import asyncio

from yarl import URL

def ipfs_config(param, value):
    os.system("ipfs config '{0}' '{1}'".format(param, value))

def ipfs_config_json(param, value):
    os.system('ipfs config --json "{0}" "{1}"'.format(
        param, json.dumps(value)))

DEFAULT_APIPORT = 5001
DEFAULT_SWARMPORT = 4001
DEFAULT_GWPORT = 8080

class IPFSMultiDaemon(multiprocessing.Process):
    """ Runs an IPFS daemon in a separate multiprocessing.Process """

    def __init__(self, repopath, apiport=DEFAULT_APIPORT,
            swarmport=DEFAULT_SWARMPORT,
            gatewayport=DEFAULT_GWPORT, initrepo=True,
            swarm_lowwater=30, swarm_highwater=50,
            queue=None):

        if not queue:
            queue = multiprocessing.Queue()

        self.repopath = repopath
        self.apiport = apiport
        self.gatewayport = gatewayport
        self.swarmport = swarmport
        self.swarm_lowwater = swarm_lowwater
        self.swarm_highwater = swarm_highwater
        self.initrepo = initrepo

        self.proc_pid = None
        self.queue = queue

        multiprocessing.Process.__init__(self)

    def run(self):
        # Sets the IPFS_PATH environment variable
        os.putenv('IPFS_PATH', self.repopath)
        if not os.path.isdir(self.repopath):
            os.mkdir(self.repopath)

        if not os.path.exists(os.path.join(self.repopath, 'config')):
            os.system('ipfs init')

        # Change the ports we listen on
        ipfs_config('Addresses.API',
                '/ip4/127.0.0.1/tcp/{0}'.format(self.apiport))
        ipfs_config('Addresses.Gateway',
                '/ip4/127.0.0.1/tcp/{0}'.format(self.gatewayport))
        ipfs_config_json('Addresses.Swarm',
                '["/ip4/0.0.0.0/tcp/{0}"]'.format(self.swarmport))

        # Swarm connection manager parameters
        ipfs_config_json('Swarm.ConnMgr.LowWater', self.swarm_lowwater)
        ipfs_config_json('Swarm.ConnMgr.HighWater', self.swarm_highwater)

        # Runs the go-ipfs daemon with pubsub activated
        self.sp = subprocess.Popen(['ipfs', 'daemon',
            '--enable-pubsub-experiment'],
             stdout=subprocess.PIPE,
             stderr=subprocess.PIPE)

        self.proc_pid = self.sp.pid
        self.queue.put(('Running', self.proc_pid))
        #(stdout, stderr)  = self.sp.communicate()

        for j in self.queue.get():
            if j == 'S':
                self.sp.terminate()
                self.queue.put('STOPPED')

    def getGatewayPort(self):
        return self.gatewayport

    def getGatewayUrl(self):
        return URL.build(
                host='localhost',
                port=self.getGatewayPort(),
                scheme='http',
                path='')

    def stop(self):
        self.queue.put('S')
        stopped = self.queue.get()

    def killproc(self):
        if self.proc_pid:
            try:
                os.kill(self.proc_pid, signal.SIGINT)
            except Exception as e:
                print('Could not stop the ipfs daemon', file=sys.stderr)
