.. _qrcodes:

Support for QR codes
====================

.. image:: ../../../../share/icons/ipfs-qrcode.png
    :width: 64
    :height: 64

There is experimental support for encoding and reading QR codes
containing references to IPFS-hosted content. To be able to use
the QR features, you need to install the **zbar** library on your
system (on Linux/BSD systems it is widely available, on MacOS you
can install it with **brew install zbar**).

In the filemanager you can access all your QR codes from the
**QR codes** folder, which contains some QR sample files by
default.

In the image viewer
-------------------

When opening an image containing IPFS QR codes, the image viewer
will display a special section below the image. For each IPFS
object found in the image, its path will be displayed, as well as
buttons to open the object and copy its path to the clipboard.

In the clipboard manager
------------------------

If a clipboard item is an image containing QR codes, a special
*IPFS QR codes* menu will be displayed in the clipboard item's menu.
From this menu you can open each individual object.

Encoding the clipboard stack
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The clipboard manager's *QR encoding* menu gives you the possibility
to QR-encode all the IPFS objects of the current clipboard stack to
a single image (RSA self-encrypted or clear). Later on the software
could provide the possibility to send QR images encrypted for
specific peers.

The *clear* QR images are not encrypted, and are not immediately
announced on the network (they are added to the repository with
the *offline* option). You can announce them later on when you
want to.

The resulting images can be found in the **QR codes** folder in
the filemanager (the RSA-encrypted images are stored in the
*encrypted* subfolder).

In the browser
--------------

If the page you're browsing contains an image that contains
IPFS QR codes, right-clicking on it will show an *IPFS QR codes*
menu similar to the one displayed in the clipboard manager.

Encoding a pyramid's IPNS key
-----------------------------

The IPNS key of your multihash pyramids can be QR-encoded. Right-click
a pyramid and select *Generate pyramid's QR code* (the generated
image's filename will contain the IPNS key id).
