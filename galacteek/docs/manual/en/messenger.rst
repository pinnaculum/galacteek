.. _messenger:

Messenger
=========

.. image:: ../../../../share/icons/dmessenger/dmessenger.png
    :width: 64
    :height: 64

The decentralized messenger uses the Bitmessage_ protocol to
send and receive messages.

How BitMessage works
--------------------

As described in Wikipedia::

    Bitmessage is a decentralized, encrypted, peer-to-peer, trustless
    communications protocol that can be used by one person to send
    encrypted messages to another person, or to multiple subscribers.

BitMessage uses identity addresses that look like this:

    **BM-87UXauazkpobLFEY4x6i2i631r48QySZr53**

You should communicate your BitMessage identity address only to
the people who want to contact you. From the messenger, clicking
on the clipboard icon on the top-left will copy your current
BitMessage address to the clipboard.

Sending messages
----------------

Composing a new message
^^^^^^^^^^^^^^^^^^^^^^^

From the messenger, click on *Compose*. The *To* compose field,
as with traditional mail clients, corresponds to the recipient
of your message.

You can type/paste a BitMessage address manually, or type the name
of a contact that you've stored (when you select a contact, its
BM address will be used).

Speed of message delivery
^^^^^^^^^^^^^^^^^^^^^^^^^

Although BitMessage is pretty fast (and fast enough), the speed with
which it delivers messages should not be compared to that of other
legacy mailing protocols such as SMTP and others, since they differ
so much in regards to security and protocol complexity.

Proof-of-Work
^^^^^^^^^^^^^

BitMessage, like blockchain technologies such as Bitcoin, uses
a concept known as *proof-of-work*.

The bitmessage client will always compute a *Proof-of-work* when sending
a message. You'll notice a CPU spike in the *notbit* process, which
is normal. After a short amount of time (which really depends on the
capacities of your CPU and the size of the message), you'll get a system
tray notification confirming the POW has been calculated and that your
message was acknowledged.

**After sending a message, do NOT quit the application until you have
have seen the system tray notification for the Proof-of-Work**

.. _Bitmessage: https://wiki.bitmessage.org
