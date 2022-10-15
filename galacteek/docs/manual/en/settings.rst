
Application settings
====================

.. image:: ../../../../share/icons/settings.png
    :width: 64
    :height: 64

IPFS settings
-------------

The application can either spawn a local IPFS daemon (this is the default) or let
you use an IPFS daemon to which you already have access.

If the IPFS daemon cannot be started, it is possible that one of the listening
ports (API, swarm or HTTP gateway) is already being used on your system. In
that case, change the ports configuration in the settings and restart the
application.

The **Minimum swarm connections** and **Maximum swarm connections** settings
let you modify the number of connections to be used for the IPFS swarm.
Using low values can significantly reduce CPU usage.

The **Maximum storage** setting controls the maximum allowed IPFS repository
size in gigabytes.

The **Routing mode** setting lets you choose between *dht* (the default)
or *dhtclient*.  Using *dhtclient* can significantly reduce CPU usage, but
your node will not act as a full :term:`DHT` node on the network.

The **Pubsub routing** setting lets you choose the pubsub routing protocol.
The *gossipsub* protocol is potentially more bandwidth-efficient than
floodsub and is backwards-compatible with the default *floodsub* protocol.

The **IPNS over pubsub** setting enables the publishing of IPNS records
over pubsub. This is an experimental feature.

Checking the **Filestore** setting will enable the use of the
IPFS filestore system when importing content from the filemanager.
Using this feature means you can add content to IPFS without
duplicating the content in the IPFS datastore. **Note**: this
is an experimental feature.

If you use the **Keep IPFS daemon running** setting, the IPFS daemon
will not be stopped when you exit galacteek and therefore others
can still access the content stored on your node. This also saves
time on startup.

**Note**: switching from a local to custom daemon (or vice versa) will make you
lose access to the content that you might have published using the previous
settings, so use with care. Use separate *application profiles* with the
**--profile** command-line switch to keep multiple separate profiles.

Browser settings
----------------

Native GPU memory buffers
^^^^^^^^^^^^^^^^^^^^^^^^^

Native video card memory buffers.

GPU rasterization
^^^^^^^^^^^^^^^^^

Enables the use of the video card processor for rasterization.

Dark Mode
^^^^^^^^^

This setting enables or disables the use of a dark theme in all
browsing tabs.

BitMessage settings
-------------------

By default the BitMessage service is enabled. From the settings you can
enable or disable the messenger service, and set the default *nice*
process priority.

Configuration editor
--------------------

You can use the configuration editor to tune the application's
configuration more finely (the settings dialog only shows
basic settings). From the *Information* menu, select
*Config editor* to open it.

The configuration is separated by module. See the **Config settings**
section below for more infos.

**Do not change any settings you are unsure about**

User interface settings
-----------------------

Enable navigation history
^^^^^^^^^^^^^^^^^^^^^^^^^

If enabled, visited dweb URLs are recorded and you will get
history search results when typing an URL.

This is *disabled* by default.

Default web profile
^^^^^^^^^^^^^^^^^^^

With this setting you can select which web profile you want enabled
by default when you open a browser tab. This setting is set by
default to *ipfs*. If you want the IPFS Javascript API always
enabled you should select *ipfs* here, or *web3* if you want both
the IPFS and Ethereum API enabled.

When the browser needs the JS API to render a page it will
automatically use at least the *ipfs* profile (if *minimal* or
another profile is the default).

Config settings
===============

This is a list of settings you can change in the config editor.

IPFS
----

For **IPFS settings**, go to the **galacteek.ipfs** module in the editor.

Peering with content providers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can choose to activate direct *peering* with different IPFS content
providers like Pinata, Cloudfare, Textile ..

- **peering.contentProvidersDb.use.cloudfare**: Peer with Cloudfare nodes
- **peering.contentProvidersDb.use.pinataNyc**: Peer with Pinata nodes (NYC)
- **peering.contentProvidersDb.use.pinataFra**: Peer with Pinata nodes (FR)
- **peering.contentProvidersDb.use.textile**: Peer with Textile nodes
- **peering.contentProvidersDb.use.protocolLabs**: Peer with ProtocolLabs
  nodes
- **peering.contentProvidersDb.use.protocolLabsNft**: Peer with ProtocolLabs
  nodes (NFT)
