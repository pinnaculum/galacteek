const { fetch: legacyFetch } = window;

function tsIpfsPath(path) {
    let pcorr = path.replace('ipns://', '/ipns/');
    pcorr = pcorr.replace('ipfs://', '/ipfs/');
    pcorr = pcorr.replace('dweb:/ipfs/', '/ipfs/');
    pcorr = pcorr.replace('dweb:/ipns/', '/ipns/');

    /* :| */
    pcorr = pcorr.replace('ens://', '/ipns/');

    return pcorr;
}

window.fetch = async (...args) => {
    /* Monkeypatch fetch() to get stuff from the IPFS gw */

    let [rsc_param, config] = args;
    var resource;
    var path;
    var tsUrl;

    const headers = {};
    const fpRegex = /^[a-zA-Z\./]*[\s]?/;

    if (typeof rsc_param === 'object') {
        if (rsc_param.constructor.name === 'Request') {
            /* Request */
            resource = rsc_param.url.toString();
        }
    } else {
      resource = rsc_param;
    }

    console.debug(
        `dweb-fetch: requested: ${ resource }`);

    if (resource.startsWith('http://') ||
        resource.startsWith('https://')) {
        hUrl = new URL(resource);

        if (hUrl.pathname.match(/ipfs/) ||
            hUrl.pathname.match(/ipns/)) {
          const replUrl = new URL('@GATEWAY_URL@');
          replUrl.pathname = hUrl.pathname;
          console.debug(
              `dweb-fetch: redirect to translated: ${ replUrl }`);
          return await legacyFetch(tsIpfsPath(replUrl.toString(), config));
        } else {
          console.debug(
              `dweb-fetch: redirect to legacy fetch: ${ resource }`);

          return await legacyFetch(resource, config);
        }
    }

    if (resource.startsWith('ipns://') ||
               resource.startsWith('ipfs://')) {
        /* dweb fetch */
        path = tsIpfsPath(resource);
    } else if ((window.location.protocol === 'ens:' ||
                window.location.protocol === 'dweb:' ||
                window.location.protocol === 'ipns:' ||
                window.location.protocol === 'ipfs:')) {
        /* dweb fetch */
        
        if (resource.startsWith('/')) {
          /* Relative to root location */

          tsUrl = new URL(window.location);

          tsUrl.hash = ''; /* Purge fragment */
          tsUrl.pathname = resource;
        } else if (resource.match(fpRegex)) {
          /* Relative to current location */
          tsUrl = new URL(window.location);
          tsUrl.hash = '';
          tsUrl.pathname = tsUrl.pathname + resource;
        } else {
          /* Absolute URL */
          tsUrl = new URL(window.location);

          console.debug(`dweb-fetch: Absolute fetch: {{ tsUrl }}`);
        }
    } else {
        return await legacyFetch(resource, config);
    }

    path = tsIpfsPath(tsUrl.toString());

    const objUrl = new URL('@GATEWAY_URL@');
    objUrl.pathname = path;

    console.debug(
      `dweb-fetch: Intercepted: ${ resource } (${ window.location.href })`);

    console.debug(`dweb-fetch: Serving: ${ objUrl }`)

    return await legacyFetch(objUrl.toString(), config);
};
