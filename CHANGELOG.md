# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The changelog for versions prior to v0.4.39 is not available, due to
the changes in the CHANGELOG formatting.

## [Unreleased]

## [0.5.1] - 2021-03-21

### Added
- Support for IPFS URL schemes from QML
- i:/ URL scheme

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
