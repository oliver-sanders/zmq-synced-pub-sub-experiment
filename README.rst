Zero MQ Data Model Experiment
=============================

A quick look at the data relationship between the Suite and UI Server in the
new Cylc architecture.

.. code-block:: none

   +----------+           (*s = spawn)                        ^
   |  Client  |                                               |
   +----------+                                             w |
       ^  ^                                                 e |
       |  |                                                 b | g
       |  `------------------------.                        s | r
       |                           |                        o | a
   +---+---------------------------+---+                    c | p
   |   |           PROXY           |   |                    k | h
   +---+---------------------------+---+                    e | q
       |              ^            |                        t | l
       |              | *s         |                        s |
       v              |            v                          |
   +---------------+  |    *s  +-----------+                  v
   | authenticator |  |  .---> | UI Server |
   +---------------+  |  |     +-----------+                  ^
   |      HUB      | -`  |         ^    ^                     |
   +---------------+     |         |    `------.            z | ?
   |    spawner    | ----`         | *s        | *s         m | ?
   +---------------+               v           v            q | ?
                               +---------+  +---------+       |
                               | Suite A |  | Suite B |       v
                               +---------+  +---------+


The Problem
-----------

We have a data model in one place (the suite) and we want to clone it
somewhere else (the UI server) whilst keeping it up to date with changes in
the original as and when they happen.

Constraints:

1. Only the changes should be sent.
2. Changes must be applied in order[1].

[1] Well, this might not be so critical but it's a good target to aim at.

The Solution
------------

.. _PUB-SUB: http://zguide.zeromq.org/page:all#Getting-the-Message-Out
.. _REQ-REP: http://zguide.zeromq.org/page:all#Ask-and-Ye-Shall-Receive
.. _PUB-XSUB-XPUB-SUB: http://zguide.zeromq.org/page:all#The-Dynamic-Discovery-Problem

There is:

* A common data structure (``DataModel``) based around nested dictionaries.

* A data publisher (representing the suite) which provides two ZMQ sockets:

  ``publisher`` (`PUB-SUB`_)
     Publishes a stream of continuous updates (deltas)
  ``syncer`` (`REQ-REP`_)
     Provides an interface for the client to request:

     1. The whole data structure when the client connects.
     2. A verification checksum to ensure that nothing has gone astray.

* A data client (representing the UI server) which connects to these sockets.

.. code-block:: none

         +-------------------+
         | Publisher (Suite) |
         |=========+=========|
         |   PUB   |   REP   |
         +---------+---------+
              |        |  ^
              |        |  |
              v        v  |
      +------------+-----------+
      |     SUB    |    REQ    |
      |============+===========|
      | Subscriber (UI Server) |
      +------------------------|

.. note::

   From the suite, through the UI server to the client we have a
   `PUB-XSUB-XPUB-SUB`_ pattern, it's kinda a shame to split it between two
   different systems (zmq, graphql over websockets) but hey ho.

Scaling
-------

The publisher does not not have any knowledge of its subscribers and does not
store any state for them meaning this approach can easily scale sideways to
accommodate more subscribers if required.

The subscriber can connect to multiple publishers but on different sockets as
these represent different data channels and there is no need to mix them
together.

Order Of Play
-------------

1. **The publisher and subscriber are started.**

   Thanks to the magic of ZMQ the order does not matter.

2. **The subsciber subscribes to updates from the publisher.**

   Deltas start coming through and are placed in a temporary queue

3. **The subscriber requests the whole data structure from the publisher.**

   By subscribing first we ensure that any messages received *whilst* this
   request is being fulfilled aren't lost.

4. **Apply any deltas which came in whilst we were busy requesting the data
   structure.**

   Every update comes along with a timestamp. This way we can tell if any
   messages came in before the data structure update (and thus are outdated)
   and ignore them.

5. **Apply deltas as they come in one by one.**

   Once we have got startup out the way it's plain sailing ahead.

