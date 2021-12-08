# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The changelog for versions prior to v0.4.39 is not available, due to
the changes in the CHANGELOG formatting.

## [Unreleased]

## [0.5.3] - 2021-09-18

### Added
- Automatic peering with popular IPFS content providers (provides
  better/faster content finding)
- Introduce the **gem** protocol (P2P gemini capsules)
- Add a new type of pyramid (*gems*, gemini IPFS capsules)
- Add a DID service to serve *gems* over IPFS streams (accessible
via the *gem:/* URL scheme)
- New python dependency: custom [aiogemini](https://gitlab.com/galacteek/aiogemini)

### Changed
- Changes in the *pronto* ontolochain system
  - Store the sync date after each chain upgrade
  - Send pronto pubsub messages at random intervals

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
