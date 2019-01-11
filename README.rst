
=========
Galacteek
=========

.. image:: https://gitlab.com/galacteek/galacteek/raw/master/share/icons/galacteek.png
    :align: center

:info: An async IPFS_ browser

**galacteek** is an experimental Qt5-based browser/toolbox
for the IPFS_ peer-to-peer network.

Installation
============

AppImage
--------

For Linux users (arch: *x86_64*), you can get an AppImage directly from IPFS
`here <https://ipfs.io/ipfs/Qme23PGVzjK37uTQGJ221Jb5QAAgvicrBPfMi5mcDAd8LV>`_
(**~138Mb**, release CID: **Qme23PGVzjK37uTQGJ221Jb5QAAgvicrBPfMi5mcDAd8LV**).

Just fetch the image (with wget for example or your favorite tool), and execute
it afterwards::

    wget https://ipfs.io/ipfs/Qme23PGVzjK37uTQGJ221Jb5QAAgvicrBPfMi5mcDAd8LV
    chmod u+x Qme23PGVzjK37uTQGJ221Jb5QAAgvicrBPfMi5mcDAd8LV
    ./Qme23PGVzjK37uTQGJ221Jb5QAAgvicrBPfMi5mcDAd8LV

Running the AppImage with the filename unchanged means that the
application will automatically pin itself (it will pin through IPFS the
AppImage that you are using). By doing so you can help redistributing the
software faster to the nodes close to you. Renaming the binary disables the
self-seeding feature::

    mv Qme23PGVzjK37uTQGJ221Jb5QAAgvicrBPfMi5mcDAd8LV Galacteek-0.3.2.AppImage

*Note*: go-ipfs_ version *0.4.18* is included in the AppImage.

PIP
---

You need to have python>=3.5 (python>=3.6 is recommended) and pip installed,
as well as go-ipfs_. From a virtualenv, or as root, install with:

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
if you want to automatically download and install it from dist.ipfs.io_
You need a recent version of go-ipfs_ (> 0.4.7) with the new DAG API.

For the media player to work on Linux, you will need to install the
*gstreamer* (1.x) package and all the gstreamer plugins.

Command-line usage
==================

Use the *-d* command-line switch to enable debugging. Using *--profile* gives
you the ability to have separate application profiles (*main* is the default
profile). Use *--help* for all options.

*Development*: Use *--monitor* to enable event-loop monitoring with aiomonitor_
(install aiomonitor_ manually as it's not a dependency).
Then connect to the aiomonitor_ interface with **nc localhost 50101**

Features
========

**galacteek** can either spawn an IPFS daemon and use it as transport, or
connect to an existing IPFS daemon. By default it will try to run a daemon. You
can change the IPFS connection settings through the *Edit* -> *Settings* menu
and restart the application afterwards.

- Browsing sessions with automatic pinning (pins every page you browse)
- Feeds (following IPNS hashes)
- File manager with drag-and-drop support
- Basic built-in media player with IPFS-stored playlists
- Search content with the ipfs-search_ search engine
- Decentralized application development/testing with the Javascript API
  (using *window.ipfs*)

.. include:: galacteek/docs/manual/en/shortcuts.rst

Keyboard shortcuts
==================

Main window keyboard shortcuts
------------------------------

- **Ctrl + t**: Open a new IPFS browsing tab
- **Ctrl + s**: Search with ipfs-search
- **Ctrl + w**: Close current tab
- **Ctrl + m**: Open the IPFS hashmarks manager
- **Ctrl + f**: Open the file manager
- **Ctrl + o**: Browse IPFS path from the clipboard
- **Ctrl + e**: Explore IPFS path from the clipboard
- **Ctrl + g**: DAG view of IPFS object from the clipboard
- **Ctrl + p**: Pin IPFS object from the clipboard
- **Ctrl + i**: Open the IPLD explorer for the IPFS object referenced in the
  clipboard

Browser keyboard shortcuts
--------------------------

- **Ctrl + b**: Bookmark current page
- **Ctrl + l**: Load an IPFS CID
- **Ctrl + r** or **F5**: Reload the current page
- **Ctrl + +**: Zoom in
- **Ctrl + -**: Zoom out

IPFS views keyboard shortcuts (file manager, hash views, dag viewer)
--------------------------------------------------------------------

- **Ctrl + h**: Copy selected item's hash (CID) to the clipboard
- **Ctrl + p**: Copy selected item's IPFS path to the clipboard
- **Ctrl + w**: Close tab/hash view

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
should work with most platforms (untested on OS X which is not officially
supported by quamash).

Donations
=========

BTC: 3HSsNcwzkiWGu6wB18BC6D37JHExpxZvyS

You can also find donations details in the application's information menu.

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
.. _cxFreeze: https://anthony-tuininga.github.io/cx_Freeze/
.. _screenshots: https://gitlab.com/galacteek/galacteek/tree/master/screenshots
.. _ipfs-search: https://ipfs-search.com
.. _releases: https://github.com/eversum/galacteek/releases
.. _srip: https://www.flaticon.com/authors/srip
