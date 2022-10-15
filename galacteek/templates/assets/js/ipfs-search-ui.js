var lastInserted = null;
var mockImage = 'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='

function renderHit(engine, hit, ipfsGwUrl) {
    var hdiv = $('<div>', {
        id: hit.hash
    });

    var title = hit.title;

    const imimeCats = ['audio', 'video', 'image', 'video', 'text'];
    const embedVideoTypes = [
        'video/webm'
    ]
    var mimeIconPath = mockImage
    
    var mimeDash = hit.mimetype.replace("/", "-")
    var dirOpenerId = `${ hit.hash }_diropen_link`
    var mpOpenerId = `${ hit.hash }_mplayer_link`
    var videoId = `${ hit.hash }_video`
    var mimeCat = hit.mimetype.substr(0, hit.mimetype.lastIndexOf("\/"));

    var objectGwUrl = new URL(ipfsGwUrl);
    objectGwUrl.pathname = hit.path;

    if (imimeCats.includes(mimeCat)) {
        mimeIconPath = `qrc:/share/icons/mimetypes/${mimeCat}-x-generic.png`
    }

    if (title.length > 32) {
        title = title.substr(0, 32) + '...';
    }

    $(hdiv).append(`
        <p style="text-align: left" class="hitheader">
            <img src="qrc:/share/icons/${engine}.png"
                width="32" height="auto"
                title="Search engine: ${ engine }"/>

            <img
                src="${mimeIconPath}"
                width="32" height="auto"
                onerror="this.src='${ mockImage }'"
                title="${ hit.mimetype }" />

            <a class="hitlink" style="margin-right: 15px"
                 href="${hit.url}"
                 title="${hit.title}"
                 onclick='event.preventDefault();
                                    window.openIpfs("${hit.path}")' >
                    ${title}
            </a>

            <a href="#" title="Hashmark"
                onclick='event.preventDefault(); window.hashmark("${hit.path}")'>
                <img src="qrc:/share/icons/hashmarks.png" width="32" height="auto"/>
            </a>

            <a href="#" title="Pin object"
                onclick='event.preventDefault(); window.ipfssearch.pinObject("${hit.path }")'>
                <img src="qrc:/share/icons/pin/pin-diago-blue.png"
                    width="32" height="auto"/>
            </a>

            <a href="#" title="Copy address to clipboard"
                    onclick='event.preventDefault(); window.ipfssearch.clipboardInput("${hit.path}")'><img src="qrc:/share/icons/clipboard.png" width="32" height="auto"/>
            </a>

            <a style="display: none"
                 id="${dirOpenerId}"
                 href="#" onclick='event.preventDefault();
                                                     window.exploreIpfs("${hit.path}")'>
                <img src="qrc:///share/icons/folder-open-black.png"
                            width="32" height="auto"/>
            </a>

            <a href="#"
               id="${mpOpenerId}"
               style="display: none"
               title="Open in mediaplayer"
               onclick='event.preventDefault(); window.ipfssearch.mplayerQueue("${hit.path}")'>
                <img src="qrc:/share/icons/multimedia/mplayer1.png" width="32" height="auto" />
            </a>

            <span style="float: right; width: 30%">
                        Content type: <b>${ hit.mimetype }</b>
                        Size: <b>${ hit.sizeformatted }</b>
            </span>

        </p>
    `);

    if (hit.mimetype.startsWith('audio')) {
        $(hdiv).find("#" + mpOpenerId).css('display', 'inline-block');

        $(hdiv).append(`
            <audio controls="controls" src="${objectGwUrl}"
                Your browser does not support the HTML5 Audio element.
            </audio>
        `)
    }

    if (hit.mimetype.startsWith('video')) {
        $(hdiv).find("#" + mpOpenerId).css('display', 'inline-block');

        if (embedVideoTypes.includes(hit.mimetype)) {
            $(hdiv).find("#" + mpOpenerId).css('display', 'inline-block');

            $(hdiv).hover(function() {
                let videoel = document.getElementById(videoId);

                if (!videoel) {
                    $(hdiv).append(`
                        <video id="${videoId}"
                            width="25%"
                            height="auto"
                            controls="controls" src="${objectGwUrl}"
                            Your browser does not support the HTML5 Audio element.
                        </video>
                    `)
                }
            });
        }
    }

    if (hit.type == 'directory' || hit.mimetype == 'inode/directory') {
        $(hdiv).find("#" + dirOpenerId).css('display', 'inline-block');
    }

    if (hit.description) {
        $(hdiv).append(`
            <div id="${hit.hash}_description" class="hitdescr">
                ${hit.description}</p>
            </div>
        `);
    }

    if (hit.mimetype.startsWith('image')) {
        var imgUrl = new URL(ipfsGwUrl);
        imgUrl.pathname = hit.path;

        $(hdiv).append(`
            <a href="#"
                onclick='event.preventDefault(); window.openIpfs("${hit.path}")'>
                <img id="img"
                     src="${ imgUrl }"
                     onerror="this.src='qrc:/share/icons/unknown-file.png'"
                     width="15%">
                </img>
            </a>
        `);
    }

    if (hit.mimetype.startsWith('text')) {
        if (hit.mimetype === 'text/html') {
                $(hdiv).append(`
                    <button onclick="previewFile('${hit.hash}');">Preview</button>
                    <div id="${hit.hash}_preview" class="textpreview">
                        <embed type="text/html"
                            src="{{ ipfsConnParams.gatewayUrl }}/${hit.path}"
                            width="100%" height="300">
                    </div>
                `);
        } else {
            $(hdiv).append(`
                <button onclick="previewFile('${hit.hash}');">Preview</button>
                <div id="${hit.hash}_preview" class="textpreview">
                    <pre id="${hit.hash}_text"></pre>
                </div>
            `);
        }
    }

    $(function() {
        $(hdiv).on('click', function(event) {
                if (event.target.getAttribute('id') === hit.hash) {
                    window.openIpfs(hit.path);
                }
        });
    });

    return hdiv.get(0);
}

