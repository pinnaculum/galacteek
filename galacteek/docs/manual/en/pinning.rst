
Pinning content
===============

.. image:: ../../../../share/icons/pin/pin-diago-blue.png
    :width: 64
    :height: 64

The concept of *pinning* is a fundamental core feature
of the IPFS technology and the distributed web.

By default, any content you visit, unless explicitely
*pinned* to your :term:`Node`, will eventually be
purged by the :term:`garbage collector` (this is a task
routinely performed by your node), to prevent your
system from keeping track of too much stuff and thus
taking disk space.

The beauty of this technology is that it gives you true
power over this choice: which content do i want to keep
but also distribute. This is where :term:`pinning`
comes into play.

**Pinning** some content means to **actually keep it**
(*don't* let it be recycled), so that you can always *access it*
unconditionally. This implies that you'll *distribute* this
content to the peers around you, as long as it's pinned
on your machine.

This can be done, at the moment, in two different ways:

- *Pinning to your node*: The content will be pinned to the
  IPFS node on **your machine**. This means that it'll
  always be possible for you to access that content, even
  when you're *offline*. This also means that, when you are
  online, you'll be able to actively distribute that content
  to the network. However, when you're not *online*, of course
  you're not participating, you're not distributing (and it's
  your right).

- *Pinning to a remote service*: IPFS offers the possibility
  to use remote services, that will pin the content for you,
  and keep it available 24/7. This is extremely valuable in
  many cases, as you probably aren't in a situation where you
  run the software continually, or even have an internet
  connection that has decent upstream bandwidth.
  Using *a remote service* ensures that the content you
  want to be kept available, will be distributed by
  machines that have high-availability on the network and
  can serve the content to many peers.


At any moment you can decide to unpin
something, by visiting this content, and selecting *Unpin*.

Pinning in the browser
----------------------

Anywhere in the interface where there's something that can
be pinned, you'll see an active pin icon, red or blue
(choose your pill).

Locally (here)
^^^^^^^^^^^^^^

.. image:: ../../../../share/icons/pin/pin-diago-blue.png
    :width: 64
    :height: 64

The blue pin means: to pin **locally** (on your machine).

Remote (there)
^^^^^^^^^^^^^^

.. image:: ../../../../share/icons/pin/pin-diago-red.png
    :width: 64
    :height: 64

The red pin means: to pin **on a remote service**.

*These options will only be visible once you have configured
a remote pinning service. You can do that in the settings.
Please check the Remote section below*

Pinning IPFS links in a webpage
-------------------------------

If you are browsing a webpage which contains relative or absolute
IPFS links and you want to pin those objects, select *Pin page's links*
from the **PIN** button. This will scan IPFS links contained in the
current page and open a separate tab from which you can select single or
recursive pinning for each link found. Once confirmed, the selected
objects are queued for pinning.

Automatic pinning
-----------------

You can also activate the automatic pinning with the
**Automatic PIN** switch button in a tab. When it's activated,
all pages visited in this browsing session will be
automatically pinned to your IPFS node.

Global Automatic pinning
------------------------

In the application's main toolbar, next to the clipboard manager,
another switch button activates application-wide automatic pinning.
When this is enabled, all the content you visit will be pinned locally.

Pinning status
--------------

In the status bar (at the bottom of the window), the pinning status
icon gives information about the status of the pinning queues.
Clicking on it gives a list of the objects being pinned.

Remote
======

Sign up
-------

First you'll have to sign up for an account with
a service provider. This is a (short) list of services that
you can use at the moment:

- Pinata_: `sign up for an account here <https://pinata.cloud/signup>`_

What you will need to register the service in *galacteek*
is the API *token* (the *JWT*, which is encoded).

Register a service
------------------

Once you have signed up, you should have your API token (*JWT*).

To register a *remote pinning service*, go to the settings
panel, then head to the *Pinning settings* section and
select *Register a remote pinning service*.

Enter an adequate *name* for the service. Then copy/paste your
Pinata API *token* (long, encoded string) in the form in the
*Key* field. Select *Ok* and your service should appear in the
list.

Your service will now appear in the list of *remote* services
when clicking on the blue *Pin* buttons in the browser, and you
can start *pinning* and sharing content !


.. _Pinata: https://pinata.cloud/
