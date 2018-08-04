Galacteek
=========

A modest IPFS_ browser

This is a standalone browser allowing you to search, browse, publish and
hashmark content on the permanent web accessible through the IPFS_ peer-to-peer
network.

Installation
============

Installation from source
------------------------

You need to have python 3.5 and pip installed, as well as go-ipfs_. Install with:

.. code-block:: shell

    pip install -r requirements.txt
    python setup.py build install

Now just run the application with:

.. code-block:: shell

    galacteek

Installation from binary
------------------------

Binary releases are only available for Linux AMD64 (also known as
*x86-64* or *x64*) platforms. They include the *0.4.15* release of go-ipfs_
and are built from the *master* branch with cxFreeze_. It's always preferable
to build from source and depending on the distribution you use you might run
into dependency problems with the binaries.

If you already have IPFS installed on your system you can download the latest
binary release with:

.. code-block:: shell

    ipfs get /ipfs/QmVrhsZHwLXhqpqZ8ggXggEax4Qoa4646FMBQTqitXPThL/galacteek-0.1.8-linux-amd64.tar.gz
    tar -xzvf galacteek-0.1.8-linux-amd64.tar.gz

Just go into the unpacked directory and run the **galacteek** program.

If you don't have IPFS installed on your system you can download the same file
here_

.. _here: https://gateway.ipfs.io/ipfs/QmVrhsZHwLXhqpqZ8ggXggEax4Qoa4646FMBQTqitXPThL/galacteek-0.1.8-linux-amd64.tar.gz

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

Platforms supported
===================

This has been only tested on Linux but should work on other systems
as well where python and qt5 are available.

Contact and donations
=====================

Contact by email at **galacteek@gmx.co.uk**

Donations are welcome and will go to other projects like ipfs-search_.
You can make a donation to the project with Monero to this monero address:

**48oNcgpqwUNWjHeTSSH8BCaJHMR7Bc8ooGY13USYxuMuGwtXfLQ1Qf9f7rJMB9g1PWELee2cNnTWz1rJiZyPigcXRCTkhU3**

or with Bitcoin here: **3HSsNcwzkiWGu6wB18BC6D37JHExpxZvyS**

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
