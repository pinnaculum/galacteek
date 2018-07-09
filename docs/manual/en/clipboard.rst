
Using the clipboard
===================

By their very nature, IPFS hashes are difficult to remember. It becomes
quite convenient to store those valuable hashes in a temporary place, and the
system's clipboard is a convenient buffer that will help you keep track of
these.

On Linux systems, the **selection** clipboard will always be used as the
primary clipboard, while on other platforms the system's clipboard will be
used.

The clipboard loader
--------------------

.. image:: ../../../share/icons/clipboard.png
    :width: 64
    :height: 64

On the top-right corner of the window sits the clipboard loader button. It records
the computer's clipboard activity and keeps an history of all the IPFS hashes
that have been stored in it since the application was started.

Clicking on the arrow next to the clipboard icon will open a menu giving you
access to the clipboard's history as well as actions to browse/explore the IPFS
resource currently referenced in the clipboard, if any.

It recognizes the following formats:

- *IPFS CID (version 0)*, for example
  **QmRifA98t769dzkDv2gQocqJPXGtTySR5dPkyTaUZXtkLo**
- *IPFS CID (version 1)*, for example
  **zb2rhd4c97sLJwmnVvUjW5movikNJaYBMfpfpGP7hktYtt8Bo**
- *IPFS path* for example
  **/ipfs/QmWzhNYvNaxz41qitbqMaTDbViFoES1NgTuoYC7dAAMJw3/src/tools** or 
  **/ipfs/QmdjTSAM2xSVsXcusNHRoES4KqkJ5mW17u6oQARTWMuWMF/CHANGES**
- *IPNS path* for example **/ipns/ipfs.io** or
  **/ipns/Qmef8KSNLZZfdnrxHZKhCBBynSUFLQ4RrH88wW3sTWxfwB**
- *URLs using the fs: or ipfs: scheme* for example
  **fs:/ipfs/QmRifA98t769dzkDv2gQocqJPXGtTySR5dPkyTaUZXtkLo**

Passing the mouse over the clipboard button will display a tooltip message
giving you information about the status of the clipboard.

Clipboard keyboard shortcuts
----------------------------

- **Ctrl+o** will browse the IPFS resource currently referenced in the
  clipboard
- **Ctrl+e** will open the explorer for the IPFS resource currently
  referenced in the clipboard
- **Ctrl+g** will open the DAG viewer for the IPFS resource currently
  referenced in the clipboard
