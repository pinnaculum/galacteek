(function() {
    function notifySetupComplete() {
        if (!window._webchannel_initialized) {
            var event = document.createEvent('Event');
            event.initEvent('_webchannel_setup', true, true);
            window._webchannel_initialized = true;
            document.dispatchEvent(event);
        }
    }

    function setupWebChannel() {
        new QWebChannel(qt.webChannelTransport, function(channel) {
            const galacteek = {};
            galacteek.dombridge = channel.objects.dombridge;
            window.galacteek = galacteek; 
            notifySetupComplete();
        });
    }

    function attemptSetup() {
        try {
            setupWebChannel();
        } catch (e) {
            setTimeout(attemptSetup, 100);    
        }
    }

    function onMessage(event) {
        try {
            var msgData = event.data;
            if (msgData._galacteek_webchannel_msg !== true)
                return;

            var channelObj = window.galacteek[msgData._galacteek_webchannel_obj];
            if (!channelObj || typeof(channelObj[msgData._galacteek_webchannel_fn]) != 'function')
                return;

            channelObj[msgData._galacteek_webchannel_fn].apply(channelObj, msgData._galacteek_webchannel_args);
        } catch(ex) {
            console.error('Caught exception while handling message to webchannel by subframe: ' + ex);
        }
    }

    try {
        if (self !== top) {
            if (top._webchannel_initialized) {
                window.galacteek = top.galacteek;
                notifySetupComplete();
            } else {
                top.document.addEventListener('_webchannel_setup', function() {
                    window.galacteek = top.galacteek;
                    notifySetupComplete();
                });
            }
        } else {
            attemptSetup();
            window.addEventListener('message', onMessage, false);
        }
    } catch (e){
    }
})();
