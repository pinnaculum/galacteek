.. image:: https://gitlab.com/galacteek/galacteek/-/raw/master/share/icons/galacteek-128.png
    :align: center

:info: A multi-platform browser and semantic agent for the distributed web

.. image:: https://gitlab.com/galacteek/galacteek/badges/master/pipeline.svg

**galacteek** is a multi-platform Qt5-based browser and
semantic agent for the distributed web

Where
=====

**galacteek** is developed `on GitLab <https://gitlab.com/galacteek/galacteek>`_
(`official website here <https://galacteek.gitlab.io>`_).

Join in `on the Telegram channel <https://t.me/Galacteek>`_
(there's also a channel on the Aether_ network, search for the *Galacteek*
community there).

Installation
============

Please go to `the download section on the website <https://galacteek.gitlab.io/#download>`_

*On Linux*: Be sure to install all the **gstreamer** packages on your
system to be able to use the mediaplayer. Problem with the AppImage ?
`Check the wiki <https://gitlab.com/galacteek/galacteek/-/wikis/AppImage#troubleshooting>`_
or `file an issue <https://gitlab.com/galacteek/galacteek/-/issues/new>`_

*On MacOS*: After opening/mounting the DMG image, hold Control and click on the
**galacteek** icon, and select **Open** and accept. You probably need to
allow the system to install applications *from anywhere* in the security
settings. `Create an issue <https://gitlab.com/galacteek/galacteek/-/issues/new>`_ if you have problems running the DMG image.

*On Windows*: GIT is not packaged in the installer. `Install it  here <https://github.com/git-for-windows/git/releases/download/v2.29.2.windows.2/Git-2.29.2.2-64-bit.exe>`_.
If you run into an issue with the installer, `please create an issue here <https://gitlab.com/galacteek/galacteek/-/issues/new>`_ .

You'll need to have *git* installed to sync hashmarks repositories.

Sponsor this project
====================

See the sponsor_ page for all the possible ways to donate to this project.

.. image:: https://gitlab.com/galacteek/galacteek/-/raw/master/share/icons/github-mark.png
    :target: https://github.com/sponsors/pinnaculum
    :alt: Sponsor with Github Sponsors
    :align: left

.. image:: https://gitlab.com/galacteek/galacteek/-/raw/master/share/icons/liberapay.png
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

See `the screencasts section on the website <https://galacteek.gitlab.io/#screncasts>`_

Screenshots
===========

.. figure:: https://gitlab.com/galacteek/galacteek/-/raw/master/screenshots/browse-wikipedia-small.png
    :target: https://gitlab.com/galacteek/galacteek/-/raw/master/screenshots/browse-wikipedia-small.png
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
(`Check this page <https://gitlab.com/galacteek/galacteek/-/wikis/Configure-your-daemon>`_
for more information).

- Decentralized Identifiers (DID) support with IPID_
- Semantic dweb agent (distributed RDF graph)
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

- Write DID services
- UI translations (French, Spanish)
- Manual translations (French, Spanish)

Platforms supported
===================

- Linux (x86_64) (main target)
- Linux (aarch64). If you have a Raspberry PI (64-bit), check the
  Raspberry_ page.
- Any BSD operating system (with manual build)
- MacOS

**Unofficially** supported:

- *Windows*: although an installer is provided, no special effort
  will be put in maintaining support for this platform. Not all
  features will work. By all means use Linux and you'll enjoy the
  full experience.

Because of the nature of the software's stack (asyncio/Quamash),
support for any other platform is unlikely.

Requirements
============

- python3 >= 3.7 (Works with python *3.7*, *3.8*, *3.9*)
- go-ipfs_ >= 0.5.0 (the installers include go-ipfs version 0.9.0)
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
.. _sponsor: https://gitlab.com/galacteek/galacteek/-/blob/master/SPONSOR.rst
.. _raspberry: https://gitlab.com/galacteek/galacteek/-/blob/master/RASPBERRY.rst
.. _quamash: https://github.com/harvimt/quamash
.. _go-ipfs: https://github.com/ipfs/go-ipfs
.. _dist.ipfs.io: https://dist.ipfs.io
.. _IPFS: https://ipfs.io
.. _ipfs-logo: https://github.com/ipfs/logo
.. _ipfs-search: https://ipfs-search.com
.. _ipfs-css: https://github.com/ipfs-shipyard/ipfs-css
.. _pyzbar: https://github.com/NaturalHistoryMuseum/pyzbar/
.. _shortcuts: https://gitlab.com/galacteek/galacteek/-/blob/master/galacteek/docs/manual/en/shortcuts.rst
.. _urlschemes: https://gitlab.com/galacteek/galacteek/-/blob/master/galacteek/docs/manual/en/browsing.rst
.. _releases: https://github.com/pinnaculum/galacteek/releases
.. _BUILDING: https://gitlab.com/galacteek/galacteek/-/blob/master/BUILDING.rst
.. _ENS: https://ens.domains/
.. _in-web-browsers: https://github.com/ipfs/in-web-browsers
.. _AppImage: https://appimage.org/
.. _IPID: https://github.com/jonnycrunch/ipid
.. _wasmer: https://wasmer.io/
.. _cyber: https://cybercongress.ai
.. _Bitmessage: https://wiki.bitmessage.org/
.. _Aether: https://getaether.net/
