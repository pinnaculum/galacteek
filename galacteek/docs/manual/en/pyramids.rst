.. _pyramids:

Pyramids
========

.. image:: ../../../../share/icons/pyramid-blue.png
    :width: 64
    :height: 64

*galacteek* uses pyramids, which allow you to publish
content dynamically on the distributed web. Pyramids
maintain a history of the content you add to them,
and they have a unique address (see :term:`IPNS`) on the network,
always pointing to the latest content (the *pyramidion*).
Pyramids can be created from the **blue** pyramid button
located in the sidebar.

There are various types of pyramids, as each pyramid
type uses a specific framework or technology to produce
its output, and requires a certain format of input (for
example, a *hugo pyramid* requires a hugo website source folder
containing Markdown files).

Pyramids can be published to your :term:`DID` as a DID service
(see :term:`DID services`). Other peers on the network will then
be able to access your pyramid by discovering the service in the list
of services attached to your DID (from the *peers* workspace), or by
directly using the pyramid's IPNS/IPFS address.

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

Hugo
====

Hugo_ is an excellent open-source static website generator. It is
very easy to publish a website generated by Hugo to IPFS. *galacteek*
makes it possible to create and manage a Hugo website with the text
editor.

To create a website with Hugo, click on the blue pyramid and select
*Create: hugo website*. Specify the site's title and change the default
content language if necessary. After validating, an empty website
will be generated.

To create a new post, click on the icon of your website in the toolbar
and select *Hugo: write new post*. It will open the text editor, with a dialog
for the post's title and other metadata. You will need to write the
content of the post in the Markdown format. Once you've saved your
post, just publish it to the pyramid and the website will be rebuilt.

Hugo is a well documented feature-rich software, see 
`the documentation here <https://gohugo.io/documentation/>`_.
All custom tuning that you wish to do on your website will
have to be done in the text editor.

Hugo themes
-----------

You can change the theme of your hugo website from your pyramid's menu.
Click on your pyramid and open the *Hugo: change theme* menu. Click on
one of the themes in the list to change your website's theme. The
theme's zip file will be downloaded and the site is then rebuilt, you should
hear a sound notification when it has been updated.

*Note*: the installed themes are **not automatically removed**. If you are
trying out different themes, this will use more space in IPFS and will
make the pyramid's building process slower. Once you're satisfied with
the theme, you can remove the unused themes by editing the site: in the
pyramid, select *Edit*, then open the *themes* directory, and for each
theme you don't use, right-click on the theme's folder and select *Delete*,
then *Save* and publish to the pyramid.

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
scheme called **gemi**, URLS use this format (*PeerID* and *capsule name*)::

    gemi:/12D3KooWQWcGx8jrWNPFRPpmd1ywXu612ShBkFGvmr7UBexzKTSk/mygem

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
.. _Hugo: https://gohugo.io