function previewFile(hash) {
    preview = document.getElementById(hash + "_preview")
    raw = document.getElementById(hash + "_text")
    fetched = document.getElementById(hash + "_fetched")

    if (!fetched) {
        window.ipfs.cat(hash, function (err, file) {
            if (!raw || err) {
                raw.innerHTML = 'IPFS fetch error'
                throw err
            } else {
                document.createElement("p", hash + "_fetched")
                raw.innerHTML = ''
                try {
                    var tNode = document.createTextNode(file.toString('utf8'))
                    raw.appendChild(tNode)
                } catch(err) {
                    raw.innerHTML = 'Decoding error'
                    throw err
                }
            }
        })
    }

    if (preview.style.display === 'none' || !(preview.style.display)) {
        preview.style.display = 'block'
    } else {
        preview.style.display = 'none'
    }
}

function statusSearching() {
        document.getElementById('searchquery').setAttribute(
            'class', 'searching')
}

function statusWaiting() {
        document.getElementById('searchquery').setAttribute(
            'class', 'waitinput')
}

new QWebChannel(qt.webChannelTransport, function (channel) {
    window.galacteek = channel.objects.galacteek;
    window.ipfssearch = channel.objects.ipfssearch;

    query = document.getElementById('searchquery')
    if (query) {
            query.focus()
    }

    window.ipfssearch.availableIpfsGateways.connect(function(gwUrlsList) {
        $('#gateway_selector').append(`
            <option value="{{ ipfsConnParams.gatewayUrl }}">Local gateway</option>
        `);

        gwUrlsList.forEach(function(gwUrl) {
            const url = new URL(gwUrl);
            $('#gateway_selector').append(`
            <option value="${ gwUrl }">${ url.host }</option>
            `);
        })
    })

    window.ipfssearch.availableMimeTypes.connect(function(mtypes) {
        $('#mimetype_selector').append(`
                <option value="*">*</option>
        `);

        mtypes.forEach(function(mtype) {
            $('#mimetype_selector').append(`
                <option value="${ mtype }">${ mtype }</option>
            `);
        })

        $(document).ready(function() {
            for (mp = 1; mp < 24; mp++) {
                var label;

                if (mp === 1) {
                    label = `${mp} month`
                } else {
                    label = `${mp} months`
                }
                $('#last-seen-period').append(`
                    <option value="${mp}M">${label}</option>
                `);
            }
            $('#last-seen-period option[value="3M"]').prop('selected', true);

            $('#mimetype_selector option[value="*"]').prop('selected', true);

            $('#mimetype_selector').change(function() {
                let value = $(this).val()

                if (value !== '*') {
                    $('#contenttype').prop('disabled', true);

                    $('#contenttype option[value="*"]').prop('selected', true);
                } else {
                    $('#contenttype').prop('disabled', false);
                }

                window.runSearch();
            });

            $('#contenttype').change(function() {
                window.runSearch();
            });
            $('#last-seen-period').change(function() {
                window.runSearch();
            });
        })
    })

    window.ipfssearch.filtersChanged.connect(function() {
        document.getElementById('results').innerHTML = ''
        channel.objects.ipfssearch.search()
    })

    window.ipfssearch.resultReady.connect(function(engine, cid, hit) {
        var insertIndex = 0;
        var resDiv = document.getElementById('results');
        var elem = document.createElement("div", cid);
        var gwUrlElement = document.getElementById('gateway_selector')

        elem.setAttribute('id', cid);
        elem.setAttribute('class', 'grayout');
        elem.setAttribute('data-score', hit.score);

        elem.style.display = 'none';

        // renderHit(engine, hit, elem);
        elem = renderHit(engine, hit, gwUrlElement.value)
        elem.setAttribute('data-score', hit.score);

        if (lastInserted !== null) {
                let prevScore = lastInserted.getAttribute('data-score');

                if (hit.score > prevScore) {
                        resDiv.insertBefore(elem, lastInserted);
                } else {
                        resDiv.insertBefore(elem, lastInserted.nextSibling);
                }
        } else {
                resDiv.insertBefore(elem, resDiv.children[insertIndex]);
        }

        lastInserted = elem;
    });

    window.ipfssearch.clear.connect(function() {
        var div = document.getElementById('results')
        while(div.firstChild){
            div.removeChild(div.firstChild);
        }
        lastInserted = null;
        document.getElementById('statusmessage').innerHTML = ""
    })

    window.ipfssearch.filesStatAvailable.connect(function(cid, stat) {
        var element = document.getElementById(cid)
        if (element) {
            element.style.display = 'block'
            element.setAttribute('class', 'hit')
        }
        document.getElementById('controls_b').style.display = 'flex'
    });

    window.ipfssearch.searchTimeout.connect(function(timeout) {
        $('#statusmessage').html(
            `<b>Search timeout</b>
            <a href="#" onclick="event.preventDefault();
                window.ipfssearch.searchRetry();">Retry</a>`
        );

        statusWaiting()
    })

    window.ipfssearch.searchError.connect(function() {
        $('#statusmessage').html(
            `<b>Search error !</b>
                <a href="#" onclick="event.preventDefault();
                    window.ipfssearch.searchRetry();">Retry</a>`
        );

        statusWaiting()
    })

    window.ipfssearch.searchComplete.connect(function() {
        statusWaiting()
    })

    window.ipfssearch.searchRunning.connect(function(query) {
        document.getElementById('searchquery').value = query
        statusSearching()
    })

    window.ipfssearch.searchStarted.connect(function(query) {
        document.getElementById('searchquery').value = query
        statusSearching()
    })

    window.ipfssearch.resetForm.connect(function() {
        document.getElementById('searchquery').value = ''
        document.getElementById('contenttype').value = 'all'
        document.getElementById('controls').style.display = 'none'
        document.getElementById('controls_b').style.display = 'none'
        document.getElementById('statusmessage').innerHTML = ""

        query = document.getElementById('searchquery')
        if (query) {
                query.focus()
        }
    })

    window.ipfssearch.vPageStatus.connect(function(vPageCur, vPageLast) {
        var ctrl = document.getElementById('controls')
        var ctrlb = document.getElementById('controls_b')
        var prev = document.getElementById('pageprev')
        var prevb = document.getElementById('pageprev_b')
        var next = document.getElementById('pagenext')
        var nextb = document.getElementById('pagenext_b')
        var pageinfo = document.getElementById('pageinfo')

        pageinfo.innerHTML = `Page ${vPageCur} / ${vPageLast}`
        pageinfo.style.display = 'block'

        ctrl.style.display = 'flex'

        if (vPageCur == 1) {
            prev.style.display = 'none'
            prevb.style.display = 'none'
        } else {
            prev.style.display = 'block'
            prevb.style.display = 'block'
        }
        if (vPageCur < vPageLast) {
            next.style.display = 'block'
            nextb.style.display = 'block'
        } else {
            next.style.display = 'none'
            nextb.style.display = 'none'
        }
    })
})

window.openIpfs = function (path) {
    window.ipfssearch.openLink(path);
}

window.hashmark = function (path) {
    window.ipfssearch.hashmark(path);
}

window.exploreIpfs = function (path) {
    window.ipfssearch.explore(path);
}

window.runSearch = function () {
    lastInserted = null;
    window.ipfssearch.cancelSearchTasks()

    document.getElementById('controls').style.display = 'none'
    document.getElementById('controls_b').style.display = 'none'

    query = document.getElementById('searchquery').value
    ctype = document.getElementById('contenttype').value
    mimeType = document.getElementById('mimetype_selector').value
    lastSeenPeriod = document.getElementById('last-seen-period').value

    window.ipfssearch.search(query, lastSeenPeriod, ctype, mimeType)
}

window.previousPage = function () {
    lastInserted = null;
    document.getElementById('controls_b').style.display = 'none'
    document.getElementById('controls').style.display = 'none'
    window.ipfssearch.previousPage()
}

window.nextPage = function () {
    lastInserted = null;
    document.getElementById('controls_b').style.display = 'none'
    document.getElementById('controls').style.display = 'none'
    window.ipfssearch.nextPage()
}
