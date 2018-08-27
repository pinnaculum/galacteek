=========
Galacteek
=========

:info: A modest IPFS_ browser

This is a simple application allowing you to search, browse, publish and
hashmark content on the permanent web accessible through the IPFS_ peer-to-peer
network.

Installation
============

PIP
---

You need to have python 3.5 and pip installed, as well as go-ipfs_.
From a virtualenv, or as root, install with:

.. code-block:: shell

    pip install galacteek

Or building it from source:

.. code-block:: shell

    pip install -r requirements.txt
    python setup.py build install

Now just run the application with:

.. code-block:: shell

    galacteek

If you don't have go-ipfs_ already installed, the application will ask you
whether you want to automatically download and install it from dist.ipfs.io_

For the media player to work on Linux, you will need to install the
*gstreamer* (1.x) package and all the gstreamer plugins.

The following command-line switches and arguments can be used:

.. code-block:: shell

    optional arguments:
      -h, --help            show this help message and exit
      --apiport APIPORT     IPFS API port number
      --swarmport SWARMPORT
                            IPFS swarm port number
      --gatewayport GATEWAYPORT
                            IPFS http gateway port number
      --profile PROFILE     Application Profile
      --migrate             Activate automatic repository migration
      -d                    Activate debugging

Features
========

**galacteek** can either spawn an IPFS daemon and use it as transport, or
connect to an existing IPFS daemon. By default it will try to run a daemon. You
can change the IPFS connection settings through the *Edit* -> *Settings* menu
and restart the application afterwards.

- Browsing sessions with automatic pinning (pins every page you browse)
- Feeds (following IPNS hashes)
- File manager with drag-and-drop support
- Basic built-in media player with IPFS-stored, per-profile playlists
- Search content with the ipfs-search_ search engine
- Decentralized application development/testing with the Javascript API
  (using *window.ipfs*)

Keybindings
===========

Main window keybindings:
------------------------

- **Ctrl+t**: Open a new IPFS browsing tab
- **Ctrl+w**: Close current tab
- **Ctrl+m**: Open the IPFS hashmarks manager
- **Ctrl+f**: Open the file manager
- **Ctrl+o**: Browse IPFS path from the clipboard
- **Ctrl+e**: Explore IPFS path from the clipboard
- **Ctrl+g**: DAG view of IPFS object from the clipboard

Browser keybindings:
--------------------

- **Ctrl+b**: Bookmark current page
- **Ctrl+l**: Load an IPFS CID

IPFS views keybindings (file manager, hash views, dag viewer):
--------------------------------------------------------------

- **Ctrl+h**: Copy selected item's hash (CID) to the clipboard
- **Ctrl+p**: Copy selected item's IPFS path to the clipboard
- **Ctrl+w**: Close tab/hash view

Screenshots
===========

See the screenshots_ directory.

.. figure:: https://gitlab.com/galacteek/galacteek/raw/master/screenshots/browse-wikipedia-small.png
    :target: https://gitlab.com/galacteek/galacteek/raw/master/screenshots/browse-wikipedia.png
    :align: center
    :alt: Browsing the Wikipedia mirror over IPFS

    Browsing the Wikipedia mirror over IPFS

Platforms supported
===================

Mainly tested on Linux. The application relies heavily on quamash_ which
should work with most platforms. Things relying on HTTPs (ipfs-search engine
queries ..) might not work on Windows due to *ProactorEventLoop* being
incompatible with SSL, and manual installation of go-ipfs_ is advised on this
platform.

Donations
=========

You can find donation details in the *Donate* section of the *Help* menu in the
application's main window.

Requirements
============

- go-ipfs_ (install from dist.ipfs.io_)
- python3 >= 3.5
- qt5
- PyQt5 with QtWebEngine support
- gstreamer (on Linux) for media player support
- quamash_
- aiohttp_
- aioipfs_

License
=======

**galacteek** is offered under the GNU GPL3 license

Some of the beautiful artwork (under the Creative Commons CC-BY-SA license)
from the ipfs-logo_ project's repository is included, unchanged.

.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _aioipfs: https://gitlab.com/cipres/aioipfs
.. _quamash: https://github.com/harvimt/quamash
.. _go-ipfs: https://github.com/ipfs/go-ipfs
.. _dist.ipfs.io: https://dist.ipfs.io
.. _IPFS: https://ipfs.io
.. _ipfs-logo: https://github.com/ipfs/logo
.. _cxFreeze: https://anthony-tuininga.github.io/cx_Freeze/
.. _screenshots: https://gitlab.com/galacteek/galacteek/tree/master/screenshots
.. _ipfs-search: https://ipfs-search.com
