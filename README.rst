
.. image:: https://gitlab.com/galacteek/galacteek/raw/master/share/icons/galacteek.png
    :align: center
    :width: 128
    :height: 128

:info: A multi-platform IPFS_ browser

**galacteek** is an experimental multi-platform Qt5-based browser/toolbox
for the IPFS_ peer-to-peer network.

Platforms supported
===================

- Linux (main target)
- FreeBSD (or any BSD OS, as long as you have PyCryptodome)
- MacOS (*experimental*)

If it works for you, great, but most likely it won't :)
This started as an experiment with quamash_ and is WIP.

If you want to donate to this project please use the
`Patreon page <https://www.patreon.com/galacteek>`_

Installation
============

On Linux systems you can use the AppImage (from the releases_ page)
or install from PyPI. On MacOS and other systems you'll need to
install from PyPI.

PyPI
----

You need to have python>=3.6 and pip installed.
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
if you want to automatically download it from dist.ipfs.io_
You need a recent version of go-ipfs_ (> 0.4.7) with the new DAG API.

For the media player to work on Linux, you will need to install the
*gstreamer* (1.x) package and all the gstreamer plugins.

There is experimental support for reading QR codes containing IPFS addresses,
using pyzbar_. pyzbar_ depends on the zbar shared library,
so make sure it's installed on your system (on Linux look for a libzbar or
libzbar0 package and install it, on MacOS install it with
**brew install zbar**).

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

URL schemes
===========

dweb:/
------

Right now the application relies on the *dweb:/* URL scheme. We are
using CIDv1 by default for all content. Starting with go-ipfs_ version
0.4.21, objects using CIDv1 are in base32 by default, creating the
possibility to integrate other URL schemes (like *ipfs://<cidv1-base32>*)
that will treat the CID as the authority. Work is being done to
integrate such schemes in the browser and make it the default.

ens://
------

There is support for accessing IPFS-hosted websites that are registered
on Ethereum Name Service (see ENS_). Just use **ens://mydomain.eth** for example
as a URL in the browser and you will be redirected to the IPFS website
referenced on ENS for this domain.

`On this dweb page <dweb:/ipfs/QmdjGyE5axZcCRorALntbqrr6TFdr7ik2kwKiUxY1tELSh/ens+ipfs/list-of_ENSIPFS-websites.html>`_
you can find a list of some ENS+IPFS websites (or with **ens://blog.almonit.eth**)

Features
========

**galacteek** can either spawn an IPFS daemon and use it as transport, or
connect to an existing IPFS daemon. By default it will try to run a daemon. You
can change the IPFS connection settings by clicking on the settings icon in the
toolbar and restart the application afterwards. If using a custom daemon, you
should enable pubsub or some features won't be available.

- Browsing sessions with automatic pinning (pins every page you browse)
- File manager with drag-and-drop support
- Following IPNS hashes
- ENS_ (Ethereum Name System) resolving (access to ENS+IPFS websites)
- Sharing hashmarks over pubsub
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

- python3 >= 3.6
- go-ipfs_ >= 0.4.7
- PyQt5 >= 5.12.2
- PyQtWebengine >= 5.12
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
.. _ENS: https://ens.domains/
