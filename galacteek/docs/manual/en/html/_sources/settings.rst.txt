
Application settings
====================

The **Edit** -> **Settings** dialog lets you change the application settings.

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
your node will not act as a full DHT node on the network.

**Note**: switching from a local to custom daemon (or vice versa) will make you
lose access to the content that you might have published using the previous
settings, so use with care. Use separate *application profiles* with the
**--profile** command-line switch to keep multiple separate profiles.

User interface settings
-----------------------

Hide hashes
^^^^^^^^^^^

This will hide the IPFS hashes wherever possible (file manager, explorer..)

Wrap single files or directories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If enabled, files or directories will be wrapped within a directory object
(.dirw)

Activate Javascript IPFS API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With this setting you can activate the Javascript API in the browser, allowing
control of your IPFS daemon from the Javascript engine. Access to the IPFS
daemon is done through the **window.ipfs** JavaScript variable.
