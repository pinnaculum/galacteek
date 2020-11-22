
const debug = console.log

function newRtcConnection() {
    var configuration = {
      offerToReceiveAudio: true,
      offerToReceiveVideo: true
    }

    const pc = new RTCPeerConnection({
      sdpSemantics: 'unified-plan',
      configuration: configuration,
      iceServers: [
        // { urls: 'stun:stun.l.google.com:19302'}
        { urls: 'stun:stun.stunprotocol.org:3478'}
      ]
    })

    // pc.addTransceiver('audio')
    // pc.addTransceiver('video')

    pc.addEventListener('track', function(evt) {
        console.log('Track event ' + evt.track.kind)

        if (evt.track.kind == 'video') {
            document.getElementById('remote_video').srcObject = evt.streams[0];
        } else {
            document.getElementById('remote_audio').srcObject = evt.streams[0];
        }
    });

    /*
    pc.ontrack = (evt) => {
      console.log('TRACK EVENT ' + evt.track.kind)

      remoteView = document.getElementById('video')

      if (evt.track.kind == 'video') {
          document.getElementById('video').srcObject = evt.streams[0];
      }
       else {
          document.getElementById('audio').srcObject = evt.streams[0];
      }
    };
    */

    return pc
}

function pcConnectTracks(pc) {
    pc.ontrack = (evt) => {
      console.log('TRACK EVENT ' + evt.track.kind)

      remoteView = document.getElementById('video')

      if (evt.track.kind == 'video') {
          document.getElementById('video').srcObject = evt.streams[0];
      }
       else {
          document.getElementById('audio').srcObject = evt.streams[0];
      }
    };
}


function rtcSetupVideo(pc) {
    constraints = {
        audio: true,
        video: true
    }

    navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
        window.localStream = stream

        stream.getTracks().forEach(function(track) {
            console.log('Adding track ' + track.kind)
            if (track.kind == 'video') {
                document.getElementById('local_video').srcObject = stream
            }

            pc.addTrack(track, stream);
        });
    })
}

function stopVideoAndAudio(stream) {
    stream.getTracks().forEach(function(track) {
        track.stop();
    });
}

function newIPFS(cb) {
    if (typeof(window.ipfs) != 'undefined') {
            debug('Using window.ipfs')
            cb(window.ipfs)
            return
    }

    const ipfs = new Ipfs({
        repo: String(Math.random() + Date.now()),
        EXPERIMENTAL: { pubsub: true },
        config: {
            Addresses: {
                Swarm: ['/dns4/ws-star.discovery.libp2p.io/tcp/443/wss/p2p-websocket-star']
            }
        }
    })

    // Wait for peers
    ipfs.on('ready', () => {
        const tryListPeers = () => {
            ipfs.swarm.peers((err, peers) => {
                if (err) throw err
                debug('Peers', peers)
                if (!peers || peers.length == 0) setTimeout(() => tryListPeers(), 1000)
                else cb(ipfs)
            })
        }
        tryListPeers()
    })
}

function ipfsDirBase() {
    return window.location.hash.substring(1)
}

function ipfsSubscribe(ipfs, handle, cb) {
    console.log('Subscribing to ' + ipfsDirBase())
    ipfs.pubsub.subscribe(
        ipfsDirBase(),
        // msg => handle(msg.data.toString('utf8')),
        msg => {
            console.log('PS ' + ipfsDirBase() + 'data is ' + msg.data)
            // handle(msg.data.toString('utf8'))
            handle(msg.data)
        },
        err => {
            if (err) {
                console.error('Failed subscribe', err)
                setTimeout(() => ipfsSubscribe(ipfs, handle, cb), 1000)
            }
            else {
                debug('Subscribe to ' + ipfsDirBase() + ' complete')
                cb()
            }
        })
}

function ipfsPublish(ipfs, data, cb) {
    ipfs.pubsub.publish(
        ipfsDirBase(),
        data,
        err => {
            if (err) console.error('Failed publish', err)
            else {
                debug('Publish complete')
                cb()
            }
        })
}

function setupChatChannel(channel) {
    const areaElem = document.getElementById('chattext')
    const messageElem = document.getElementById('message')

    channel.onclose = () => areaElem.value += "**system** chat closed\n"
    channel.onopen = () => {
        messageElem.disabled = false
        areaElem.value += "**system** chat started\n"
    }
    channel.onmessage = e => areaElem.value += '**them** ' + e.data + "\n"

    messageElem.onkeypress = e => {
        const message = messageElem.value
        if (e.keyCode == 13 && message) {
            messageElem.value = ''
            areaElem.value += '**me** ' + message + "\n"
            channel.send(message)
        }
    }
}
