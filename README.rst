Galacteek
=========

A modest IPFS_ navigator and file manager

Installation
============

You need python 3.5 and pip installed. Install with:

.. code-block:: shell

    pip install -r requirements.txt
    python setup.py build install

Now just run the application with:

.. code-block:: shell

    galacteek

Keybindings
===========

Default keybindings:

- Ctrl+t: Open a new tab
- Ctrl+w: Close current tab
- Ctrl+m: Opens bookmarks

In-browser bindings:

- Ctrl+B: Bookmarks current page

Screenshots
===========

.. image:: https://gitlab.com/cipres/galacteek/raw/927819fb2b6694c2dd6a93c12131aea9042fa94b/screenshots/filesview.png
    :target: https://gitlab.com/cipres/galacteek/blob/927819fb2b6694c2dd6a93c12131aea9042fa94b/screenshots/filesview.png

Platforms supported
===================

This has been mainly tested on Linux but should work on other systems
as well where python and qt5 is available.

Requirements
============

- go-ipfs_ (install from dist.ipfs.io_)
- python3 >= 3.5
- qt5 (i use version 5.10 but it should work with earlier versions)
- PyQt5 with QtWebEngine support
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

**galacteek** is offered under the GNU Affero GPL3 license with no guarantees
whatsoever :-)