6. **Verify?**

   At some future point we may want to verify the data model to ensure it is
   still "in-sync" (a health check).
   
   Why would it be out of sync:

   1. Lost messages.
   2. Messge order out of wack.
   3. Internal error.
   
   Depends how much faith we have in ZMQ PUB-SUB and local network.

Usage
-----

Environment
^^^^^^^^^^^

Note: Hashing requires ordered dictionaries i.e. CPython3.6+

.. code-block:: console

   $ pip install pyzmq

.. code-block:: console

   $ conda create -n zmq -c conda-forge python=3.7 pyzmq

Example
^^^^^^^

.. code-block:: console

    $ python publisher.py
    Sync'er listening
    Data driver started
    (1548156600.8683233, {'AAAA': {'aahed': {'Aalto': 'Aara'}}})
    Received sync request: "update"
    (1548156605.8747132, {'Aarika': 'AARP'})
    (1548156610.8803785, {'aahed': {'AAAA': {'AAUW': 'Ababa'}}})
    Received sync request: "verify"
    (1548156615.8819778, {'Aalto': 'abacisci'})
    (1548156620.8876173, {'AAAA': {'abactor': 'abadengo'}})

.. code-block:: console

   $ python subscriber.py
   Subscriber running
   Clean update requested
   # queueing: 1548156605.8747132 {'Aarika': 'AARP'}
   # queueing: 1548156610.8803785 {'aahed': {'AAAA': {'AAUW': 'Ababa'}}}
   Fast-forwarded to - 1548156600.8683233
   Applying queued deltas:
   # applying: 1548156605.8747132 {'Aarika': 'AARP'}
   # applying: 1548156610.8803785 {'aahed': {'AAAA': {'AAUW': 'Ababa'}}}
   Update completed
   Verifying
   # queueing: 1548156615.8819778 {'Aalto': 'abacisci'}
   # queueing: 1548156620.8876173 {'AAAA': {'abactor': 'abadengo'}}
   # queueing: 1548156625.8933313 {'abactor': 'abaiser'}
   Applying queued deltas
   Verification successful
   # applying: 1548156615.8819778 {'Aalto': 'abacisci'}
   # applying: 1548156620.8876173 {'AAAA': {'abactor': 'abadengo'}}

TODO
----

Message Order
^^^^^^^^^^^^^

This implementation relies on messages arriving at the subscriber in the order
they are sent from the publisher.

This is fundamentally dodgy, however, for our purposes it
`might actually be ok <https://lists.zeromq.org/pipermail/zeromq-dev/2015-January/027748.html>`_.

If we want this to work outside of certain network "guaranties" we could:

1. Provide each delta with both its timestamp and that of its predecessor
   creating a message chain:

   +-----------+--------------------+--------------+
   | timestamp | previous timestamp | delta        |
   +===========+====================+==============+
   |    0      |        /           | foo          |
   +-----------+--------------------+--------------+
   |    1      |        0           | bar          |
   +-----------+--------------------+--------------+
   |    2      |        1           | baz          |
   +-----------+--------------------+--------------+
   |    4      |        3           | pub  # ERROR |
   +-----------+--------------------+--------------+

   The subscriber could then wait for the missing message and or request a
   refresh of the whole data structure.

2. Provide each delta with a checksum. This would require a fast way to hash the
   data structure.

   +-----------+--------------------+--------------+
   | timestamp | hash after change  | delta        |
   +===========+====================+==============+
   |    0      | #1233              | foo          |
   +-----------+--------------------+--------------+
   |    1      | #2345              | bar          |
   +-----------+--------------------+--------------+

3. Provide each delta as a diff containing both the new and old component.

   * A more advanced merge algorithm could detect conflicts.
   * To resolve conflicts we could potentially request just the part of the
     data structure the conflict is contained in.
     
   This is beginning to sound perhaps a bit too clever.

Better Hashing
^^^^^^^^^^^^^^

* Some way of creating a rolling hash (one which we can incrementally update as
  the data evolves in a digest type manner).

* Could use the python ``__hash__`` interface if we prefix the timestamp as an
  integer.

Cleanup
^^^^^^^

Shutdown gently rather than taking a hatchet to the main loop.
