# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.2] - 2023-06-12

### Added
- Support for the gopher protocol
- g dweb channel: add slots to get the DID from a peer ID and vice versa

## [0.7.1] - 2023-06-04

### Changed
- Dweb passport service: use DID based URLs for all passport identifiers
- Set a "last seen date" triple for DIDs
- Change the gemini CSS

### Fixed
- SparQLResultsModel: properly handle datetime Literals in data()

## [0.7.0] - 2023-05-08

### Changed
- Register a default aioipfs jsonld document loader early on
  (this fixes some jsonld *normalization* operations where the default
  "requests" document loader couldn't pull schemas from ipfs)
- asyncify the *galacteek.ld.signatures* module
- goliath (guardian): add a processor for ips://galacteek.ld/GenericReaction

## [0.6.9] - 2023-04-24

### Added
- Implement a simple IPFS HTTP gateway availability checker
- Show the HTTP gateway response time and status in the gateways menus
- IPFSPath: implement publicSubDomainUrlForGateway()

### Changed
- QQuickWebEngineProfile: install all URL schemes in quickClone()

### Fixed
- SparQLResultsModel: always use Literal.value in data()

## [0.6.8] - 2023-04-04

### Added
- Implement a synchronous thread-based version of NativeIPFSSchemeHandler
  that's now used by the ipfs:// scheme handler

### Fixed
- Show the hovered URL tooltip at the bottom left corner of the
  QtWebEngineView widget

## [0.6.7] - 2023-04-01

### Added
- ChatGPT
  - Resize generated images
  - Add an "Open" button to import generated images to IPFS and open them
  - Implement image variations (up to 9 images in one call)

### Fixed
- IPFSPath: fix parsing of "subdomain gateway" URLs

## [0.6.6] - 2023-03-31

### Added
- ChatGPT: Add a QDial widget to control the text completion's "temperature"

### Fixed
- Better resizing policy for the QTextEdit containing the text completion

## [0.6.5] - 2023-03-25

### Added
- Web Passwords vault implementation: save passwords from HTML forms and
  autofill passwords
- ChatGPT integration with the openai python module
  - Implement basics: text completion, image generation
  - Implement translation to languages supported by ChatGPT
  - Implement QML code generation with live preview in a QtQuickWidget

### Changed
- openai pypi requirement: ==0.27.2

## [0.6.4] - 2023-03-21

### Added
- Add some more hugo themes for hugo pyramids
- Add a new pronto event: GraphModelUpdateEvent

### Changed
- Group pyramid clipboard actions in a single menu
- Text editor: use the pathlib.Path API
- Update the tags model and rebuild the hashmarks menu when the default
  content language is changed

### Fixed
- Tag preferences model: honor the content language from the settings
- Hashmarks manager
  - Prevent a double menu update on startup
  - Fix issue with wrong tag language code
  - Optimize menu update when tagging/untagging hashmarks from the tags dialog
  - Add an action to remove a subscription to a tag

## [0.6.3] - 2023-03-14

### Added
- Support for building websites with hugo (a static website generator)
  - New dialog to automatically download and install hugo (extended version)
  - Support for changing the hugo theme from a list of standalone themes

- Pyramids
  - Add a menu action to copy the pyramid's URL using one of the public
    IPFS HTTP gateways
  - Add a menu action to pin the pyramid's content locally or to a remote
    IPFS pinning service

### Changed
- Text editor: flash the pyramid drop button after a modification
  to a file is made to draw attention

## [0.6.2] - 2022-12-16

### Changed
- Freeze kubo repo migrations for v13

## [0.6.1] - 2022-11-06

### Added
- LDSearcher widget: linked-data searcher
- Tags dialog: make it possible to add new tags by querying wikidata or dbpedia
- New themes: breeze-dark and indigo
- Add --config-apply cmdline arg

### Changed
- Upgrade pillow req to v9.2.0
- Tag URIs are always lowercased

### Fixed
- Catch/silence asyncio.CancelledError in dbpedia CONSTRUCT tasks

## [0.6.0] - 2022-10-20

### Added

- UI dialog to create tags
- Settings: add a setting to enable/disable the resource blocker
  (disabled by default)
- An action in the clipboard item menu to copy the URL in the clipboard
  for a specific gateway.
- Show the meaning of a tag (i18n resource abstract, live from dbpedia)
  in the tags dialog

### Changed
- Open up the ws toolbar when a QML dapp is loaded

## [0.5.9] - 2022-10-17

### Changed

- ontolochain: urn:ipg:i:i0 is the default output graph
- ipfs-search UI: make the JS side call initialize() on the handler
  after all the signals are connected

### Fixed

- P2P smartql service: Only allow POST requests on /sparql
- P2P smartql service rate-limiting: require a sufficient log size
  before deciding to block a request or not

## [0.5.8] - 2022-09-24

### Added

- browser: Monkeypatch fetch() to support loading IPFS objects natively
  without any JS requirements
- Interceptor: add http://domain.eth to ens://domain.eth redirection
- Add a resource blocking system (with python-adblock; block lists are
  pulled from IPFS)
- Add the ips:// URL scheme (renders IPS JSON-LD schemas)
- Add a UI action to view IPS schemas
- Implement intelligent RDF tags (inspired from "Meaning of a tag")
- pronto: support for subconjunctive graphs (parent store)
- pubsub sniffer: nicer UI (add topic filter and max messages widgets)
- Add UI elements in the settings to configure the various webprofiles
- Add support for Greasemonkey scripts
- Use a popup (vs a tab previously) for the pinning status widget
- Add support for configurable dark theme inside QtWebEngine widgets
- browser: Detect page's language from lang tag and pass it to addHashmark

### Changed

- Hashmarks: use RDF storage (old hashmarks db is deprecated,
  possible to migrate from the UI)
- js-ipfs-http-client: upgrade to v49.0.2
- IPFS search UI
  - Add an IPFS gateway UI selector
  - Add an exact MIME type filter
  - Add a filter for "last seen period" (helps to filter out dead content)
  - Search results are buffered in a RDF graph and periodically flushed
  - Embed audio and video content in the search results

### Fixed

- Pubsub sniffer UI (bugfix): unhook PS listeners when the widget is destroyed
- Fix "Repeated subscription to key" aiopubsub message warnings

## [0.5.7] - 2022-09-08

### Added

- prontog:/ Implement RDF ttl graph highlighting with pygments

### Changed

- Use kubo v0.15.0 and fs-repo-migrations v2.0.2 in the runtime images
- Add galacteek.ipfs.asyncipfsd.ipfsMigrationLatest
  (to get the latest available migration version with fs-repo-migrations)
- Use aioipfs==0.5.7 (works with the latest kubo)
- Put the browser tab URL address bar code in a separate module
- Implement the URL clouding widget in a QML QuickItem component
- Pin all major pypi requirements

### Fixed

- Fix a bug when the first browser tab in a workspace wouldn't
  get its tab title updated when the page's title changes

## [0.5.6] - 2022-08-08

### Added

- Functions to reencode PeerIDs into different base encodings
- Support for the ipfs+http(s):// protocol
- UI: add actions to create HTTP forward DID services
- Implement list-based and item-based Qt SparQL models

### Changed
- ipfs URL scheme handler: use chunking algorithm for downloading objects
- ipfs URL scheme handler: use QIODevice.Append as the default QBuffer open mode
- Use SparQL models for the various peers, DID, and DID services models

### Fixed
- EthDNS resolving: use the dns.eth.limo service instead of eth.link
  (eth.link is now unavailable).
- ipfs:// URL scheme handler
  - Don't preinstantiate QBuffer for each request
  - Fix a bug with relative URLs when cat() tells us a DAG is a unixfs
    directory: use a redirect with a trailing / so that QtWebEngine can
    properly compute relative URLs

## [0.5.5] - 2022-04-23

### Added
- Add a way to define datasets in the pronto config
- Add a console script: *rdfifier* (converts YAML-LD to RDF)
- MFS model: add an API to trigger UnixFS listing from external
  agents (like a QML dapp)
- ipfs dweb channel: Add API for remote pinning

### Changed
- Allow file:// URLs to be passed from QML code
- CI: distribute wheel
- httpFetch returns a Path and sha512 checksum
- Set SSL_CERT_FILE from certifi for dmg and AppImage
- IPFSOperator: isPinned() can receive a pin type argument

## [0.5.4] - 2022-04-04

### Added
- RDF hashmarks store
- Qt SparQL models API: add async support
- Add MIME type recognition for turtle (ttl), YAML
- Add UI to browse pronto graphs from a browser tab

### Changed
- Improve the Curve25519 pubsub API
- SmartQL P2P service
  - Implement a peer-dependent authentication middleware for the http service
- Pronto
  - galacteek.ld.pronto: pubsub service is now encrypted with curve25519
  - Use time-rotating peer-dependent credentials for the smartql p2p service
  - Use Sleepycat as the default RDF store
- Mediaplayer:
  - Deprecate old MFS+JSON playlists storage
  - Store playlists as RDF (schema is: ips://galacteek.ld/MultimediaPlaylist)
  - Playlists by default are stored in a private RDF store
  - Playlists can be published to a public RDF store
  - Public playlists are synchronized between peers via a SparQL script
- Content providers peering: separate Pinata nodes config by region
- Update *Pillow* to v9.0.1
- EthDNS resolver: use DNS over HTTPs requests using the JSON API from eth.link
- IPS contexts loader: add TTLCache for small schemas
- inter:/ URL scheme j2 templates are now dynamically loaded from an icapsule

### Fixed
- AppImage: fix xkb issue when running in Wayland (set XKB_CONFIG_ROOT)

## [0.5.3] - 2022-01-14

### Added
- ICapsules registry system (based on YAML-LD)
- Automatic peering with popular IPFS content providers (provides
  better/faster content finding)
- Introduce the **gem** protocol (P2P gemini capsules)
- Add a new type of pyramid (*gems*, gemini IPFS capsules)
- Add a DID service to serve *gems* over IPFS streams (accessible
via the *gemi:/* URL scheme)
- New python dependency: custom [aiogemini](https://gitlab.com/galacteek/aiogeminipfs)

### Changed
- Changes in the *pronto* ontolochain system
  - Store the sync date after each chain upgrade
  - Send pronto pubsub messages at random intervals

### Fixed
- Focus bug fix in the text editor widget

## [0.5.2] - 2021-08-04

This release brings support for the gemini protocol.

Updating is recommended, as the go-ipfs upgrade fixes potential
performance issues ocurring with go-ipfs *0.9.0*.

### Added
- Support for the great gemini protocol via the *gemini://* scheme
  - Gemini capsule browsing
  - Support for gemini's input system
  (try [gemini://geminispace.info/search](gemini://geminispace.info/search))
  - Support for raw files download via *gemini://* (tested with PDF files)

### Changed
- Use go-ipfs version *0.9.1* (see the
[release notes](https://github.com/ipfs/go-ipfs/releases/tag/v0.9.1)
for more details)

## [0.5.1] - 2021-06-29

### Added
- 1st iteration of a semantic dweb engine
  - Support translation of IPFS objects (mainly DAGs) to RDF graphs
  - Support querying the RDF graphs via SparQL from QML dapps
  - P2P SparQL services and exchange of objects over IPFS-P2P tunnels
- Enable the use of the new experimental *AcceleratedDHTClient*
  go-ipfs setting (this activates an alternative, faster DHT client)
- Support for IPFS URL browsing from QML (QtWebEngine QML integration)
- i:/ URL scheme

### Changed
- Use go-ipfs version *0.9.0*
- Use fs-repo-migrations version *2.0.1*

### Fixed
- Bug fix: "link to QA toolbar action"

## [0.5.0] - 2021-03-12

This release introduces support for *remote pinning*.

All IPFS services (pubsub, p2p) are now part of the
application's services graph (the application is now designed
as a graph of services, you can view the graph in the *Settings*
workspace).

### Added
- Use *go-ipfs* version: *0.8.0*
- Use *PyQt* version: *5.15.2*
- Use *PyQtWebEngine* version: *5.15.2*
- Support for remote pinning services (yay!)
  - Configure your RPS from the settings (tested with *Pinata*)
  - From the PIN object buttons (blue pin) you can choose to
    pin with a remote service or to your IPFS node
  - Add a status icon for remote pinning (basic for now)
- Add a workspace action to view the application's services graph
  (you need graphviz installed for this to work)
- Add coroutines to load services dynamically from the
  *services* Python package

### Changed
- Support for mkdocs themes (bootswatch) for your dwebsites
  (*darkly* is the default)
- Easier to publish/unpublish websites, dynamic content .. on your DID
- Easier to create and publish a markdown website
- QA toolbar: modernize, should now support large number of items
- Use a dock instead of a status bar
- MFS: recursive collapse when double-clicking an already-expanded
  directory
- Pubsub services are now part of the services tree
- P2P services (like the DIDauth service) are now part of the
  services tree

### Fixed
- Fix mkdocs website creation on non-Linux platforms
- Focus bug in the markdown editor

## [0.4.42] - 2020-12-12

This is build 42 (the end of the cycle).

RIP Douglas Adams, and thanks for all the fun.

### Added
- BitMessage support
- Themes support. *moon3* is the default theme
- Hierarchical, per-module config system based on omegaconf

- Introduce APIs to dynamically start P2P services associated with
  a DID service
- Introduce protocol versioning by default for P2P services
  /p2p/Qm..../x/pizza/1.0.0
- Async logging handlers (logbook)
- *galacteek.ipfs.ipfsops.IPFSOperator*: add coroutines to dial P2P
  services from a full service address, e.g /p2p/Qm..../x/myservice

- Python dependencies
  - [mode](https://github.com/ask/mode) == 4.4.0
  - [omegaconf](https://github.com/omry/omegaconf) == 2.0.5

### Changed
- Combine async services (*GService*) with in-app JSON-LD PubSub messaging.
  This should become the official way of pushing events throughout the app.
- Use dynamic, configurable processing throttlers for all pubsub services
- *galacteek.ipfs.asyncipfsd.AsyncIPFSDaemon*: the daemon's configuration
  is now done in an atomic call (by externally calling *ipfs config replace*).
  This makes the boot process faster.
- Configurable webprofiles

### Fixed
- Memory leak in the BrowserTab class (Qt reparenting)
- UTF-8 rendering of blog posts

## [0.4.41] - 2020-12-04
### Added
- Tor support
  - Tor proxying on all platforms (enabled manually from the
    status bar for now, very soon there'll be finer control
    of the relays via [stem](https://stem.torproject.org/))
  - Proxying of ipfs-search and cyber requests via Tor

- Add a new *anonymous* web profile
- Automatically fetch favicons when hashmarking an http(s) website
- Handle SSL certificate errors

- New python dependencies
  - [aiohttp-socks](https://pypi.org/project/aiohttp-socks/) >=0.5.5
  - validators >= 0.18.1

### Changed
- Browser tab UI
  - Use a block-style cursor for the address bar
  - Typing an .eth domain name automatically loads it through *ens://*
  - Run IPFS searches or searches with popular engines (duckduckgo, ..)
    from the address bar
  - Change the history lookup interface

- The @Earth workspace is now the first/default workspace in the WS stack
- Workspace APIs
  - Changed wsRegisterTab(): accept a *position* argument to insert tabs
    at the end of the tabs list or after the current tab

### Fixed
- Bookmarking of clearnet URLs

## [0.4.40] - 2020-11-29
### Added
- Lightweight BT client integration (asyncio-based)
  - Add torrents from .torrent files, magnet links
  - Automatically transform magnet links stored in the clipboard 
    to .torrent files stored in IPFS
  - Torrent to IPFS transfer: from the BT client you can easily
    transfer completed downloads to IPFS and have them linked in
    your *downloads* MFS directory.

- New python dependencies
  - [colour](https://github.com/vaab/colour) >= 0.1.5
  - [magnet2torrent](https://github.com/JohnDoee/magnet2torrent) >= 1.1.1

### Changed
- Log to time-rotated log files by default (use --log-stderr if you
  want logs to be sent to stderr instead)
- Per-module color styling of log records
- IPFS daemon init dialog
  - Add a combo box to select the IPFS content routing mode
  - Add a *Quit* button

## [0.4.39] - 2020-11-15
### Added
- Support for Windows (packaged as a one-file EXE and NSIS installer)

- Continuous Integration with Github Actions (Travis CI is still supported)
  - CI workflow for ubuntu (Bionic), MacOS and windows
  - Automatically embed CHANGELOG contents in GH releases

### Changed
- Move from quamash to [asyncqt](https://github.com/gmarull/asyncqt) (v 0.8.0)

### Fixed
- Fix issues with libmagic and zbar on Windows
- Fix issues with IPFS paths not always treated as POSIX paths
- Fix [#31](https://github.com/pinnaculum/galacteek/issues/31) (thanks @teknomunk)
- Fix [#32](https://github.com/pinnaculum/galacteek/issues/32) (thanks @teknomunk)
