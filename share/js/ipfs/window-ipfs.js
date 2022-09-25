window.ipfs = window.IpfsHttpClient({
    host: '@HOST@',
    port: @API_PORT@
});

const { fetch: legacyFetch } = window;

function tsIpfsPath(path) {
    let pcorr = path.replace('ipns://', '/ipns/');
    pcorr = pcorr.replace('ipfs://', '/ipfs/');
    pcorr = pcorr.replace('dweb:/ipfs/', '/ipfs/');
    pcorr = pcorr.replace('dweb:/ipns/', '/ipns/');
    pcorr = pcorr.replace('/#/', '/'); /* ? */
    return pcorr;
}

window.fetch = async (...args) => {
    /* Monkeypatch fetch() to get things from the IPFS gw */

    let [resource, config ] = args;
    var path = '';
    const headers = {};
    const fpRegex = /^[a-zA-Z\./]*[\s]?/;

    if (resource.startsWith('http')) {
        console.debug(
            `dweb-fetch: redirect to legacy fetch: ${ resource }`);

        return await legacyFetch(resource, config);
    }

    if (resource.startsWith('ens://')) {
        // TODO: assume it comes from /ipns/ for now
        // galacteek could set the resolved IPFS object in 'window' ..
        let href = resource.replace('ens://', '/ipns/');
        return await legacyFetch(tsIpfsPath(href), config);
    } else if (resource.startsWith('ipns://') ||
               resource.startsWith('ipfs://')) {
        /* dweb fetch */
        path = tsIpfsPath(resource);
    } else if ((window.location.protocol === 'ens:' ||
                window.location.protocol === 'ipns:' ||
                window.location.protocol === 'ipfs:') &&
                (resource.startsWith('.') || resource.match(fpRegex)) ) {
        /* Relative fetch */
        let href = window.location.href.replace('ens://', '/ipns/');
        path = tsIpfsPath(href).concat(resource);
    } else {
        return null
    }

    const objUrl = new URL('@GATEWAY_URL@');
    objUrl.pathname = path;

    console.debug(
      `dweb-fetch: Intercepted: ${ resource } (${ window.location.href })`);

    console.debug('dweb-fetch: Serving: ' + objUrl.toString())

    return await legacyFetch(objUrl.toString(), config);
};
