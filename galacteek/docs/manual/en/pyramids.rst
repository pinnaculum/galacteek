.. _pyramids:

Pyramids
========

.. image:: ../../../../share/icons/pyramid-blue.png
    :width: 64
    :height: 64

Pyramids are a way to give a unique address on the
network to content that you are regularly updating. It could be a
website you're working on, a blog, a code repository, a distributed
web app that you want to share with the world without the hassle of
distributing the new cryptographic identifiers of your work
every time you're making some changes.

To ensure that the :term:`IPNS` records are maintained you can leave the
application running (closing the main window will minimize the app
to the system tray).

Basic pyramid
-------------

The basic pyramid can be seen as a simple stack of IPFS objects,
with the top of the pyramid automatically associated with the
pyramid's IPNS key.  Just share the IPNS address with whoever
you want so that they can always access the latest content.

This pyramid type has no DAG associated to it (it just keeps
a history of what you throw at it).

Usage
^^^^^

From the right toolbar, click on the blue pyramid button
and then select *Create pyramid (basic)*. After entering the
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

Auto-sync pyramid
-----------------

This type of pyramid will automatically synchronize to IPFS a file or
directory that you choose when you create the pyramid. Whenever
the contents of that file/directory changes, it will be
reimported to IPFS and associated with the IPNS key.

Usage
^^^^^

From the right toolbar, click on the blue pyramid button
and then select *Create auto-sync pyramid*. Select the file
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

MKDocs website
--------------

MKDocs_ is a fast, simple and downright gorgeous static site
generator that's geared towards building project documentation.
Documentation source files are written in Markdown, and configured
with a single YAML configuration file.

Although it's geared towards documentation projects, you can use MKDocs
to build any type of website (including blogs) thanks to its plugin
system and the power of Markdown.

Usage
^^^^^

After creating an MKDocs pyramid the default website will be generated.
To edit the website, just click on the pyramid and select *Edit input*,
which will open the text editor, from which you can modify the
structure of the MKDocs project. Once you have made changes to the
project and want to update your website, use the pyramid drop button
in the editor to push the new version, and the website will be
automatically regenerated.

For more information on how to use MKDocs please consult the
`MKDocs user guide <https://www.mkdocs.org/user-guide/writing-your-docs/>`_

DAG building pyramids
---------------------

These types of pyramids have a :term:`DAG` associated to them.
The pyramid's :term:`IPNS` key is always matching the latest
version of the DAG.

Image gallery
^^^^^^^^^^^^^

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


.. _MKDocs: https://www.mkdocs.org/
