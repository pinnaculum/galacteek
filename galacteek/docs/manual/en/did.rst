.. _did:

Decentralized Identity
======================

.. image:: ../../../../share/icons/planets/saturn.png
    :width: 64
    :height: 64

A :term:`DID` (standing for *Decentralized Identifier*) is
*a new type of identifier for verifiable, decentralized digital
identity*.

Digital identity has always been a key aspect of Internet
interactions. The second wave of Web technology (the now
dying, so-called Web 2.0), brought tremendous
innovations, but it has failed to give netizens of the world
a true sense of control over their digital identity, leaving us in the
current state: weak control over our digital identities,
and no control over what we publish. The dweb, thanks to
the power of its protocols, erases the slavery model of
the ancient client-server paradigm.

Your thoughts matter and have value, stop being a slave,
and express yourself on the dweb freely.

Enter IPID
----------

InterPlanetary Identifiers (see IPID_) are a type of decentralized
identifiers (DID) that live in the IPFS ecosystem (the DID
document associated with an IPID identifier is stored
as a :term:`DAG` in your IPFS repository).

The identifier of your IPID is an IPNS key, which always points
to the latest version of the DID document DAG (your latest
identity). This is an example of an IPID identifier::

    did:ipid:QmSK1moUFX4k6JdmjgSWxCicZ4TMQ87oq2m9frNZo6TadQ

(DIDs always follow the format *did:method-name:method-specific-id*,
inf our case *method-name* is *ipid* and the *method-specific-id*
is the IPNS key associated with our IPID).

By using IPIDs you have immense control over your digital identities:
your identity is backed by a crypto-based Merkle tree stored
on your system.

Implementation and goals
^^^^^^^^^^^^^^^^^^^^^^^^

*Note*: IPID_ is still a recent, subject-to-changes DID specification

In the 0.4 branch of :term:`galacteek` the IPID implementation is still
in its early stages and there will be probable changes in the IPID
schema, until stabilization at the end of the 0.4 branch cycle
(at version *0.4.42*).

Some of the goals in the UI are:

- Connection-state independence over resolvability of the identities
  (even offline, you should be able to manage your contacts).

- Easy way to publish services (could be anything from a link
  to a document to a restricted chat or video service ..)

- "Muted" identities

IP Profile
----------

Your profile in **galacteek** can have as many decentralized
identities attached to it as you like.

Each identity is represented by an IP handle (Space handle) and a DID.

Your IP handle will be tied to your peer ID if you don't register
it on the blockchain, otherwise it's not peer-specific.
Examples::

    alchemist@Saturn
    noname#156@Mars/QmXcBFXy5XA5qELL8Z8GeJdeD9LWa2cWVVnkStK6Jxtvas
    dwebartist@Earth/QmVrLyye1bByJT3ktj9gRFvxibBVpxk7vXvcwEXF9hhdku

InterPlanetary services
-----------------------

You can publish services (they can be simple IPFS links, or P2P
services) on your DID.

An IP service attached to an IPID has a DID URL, for example::

    did:ipid:QmXcBFXy5XA5qELL8Z8GeJdeD9LWa2cWVVnkStK6Jxtvas/blog

This same IP service can be searched using the Space handle
of the peer, for example **macfly@Mars@...** (this service
would be represented as **macfly@Mars@VVnkStK6Jxtvas/blog**)

You can search the IP services of a peer from the main menu,
or by typing **Mod + i**. Typing a Space handle will autocomplete
and show you the IP services for that peer.

Creating DID services
---------------------

From the profile menu you can create new services. Click on the helmet
and go to the *IP services* menu.

Object collections service
^^^^^^^^^^^^^^^^^^^^^^^^^^

This type of service is a simple container of IPFS files. You can publish
files to a collection from the filemanager.

HTTP forwarding service
^^^^^^^^^^^^^^^^^^^^^^^

This DID service allows you to serve an existing HTTP website over IPFS
(via libp2p tunnels). It will be accessible through the *ipfs+http*
protocol. The *ipfs+http* protocol doesn't use domain names, but
base36-encoded IPFS PeerIDs (this makes it pretty secure, as there is
no DNS resolving involved, the URL origin being the PeerID which is
dialed directly through IPFS).

From the menu select *Add HTTP forward service*. The dialog form will ask
you for the IP address and listening port of the HTTP website you want to
use. The *public TCP port* (by default 80) is the port number for the
*ipfs+http* DID service, and is included in the URL. This means that
you can serve as many websites as you want on a single IPFS node, by using
different *public ports*.

For more infos on the *ipfs+http* protocol, look at the :ref:`browsing`
section.

.. _IPID: https://github.com/jonnycrunch/ipid
