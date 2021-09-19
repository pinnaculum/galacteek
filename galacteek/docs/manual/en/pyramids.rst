.. _pyramids:

Pyramids
========

.. image:: ../../../../share/icons/pyramid-blue.png
    :width: 64
    :height: 64

Pyramids are a way to give a unique address on the
network to content that you are regularly updating.

It could be a website you're working on, a blog,
a code repository, a distributed web app that you want
to share with the world.

Basic pyramid
=============

The basic pyramid can be seen as a simple stack of IPFS objects,
with the top of the pyramid automatically associated with the
pyramid's IPNS key.  Just share the IPNS address with whoever
you want so that they can always access the latest content.

This pyramid type has no DAG associated to it (it just keeps
a history of what you throw at it).

Usage
-----

From the pyramids toolbar (at the bottom), click on the blue pyramid button
and then select *Add: dynamic content*. After entering the
different parameters and validating the dialog, you will
see your new pyramid appear in the right toolbar.

Updating the pyramid works by drag-and-dropping
IPFS objects on the pyramid (from the filemanager, browser,
ipfssearch results ...).  Just drag-and-drop a valid IPFS object
on the pyramid's button and this object will be at the top of the
stack and will be published to the pyramid's :term:`IPNS` key.

You can also add the current clipboard item to the pyramid, by using
the *Add current clipboard item to the pyramid* action in the pyramid's
menu. From the filemanager and the editor, you can easily transfer
objects to a pyramid.

From the pyramid's menu you can also copy the IPNS address of the pyramid,
as well as create a QR code image for the IPNS key.

Filesystem synchronizer
=======================

This type of pyramid will automatically synchronize to IPFS a file or
directory that you choose when you create the pyramid. Whenever
the contents of that file/directory changes, it will be
reimported to IPFS and associated with the IPNS key.

Usage
-----

From the right toolbar, click on the blue pyramid button
and then select *Create filesystem synchronizer*. Select the file
or directory that you want to automatically sync.
You can choose if you want to import *hidden* files, and
select the delay (in seconds) after which the autosync
will start when some changes are detected.

If you are synchronizing a folder, you can use a
*.gitignore* file at the folder's root to specify rules
to ignore certain files.

When enabling the *Filestore* option, the import will use
the IPFS *filestore* storage if available on this IPFS
daemon, to avoid file duplication.

*Note*: As explained in Qt's documentation, the act of monitoring
files and directories for modifications consumes system resources.
This implies there is a limit to the number of files and directories
your process can monitor simultaneously. On Linux you can modify
the maximum number of *inotify user watches* with the command
**sysctl fs.inotify.max_user_watches=<num>**

Dwebsite
========

If you want to build a simple website that you can
easily edit with a text editor, click on the *blue pyramid*
and select *Create: dwebsite*.

Usage
-----

After creating a *dwebsite* the default website will be generated.
Click on its icon and select *Open* to view it.

To edit the website, just click on the pyramid and select *Edit*,
which will open the text editor, from which you can modify the
structure of your website.

Your web pages are in the *docs* folder (the default *page*
is called *index*), and they have an *.md* file suffix (they are
formatted in *Markdown*). To edit a page from the editor,
just *double-click* in the filesystem tree on the page you wish
to edit. After you made your changes, click on the *Save* icon.
Note that this only writes the contents of the page, but does
not update your website.

Updating your website
^^^^^^^^^^^^^^^^^^^^^

After saving, above the text editor zone, you will see a
new entry appear in the *editing history*. To **update** your
*dwebsite*, click on the *blue pyramid icon* and then select
your website from the list (there should only be one).

For more information on how to use MKDocs please consult the
`MKDocs user guide <https://www.mkdocs.org/user-guide/writing-your-docs/>`_

Publishing
^^^^^^^^^^

Selecting *Publish* from the pyramid menu will publish
your *dwebsite* and attach it to your *identity* (DID).
Others will see your website in the services list.

Configuration
-------------

The configuration of your *dwebsite* is done with the
*mkdocs.yml* file, which is in the *YAML* format.

Website name
^^^^^^^^^^^^

Change the name of your website using the **site_name**
configuration variable.

Theme
^^^^^

Change the theme using the **theme** configuration variable.
You can use any of the following themes::

    cerulean
    cosmo
    cyborg
    darkly
    flatly
    journal
    litera
    lumen
    lux
    materia
    minty
    pulse
    sandstone
    simplex
    slate
    solar
    spacelab
    superhero
    united
    yeti

Check `this page <https://mkdocs.github.io/mkdocs-bootswatch/>`_
to see screenshots of the themes.

Gems
====

You can easily create Gemini_ websites (*capsules*) in galacteek.

Click on the *blue pyramid* and select *Create: gem*. This will create
an empty Gemini_ capsule in IPFS.

Now in the pyramids toolbar click on your newly created capsule and
select *Edit*. From the editor you will be able to edit and create new
gemini pages (gemini files use the *.gmi* suffix). The default index file is
called *index.gmi*.

Make your changes and save. Once saved, click on the blue pyramid in the
editor and send the changes to your pyramid. This will upgrade the capsule
to the new version. You can also create files and directories in the editor
by right-clicking in the folder view.

**Until you publish your capsule to your DID, you won't be able to
access it from the browser. Once you're ready click on the capsule
and hit Publish.**

**Once published, click on the capsule and select Access Gemini Capsule**

**You can also go to the Peers workspace and double-click on your DID.
The capsule will appear in the gems section**

Gemini IPFS capsules in *galacteek* are accessed via a specific URL
scheme called **gem**, URLS use this format (*PeerID* and *capsule name*)::

    gem:/12D3KooWQWcGx8jrWNPFRPpmd1ywXu612ShBkFGvmr7UBexzKTSk/mygem

Syntax
------

Gemini_ uses a very lightweight markup language called *gemtext*.

Links are created by using the **=>** markup on a single line.

Checkout the gemtext_ page and `the gemtext cheatsheet <https://gemini.circumlunar.space/docs/cheatsheet.gmi>`_ as well to understand how to easily write
content in your gemini capsules.

DAG building pyramids
=====================

These types of pyramids have a :term:`DAG` associated to them.
The pyramid's :term:`IPNS` key is always matching the latest
version of the DAG.

Image gallery
-------------

This is a simple application to demonstrate the power and
simplicity of the DAG API in IPFS.
Just drag-and-drop images from the filemanager on the pyramid
and they will be added to the image gallery.

You can also drag-and-drop images from web pages.

You can browse the gallery directly or through the IPNS address.

From the pyramid's menu you can change the gallery's title,
or rewind the DAG. Rewinding the DAG cancels the latest
DAG operation (for example if you've added an image that
you now want to remove, just rewind the DAG once, and
the DAG will be restored to the previous object in the history).

IPNS records
============

To ensure that the :term:`IPNS` records are maintained
you can leave the application running (closing the main window
will minimize the app to the system tray).


.. _MKDocs: https://www.mkdocs.org/
.. _Gemini: https://gemini.circumlunar.space/
.. _gemtext: https://gemini.circumlunar.space/docs/gemtext.gmi
