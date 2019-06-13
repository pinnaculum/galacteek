.. _hashmarks:

Hashmarks
=========

Hashmarks are bookmarks for IPFS objects (that can be links to
directories, webpages, documents, text files, ...). Hashmarks
are referenced by the full IPFS path of the object and can contain
*fragments*.  These are all valid paths for hashmarks::

    /ipfs/zdj7WazZDaMUSua3wCKgjPAj9bZXbh2EMUHzFTEmHh1BUs2uH
    /ipfs/zdj7WazZDaMUSua3wCKgjPAj9bZXbh2EMUHzFTEmHh1BUs2uH/settings.html
    /ipfs/zdj7WazZDaMUSua3wCKgjPAj9bZXbh2EMUHzFTEmHh1BUs2uH/settings.html#ipfs-settings
    /ipns/dist.ipfs.io/favicon.ico

You can create hashmarks from many places, like in a browser tab,
or from the filemanager.

Pressing **Ctrl+b** from the browser will hashmark the current
page if it's a valid IPFS object. From the clipboard manager
you can create hashmarks as well, by opening the menu of the
clipboard item of your choice and clicking on the *Hashmark* action.

Hashmarks are given a category, a title, description and icon (that
will be stored within IPFS). Flagging a hashmark as *shared* means
that it will be shared on the network with other peers (off by default).
Received hashmarks are RSA-encrypted in your IPFS repository with
your profile's RSA key.

Local Hashmarks menu
--------------------

.. image:: ../../../../share/icons/hashmarks.png
    :width: 64
    :height: 64

From the toolbar, clicking on the hashmarks icon opens a menu
giving access to all your local hashmarks, by category.

Clicking an item will trigger the opening of the corresponding
resource, depending on its type (the file type of the resource
is automatically detected and cached by the application). There
are built-in viewers/renderers for things like text files,
images, multimedia files etc.. For files that cannot be
rendered by the application (for example PDF files), the system's
default application will be used to open the file.

Shared Hashmarks menu
---------------------

.. image:: ../../../../share/icons/hashmarks-library.png
    :width: 64
    :height: 64

This menu shows the hashmarks that have been received on the
network from other peers.

Following IPNS keys
===================

There is basic support for following IPNS names/keys. When browsing
a root IPNS URL (e.g **/ipns/awesome.ipfs.io**), open the IPFS CID
menu on the left, and click on **Follow IPNS resource**).

The IPNS name or key will be periodically resolved (the resolve frequency
is configurable). The resolved entries are added as hashmarks inside
the IPNS feed and can be browsed from the hashmarks manager.
