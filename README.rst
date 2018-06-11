Galacteek
=========

A modest IPFS_ navigator and content publisher

Installation
============

You need to have python 3.5 and pip installed, as well as go-ipfs_. Install with:

.. code-block:: shell

    pip install -r requirements.txt
    python setup.py build install

Now just run the application with:

.. code-block:: shell

    galacteek

**galacteek** can either spawn an IPFS daemon and use it as transport, or
connect to an existing IPFS daemon. By default it will try to run a daemon. You
can change the IPFS connection settings through the *Edit* -> *Settings* menu
and restart the application afterwards.

Features
========

- IPFS hashmarks sharable through IPFS pubsub channels (*experimental*)
- Browsing sessions with automatic pinning (pins every page you browse)
- Feeds (following IPNS hashes)
- File manager with drag-and-drop support
- Basic built-in media player with IPFS-stored, per-profile playlists

Keybindings
===========

Main window keybindings:
------------------------

- *Ctrl+t*: Open a new IPFS browsing tab
- *Ctrl+w*: Close current tab
- *Ctrl+m*: Open the IPFS marks manager
- *Ctrl+f*: Open the file manager
- *Ctrl+o*: Browse IPFS path from the clipboard
- *Ctrl+e*: Explore IPFS path from the clipboard

Browser keybindings:
--------------------

- *Ctrl+b*: Bookmark current page
- *Ctrl+l*: Load an IPFS CID

IPFS views keybindings (file manager, hash views):
--------------------------------------------------

- *Ctrl+h*: Copy selected item's hash (CID) to the clipboard
- *Ctrl+p*: Copy selected item's IPFS path to the clipboard
- *Ctrl+w*: Close tab/hash view

Platforms supported
===================

This has been mainly tested on Linux but should work on other systems
as well where python and qt5 are available.

Contact
=======

Contact by email at galacteek@gmx.co.uk

Requirements
============

- go-ipfs_ (install from dist.ipfs.io_)
- python3 >= 3.5
- qt5 (preferrably >5.6)
- PyQt5 with QtWebEngine support
- gstreamer (on Linux) for media player support
- quamash_
- aiohttp_
- aioipfs_

.. _aiohttp: https://pypi.python.org/pypi/aiohttp
.. _aioipfs: https://gitlab.com/cipres/aioipfs
.. _quamash: https://github.com/harvimt/quamash
.. _go-ipfs: https://github.com/ipfs/go-ipfs
.. _dist.ipfs.io: https://dist.ipfs.io
.. _IPFS: https://ipfs.io

License
=======

**galacteek** is offered under the GNU GPL3 license
