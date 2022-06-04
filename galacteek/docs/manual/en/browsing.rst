
Browsing
========

URL bar
-------

In the address bar you can type (or paste) a full URL, an
IPFS :term:`CID` or a full :term:`IPFS path` (they will be
loaded with the appropriate scheme). If you type
an ENS domain name or a regular domain name it will be
loaded automatically with the right scheme.

You can also type words that you want to search for in the hashmarks
database and the visited URLs history. Search results will
pop up after a short amount of time. Hitting the *Escape* key
will hide the results.

You can also use specific syntax to search with certain
search engines:

- Use the **d** prefix to search with the DuckDuckGo_ web search engine.
  Example: **d distributed web**
- Use the **i** or **ip** prefix to run a search on the IPFS
  network. Example: **i distributed web**

CID status icon
^^^^^^^^^^^^^^^

When you are browsing a valid page over IPFS, you will see an
orange-colored IPFS cube or a blue-colored IPFS cube to the
left of the address bar.

If you are browsing using an *indirect* scheme (an URL scheme
that proxies/maps IPFS objects, like *ens://* or *qmap://*), the
cube will always display information about the "underlying"
IPFS object that is being accessed.

When you see an orange cube, it means that you're browsing
using the secure *ipfs://* URL scheme with a base32-encoded
:term:`CID`.

When you see a blue cube, it means that you're browsing
using the *dweb:/* URL scheme.

Clicking on the cube will open the DAG viewer for the page's
IPFS object.

Supported URL formats
---------------------

ipfs:// and ipns://
^^^^^^^^^^^^^^^^^^^

These are the *native* URL schemes that support
using base32-encoded (lowercase) :term:`CID` strings as
hostname (with the benefit of the CID becoming the URL's
authority). You can use a domain name with both schemes.
The following URL formats are supported::

    ipfs://{cidv1base32}/path/to/resource
    ipfs://{fqdn-with-dnslink}/path/to/resource
    ipns://{fqdn-with-dnslink}/path/to/resource
    ipns://{libp2p-key-in-base32}/path/to/resource

Examples::

    ipfs://bafybeibp7sff6wwowsimitrxcpdoqnknyreesvtn24qrnx7gxkhqhzj2fi/
    ipfs://awesome.ipfs.io/articles/
    ipns://ipfs.io/
    ipns://bafzbeibj2g3uu4lm22xriznrfc22tocvtzdkoo7mqm46v7x3fkelkd6d6i/docs/

If you use a valid base58-encoded :term:`CID` (whatever the CID version)
with the *ipfs://* URL scheme, the CID will automatically be
upgraded (v0 to v1) if necessary and its base32 representation will
be used in the URL. For instance, trying to access::

    ipfs://QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco

will trigger a :term:`CID upgrade` and ultimately access the same object with
its base32 representation at the following URL::

    ipfs://bafybeiemxf5abjwjbikoz4mc3a3dla6ual3jsgpdr4cjr3oz3evfyavhwq

*Note*: the scheme handler for these URL schemes does not
use the *go-ipfs* daemon's HTTP gateway

ipid://
^^^^^^^

The *ipid* URL scheme allows direct access to the content published
by *IPID* holders. URLs use the following format::

    ipid://{did-id}/{service-path}

Where *did-id* is the *IPID identifier* (it actually corresponds
to an IPNS key).

Examples::

    ipid://k2k4r8jz0dyx3przi8mk1trj1ga0ibgroyhbvwumkbig70uphz7qpnqn
    ipid://k2k4r8jz0dyx3przi8mk1trj1ga0ibgroyhbvwumkbig70uphz7qpnqn/blog

This scheme currently only supports the *GET* method.

dweb:/
^^^^^^

This is the legacy scheme and it will automatically be used when
accessing content rooted under :term:`CIDv0` objects.

This scheme uses the *go-ipfs* HTTP gateway. You should use
this scheme for example when accessing websites that use
the *Fetch API*.

Since version *0.4.12*, automatic :term:`CID upgrade` is enabled as much
as possible, meaning that the *ipfs://* URL scheme will
automatically be used whenever possible.
IPNS paths using a base58 libp2p key will still be
accessed using the *dweb:/* scheme.

Because it proxies the requests to the *go-ipfs* daemon's HTTP
gateway, it can handle anything that the daemon supports::

    dweb:/ipfs/{cidv0}/path/to/resource
    dweb:/ipfs/{cidv1b32}/path/to/resource
    dweb:/ipfs/{cidv1b58}/path/to/resource
    dweb:/ipns/{fqdn-with-dnslink}/path/to/resource
    dweb:/ipns/{libp2p-key-in-base58}/path/to/resource

Examples::

    dweb:/ipfs/bafybeibp7sff6wwowsimitrxcpdoqnknyreesvtn24qrnx7gxkhqhzj2fi
    dweb:/ipfs/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/wiki/
    dweb:/ipns/QmarwvLcWm51SwhnxABxsy1cE7v1RHPMjt4VkQ3kqsrdX3
    dweb:/ipns/awesome.ipfs.io

ens:// and ensr://
^^^^^^^^^^^^^^^^^^

There is support for accessing IPFS-hosted websites that are registered
on the *Ethereum Name Service* (see ENS_). The ENS domains are resolved
via EthDNS.

Just use **ens://mydomain.eth** or **ensr://mydomain.eth** for instance
as a URL in the address bar.

The *ensr://* URL scheme is a resolve-and-redirect scheme, meaning
that you will be redirected to the IPFS website referenced on ENS,
switching to the *dweb://* scheme.

The *ens://* URL scheme is a resolve-and-proxy scheme: rather than
being redirected, the URL is preserved and the scheme handler
transparently proxies the resolved IPFS object referenced in the
DNSLink for this domain. *Note*: if the underlying website depends
on the Javascript *window.location* variable to contain the IPFS
path, use the *ensr* scheme.

Go to `ens://blog.almonit.eth <ens://blog.almonit.eth>`_ to find a list
of some ENS+IPFS websites.

gemini://
^^^^^^^^^

You can browse Gemini_ capsules using the *gemini* URL scheme.

- `gemini://geminispace.info <gemini://geminispace.info>`_

gemi:/
^^^^^^

You can browse Gemini_ capsules over IPFS streams using the
*gemi* URL scheme. *gemi* URLs include the peer ID and the
capsule name::

    gemi:/12D3KooWNLKji99VFXXRns4vXnqvHGNdEN5rBBwSqKVGhDQHfzT1/hello/

magnet: and stream-magnet:
^^^^^^^^^^^^^^^^^^^^^^^^^^

`WebTorrent <https://webtorrent.io/>`_ is partially supported. The contents
of a torrent can be rendered from a *magnet* link. Example:

- `Sintel (animation) <magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=Sintel&ws=https%3A%2F%2Fwebtorrent.io%2Ftorrents%2F&xs=https%3A%2F%2Fwebtorrent.io%2Ftorrents%2Fsintel.torrent#>`_

The individual files of the torrent can be transferred to your IPFS node by
clicking on the links in the page.

prontog:/
^^^^^^^^^

The *prontog* URL scheme gives you access to the *pronto* RDF
graph exports (in *turtle* (ttl) or *XML* formats)::

- `prontog:/urn:ipg:i <prontog:/urn:ipg:i>`_
- `prontog:/urn:ipg:h0 <prontog:/urn:ipg:h0>`_

manual:/
^^^^^^^^

There is support for mapping IPFS objects to a specific URL scheme,
allowing easy access from the URL bar to commonly-accessed resources.

This is used for instance by the manual. To access the manual from
the URL bar, just type in **manual:/** (or just **manual:**)

- `manual:/ <manual:/>`_
- `manual:/browsing.html <manual:/browsing.html>`_

qmap://
^^^^^^^

The **qmap://** URL scheme allows quick access to IPFS objects that
you've mapped from the browser. From a browser tab, open the IPFS
menu and select *Create quick-access mapping*. Once the object is
mapped, it will be accessible with the **qmap://mappingname** URL,
for instance if your mapping name is *docs*, the quick-access URL
would be **qmap://docs**

If you are mapping an IPNS path, it is resolved periodically
and the result is cached.

Web profiles
------------

There are 4 distinct web profiles that can be used when accessing a
webpage. The current profile can be changed from a browser tab by
opening the IPFS menu and selecting a profile from the *Web profile*
submenu.

You can change the default web profile that will be used when opening
a browser tab by changing the *Default web profile* setting in the *UI*
section of the application settings.

Anomymus profile
^^^^^^^^^^^^^^^^

Anonymous profile:

- Javascript is disabled
- Caching is disabled
- No persistent cookies
- XSS auditing

Minimal profile
^^^^^^^^^^^^^^^

This profile doesn't include any specific scripts

IPFS profile
^^^^^^^^^^^^

This profile adds a JS script to be able to access your IPFS node
from *window.ipfs* in the main Javascript world

Web3 profile
^^^^^^^^^^^^

Derives from the IPFS profile. If Ethereum is enabled, it injects
a *Web3* instance (from the *web3.js* JS library) available as
*window.web3* in the main Javascript world

.. _ENS: https://ens.domains/
.. _DuckDuckGo: https://duckduckgo.com
.. _Gemini: https://gemini.circumlunar.space/
