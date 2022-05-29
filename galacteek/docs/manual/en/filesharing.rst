.. _sharing:

Sharing files
=============

**This module is disabled at the moment**

From the files workspace you can easily share files on
the network.

In the top-left toolbar you'll see a round icon:

.. image:: ../../../../share/icons/fileshare.png
    :width: 64
    :height: 64

You'll be prompted with a dialog, which will create a
**seed** on the network. Now all you have to do
is drag files from your filemanager and drop them inside this
dialog.

You can store as many files/directories as you want
in the seed (but be reasonable). For each file you can
specify the pin request parameters (how many peers you'd want
to pin this file).

You can also add a file from the clipboard by clicking on
the clipboard button (the current clipboard item will be used).

Once you're ready enter the **Seed name** and **description**.
When people search for files it is matched against the seed name,
so choose something appropriate.

Hit **OK** and the seed will be created, and instantly available
for others.

Searching
=========

There's a tab called **File sharing** in the files workspace.
From here you can search for files shared by others.

Click on a file you'd like to fetch in the search results.
On the far-right there's a combobox with the following options:

- **Pin**: will pin all the files in the seed
- **Pin and download**: will pin all the files, and download them in
  your Downloads directory (in the **seeds** subfolder)
- **Download only**: don't pin, but download the files
