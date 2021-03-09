
.. image:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/icons/galacteek-128.png
    :align: center

:info: A multi-platform browser for the distributed web

.. image:: https://github.com/pinnaculum/galacteek/workflows/galacteek/badge.svg
    :target: https://github.com/pinnaculum/galacteek/actions

.. image:: https://badges.gitter.im/galacteek/community.svg
    :target: https://gitter.im/galacteek/galacteek?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge

**galacteek** is a multi-platform Qt5-based browser/toolbox
for the IPFS_ peer-to-peer network.

Installation
============

Stable release
--------------

* **AppImage (Linux)**: `Galacteek-0.4.42-x86_64.AppImage <https://github.com/pinnaculum/galacteek/releases/download/v0.4.42/Galacteek-0.4.42-x86_64.AppImage>`_
* **DMG (MacOS)**: `Galacteek-0.4.42-x86_64.dmg <https://github.com/pinnaculum/galacteek/releases/download/v0.4.42/Galacteek-0.4.42-x86_64.dmg>`_
* **Windows**: `Galacteek-0.4.42-installer-x86_64.exe <https://github.com/pinnaculum/galacteek/releases/download/v0.4.42/Galacteek-0.4.42-installer-x86_64.exe>`_

*On Linux*: Be sure to install all the **gstreamer** packages on your
system to be able to use the mediaplayer. Problem with the AppImage ?
`Check the wiki <https://github.com/pinnaculum/galacteek/wiki/AppImage#troubleshooting>`_
or `file an issue <https://github.com/pinnaculum/galacteek/issues/new?assignees=&labels=appimage&template=appimage-issue.md&title=Cannot+run+the+AppImage>`_

*On MacOS*: After opening/mounting the DMG image, hold Control and click on the
**galacteek** icon, and select **Open** and accept. You probably need to
allow the system to install applications *from anywhere* in the security
settings. `Create an issue <https://github.com/pinnaculum/galacteek/issues/new?assignees=&labels=dmg&template=dmg-issue.md&title=Cannot+run+the+DMG+image>`_ if you
have problems running the DMG image.

*On Windows*: GIT is not packaged in the installer. `Install it  here <https://github.com/git-for-windows/git/releases/download/v2.29.2.windows.2/Git-2.29.2.2-64-bit.exe>`_.
If you run into an issue with the installer, `please create an issue here <https://github.com/pinnaculum/galacteek/issues/new?assignees=&labels=windows-installer&template=windows-installer-issue.md>`_ .

You'll need to have *git* installed to sync hashmarks repositories.
See the releases_ page for all releases.

Sponsor this project
====================

See the sponsor_ page for all the possible ways to donate to this project.

.. image:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/icons/github-mark.png
    :target: https://github.com/sponsors/pinnaculum
    :alt: Sponsor with Github Sponsors
    :align: left

.. image:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/icons/liberapay.png
    :target: https://liberapay.com/galacteek/donate
    :alt: Sponsor with Liberapay
    :align: left

Contact
=======

From the *galacteek* main window, go to the *Messenger* workspace
and select *Compose*. In the recipient field, type in *galacteek*,
select the *galacteek-support* contact, write your message and hit *Send*.

Alternatively, from the *galacteek* main window, go to the *Information* menu
on the top right and select *About*. Just click on the *Author*
link (**cipres**) and it will automatically start the BitMessage_
composer with my BitMessage address.

Screencasts
===========

.. figure:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/screencasts/browsing-ipfsio.gif
    :align: center

    Browsing ipns://ipfs.io

.. figure:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/screencasts/filemanager-dirimport.gif
    :align: center

    Filemanager drag-and-drop

.. figure:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/screencasts/filesharing.gif
    :align: center

    File sharing

.. figure:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/screencasts/pyramid-drop1.gif
    :align: center

    Publish a directory to a pyramid

.. figure:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/share/screencasts/bwstats.gif
    :align: center

    Live bandwidth stats

Screenshots
===========

.. figure:: https://raw.githubusercontent.com/pinnaculum/galacteek/master/screenshots/browse-wikipedia-small.png
    :target: https://raw.githubusercontent.com/pinnaculum/galacteek/master/screenshots/browse-wikipedia.png
    :align: center
    :alt: Browsing the Wikipedia mirror over IPFS

    Browsing the Wikipedia mirror over IPFS

Features
========

**galacteek** can either spawn an IPFS daemon and use it as transport, or
connect to an existing IPFS daemon. By default it will try to run a daemon. You
can change the IPFS connection settings by clicking on the settings icon in the
toolbar and restart the application afterwards. If using a custom daemon, you
should enable pubsub and p2p streams, or some features won't be available
(`Check this page <https://github.com/pinnaculum/galacteek/wiki/Setup-your-daemon>`_
for more information).

- Decentralized Identifiers (DID) support with IPID_
- Browser-to-browser DID authentication over libp2p streams
  (Verifiable Credentials with RSA-PSS)
- Browsing sessions with automatic pinning (pins every page you browse)
- Distributed chat with pubsub (chat channels syncronized with CRDT+DAG)
- Support for remote pinning services
- File manager with drag-and-drop support and timeframes (per-day view
  of files in the MFS)
