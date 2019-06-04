
.. image:: https://gitlab.com/galacteek/galacteek/raw/master/share/icons/cube-nova-aqua.png
    :align: center
    :width: 128
    :height: 128

:info: A multi-platform IPFS_ browser

**galacteek** is an experimental multi-platform Qt5-based browser/toolbox
for the IPFS_ peer-to-peer network.

Platforms supported
===================

- Linux
- MacOS
- FreeBSD

Donations
=========

If you want to donate to this project please use the
`Patreon page <https://www.patreon.com/galacteek>`_

Installation
============

On Linux systems you can use the AppImage (from the releases_ page)
or install from PyPI. On MacOS and other systems you'll need to
install from PyPI.

PyPI
----

You need to have python>=3.5 (python>=3.6 is recommended) and pip installed.
From a virtualenv, or as root, install with:

.. code-block:: shell

    pip install galacteek

Upgrade with:

.. code-block:: shell

    pip install -U galacteek

Or building it from source:

.. code-block:: shell

    pip install -r requirements.txt
    python setup.py build install

Now just run the application with:

.. code-block:: shell

    galacteek

If you don't have go-ipfs_ already installed, the application will ask you
if you want to automatically download and install it from dist.ipfs.io_
You need a recent version of go-ipfs_ (> 0.4.7) with the new DAG API.

For the media player to work on Linux, you will need to install the
*gstreamer* (1.x) package and all the gstreamer plugins.

There is experimental support for reading QR codes containing IPFS addresses,
using either pyzbar_ or qreader_ (both are included in the application).
pyzbar_ depends on the zbar shared library,
so make sure it's installed on your system (on Linux look for a libzbar or
libzbar0 package and install it, on MacOS install it with
**brew install zbar**). It's recommended to use pyzbar as it supports
reading multiple QR codes contained in a single image.

AppImage
--------

For Linux users (arch: *x86_64*), you can get an AppImage
from the releases_ page. The script used to build the image can be found
`here <https://github.com/eversum/galacteek/blob/master/AppImage/galacteek-appimage-build>`_

Command-line usage
==================

Use the *-d* command-line switch to enable debugging output. Using *--profile* gives
you the ability to have separate application profiles (*main* is the default
profile). Use *--help* for all options.

*Development*: Use *--monitor* to enable event-loop monitoring with aiomonitor_
(install aiomonitor_ manually as it's not a dependency).
Then connect to the aiomonitor_ interface with **nc localhost 50101**

Features
========

**galacteek** can either spawn an IPFS daemon and use it as transport, or
connect to an existing IPFS daemon. By default it will try to run a daemon. You
can change the IPFS connection settings by clicking on the settings icon in the
toolbar and restart the application afterwards. If using a custom daemon, you
should enable pubsub or some features won't be available.

- Browsing sessions with automatic pinning (pins every page you browse)
- Feeds (following IPNS hashes)
- Sharing hashmarks over pubsub
- File manager with drag-and-drop support
- Basic built-in media player with IPFS-stored playlists
- Search content with the ipfs-search_ search engine
- Image viewer
- QR codes from images
- Decentralized application development/testing with the Javascript API
  (using *window.ipfs*)

Keyboard shortcuts
==================

Please see the shortcuts_ page (or from the application, click on the
Information icon in the toolbar, which will open the documentation).

Screenshots
===========

.. figure:: https://gitlab.com/galacteek/galacteek/raw/master/screenshots/browse-wikipedia-small.png
    :target: https://gitlab.com/galacteek/galacteek/raw/master/screenshots/browse-wikipedia.png
    :align: center
    :alt: Browsing the Wikipedia mirror over IPFS

    Browsing the Wikipedia mirror over IPFS

.. figure:: https://gitlab.com/galacteek/galacteek/raw/master/screenshots/qr-codes-mezcla.png
    :target: https://gitlab.com/galacteek/galacteek/raw/master/screenshots/qr-codes-mezcla.png
    :align: center
    :alt: QR codes

    IPFS QR codes

Contributions and contact
=========================

Contributions and ideas are more than welcome!
Contact by mail at: galacteek AT protonmail DOT com

Requirements
============

- python3 >= 3.5.3 (it is strongly suggested to use python>=3.6)
- go-ipfs_ > 0.4.7
- qt5
- PyQt5 with QtWebEngine support
- gstreamer (on Linux) for media player support
- quamash_
- aiohttp_
- aioipfs_

License
=======

**galacteek** is offered under the GNU GPL3 license

Some elements from the ipfs-css_ repository (CSS files and fonts) are included.

Some icons from the "Oxygen" icons set are included.

Some of the beautiful artwork (under the Creative Commons CC-BY-SA license)
from the ipfs-logo_ project's repository is included, unchanged.

Main icon made by srip_ (flaticon, CC by 3.0)

.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _aioipfs: https://gitlab.com/cipres/aioipfs
.. _aiomonitor: https://github.com/aio-libs/aiomonitor
.. _quamash: https://github.com/harvimt/quamash
.. _go-ipfs: https://github.com/ipfs/go-ipfs
.. _dist.ipfs.io: https://dist.ipfs.io
.. _IPFS: https://ipfs.io
.. _ipfs-logo: https://github.com/ipfs/logo
.. _ipfs-search: https://ipfs-search.com
.. _ipfs-css: https://github.com/ipfs-shipyard/ipfs-css
.. _releases: https://github.com/eversum/galacteek/releases
.. _srip: https://www.flaticon.com/authors/srip
.. _pyzbar: https://github.com/NaturalHistoryMuseum/pyzbar/
.. _qreader: https://github.com/ewino/qreader/
.. _shortcuts: http://htmlpreview.github.io/?https://raw.githubusercontent.com/eversum/galacteek/master/galacteek/docs/manual/en/html/shortcuts.html
.. _releases: https://github.com/eversum/galacteek/releases