- File sharing
- BitTorrent to IPFS bridge
- Tor support
- Simple messenger based on the Bitmessage_ protocol
- Search content with the ipfs-search_ search engine as well as with cyber_
- Built-in blog with Atom feeds
- Webcam to IPFS capture (image and videos)
- Basic built-in media player with IPFS-stored playlists
- Image viewer and QR codes support
- Use the IPFS filestore to avoid file duplication
- ENS_ (Ethereum Name Service) resolving (access to ENS+IPFS websites)
- Run WASM binaries with wasmer_ (use *Open* on a WASM object from the
  clipboard manager)

Command-line usage
==================

Use the *-d* command-line switch to enable debugging output. Using *--profile* gives
you the ability to have separate application profiles (*main* is the default
profile). Use *--help* for all options.

If you've changed some settings and want to go back to the default
configuration, use **--config-defaults**.

You can run the IPFS daemon in *offline* mode, using **--offline**

Time-rotated log files can be found in the
*$HOME/.local/share/galacteek/main/logs* directory

Enable colorized log output with **--log-color**

*Development*: Use *--monitor* to enable event-loop monitoring with aiomonitor_
(install aiomonitor_ manually as it's not a dependency).
Then connect to the aiomonitor_ interface with **nc localhost 50101**

Keyboard shortcuts
==================

Please see the shortcuts_ page (or from the application, click on the
Information icon in the toolbar, which will open the documentation).

Development
===========

For instructions on how to build the application, look at the
BUILDING_ page.

Contributions
=============

Contributions that can help:

- Write DID services (a chat service using JSON-LD for example)
- UI translations (French, Spanish)
- Manual translations (French, Spanish)

Platforms supported
===================

- Linux (x86_64) (main target)
- Linux (aarch64). If you have a Raspberry PI (64-bit), check the
  Raspberry_ page.
- Any BSD operating system (with manual build)
- MacOS
- Windows

The following features are not yet available for windows:

- Bitmessage client (receiving messages works, but a cygwin IPC bug
  prevents sending messages)

Because of the nature of the software's stack (asyncio/Quamash),
support for any other platform is unlikely.

Requirements
============

- python3 >= 3.7 (Works with python *3.7*, *3.8*, *3.9*)
- go-ipfs_ >= 0.5.0
- PyQt5 >= 5.13.2
- PyQtWebengine >= 5.13.2
- gstreamer (on Linux) for media player support
- git
- asyncqt_
- aiohttp_
- aioipfs_

License
=======

**galacteek** is offered under the GNU GPL3 license

The logos and animations are licensed under the Creative
Commons CC-BY-SA license.

The BT client code (*galacteek.torrent* module) is licensed
under the MIT license, Copyright (c) 2016 Alexander Borzunov

Some elements from the ipfs-css_ repository (CSS files and fonts) are included.

Some icons from the "Oxygen" icons set are included.

This software incudes icons made by the following FlatIcon authors:

- `FreePik <https://www.flaticon.com/authors/freepik>`_
- `Pixel perfect <https://www.flaticon.com/authors/pixel-perfect>`_
- `Kiranshastry <https://www.flaticon.com/authors/Kiranshastry>`_
- `Smashicons <https://smashicons.com>`_
- `Pause08 <https://www.flaticon.com/authors/pause08>`_
- `DinosoftLabs <https://www.flaticon.com/authors/DinosoftLabs>`_

Some of the beautiful artwork (under the Creative Commons CC-BY-SA license)
from the ipfs-logo_ project's repository is included, unchanged.

.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _aioipfs: https://gitlab.com/cipres/aioipfs
.. _aiomonitor: https://github.com/aio-libs/aiomonitor
.. _asyncqt: https://github.com/gmarull/asyncqt
.. _sponsor: https://github.com/pinnaculum/galacteek/blob/master/SPONSOR.rst
.. _raspberry: https://github.com/pinnaculum/galacteek/RASPBERRY.rst
.. _quamash: https://github.com/harvimt/quamash
.. _go-ipfs: https://github.com/ipfs/go-ipfs
.. _dist.ipfs.io: https://dist.ipfs.io
.. _IPFS: https://ipfs.io
.. _ipfs-logo: https://github.com/ipfs/logo
.. _ipfs-search: https://ipfs-search.com
.. _ipfs-css: https://github.com/ipfs-shipyard/ipfs-css
.. _releases: https://github.com/pinnaculum/galacteek/releases
.. _pyzbar: https://github.com/NaturalHistoryMuseum/pyzbar/
.. _shortcuts: https://github.com/pinnaculum/galacteek/blob/master/galacteek/docs/manual/en/shortcuts.rst
.. _urlschemes: https://github.com/pinnaculum/galacteek/blob/master/galacteek/docs/manual/en/browsing.rst#supported-url-formats
.. _releases: https://github.com/pinnaculum/galacteek/releases
.. _BUILDING: https://github.com/pinnaculum/galacteek/blob/master/BUILDING.rst
.. _ENS: https://ens.domains/
.. _in-web-browsers: https://github.com/ipfs/in-web-browsers
.. _AppImage: https://appimage.org/
.. _IPID: https://github.com/jonnycrunch/ipid
.. _wasmer: https://wasmer.io/
.. _cyber: https://cybercongress.ai
.. _Bitmessage: https://wiki.bitmessage.org/
