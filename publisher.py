import asyncio
import json
import random
import time

import zmq
import zmq.asyncio

from common import DataModel, delta_generator, UPDATE_COMMAND, VERIFY_COMMAND


class DataDriver(DataModel):
    """The server end of the data structure."""

    def __init__(self, **kwargs):
        super(DataDriver, self).__init__()
        self.subscribers = []
        self.generator = delta_generator()

    def subscribe(self, fcn):
        """Register a new subscriber callback.

        Callbacks must accept the following arguments:
            timestmap (int): Timestamp of the change.
            delta (dict): The diff being applied.

        """
        self.subscribers.append(fcn)

    def publish(self, timestmap, delta):
        """Execute callback functions."""
        for fcn in self.subscribers:
            fcn((timestmap, delta))

    async def start(self):
        """Populate the data structure by continually adding diffs."""
        print('Data driver started')
        while True:
            timestmap = time.time()
            delta = self.generator.__next__()
            self.apply_delta(timestmap, delta)
            self.publish(self.timestmap, delta)
            await asyncio.sleep(5)


async def zmq_listener(socket, callback_dict):
    """Listen on a ZMQ socket, execute a callback when message received.
    
    Args:
        socket (zmq.Socket): The socket to listen on.
        callback_dict (dict): Dictionary with format
            `{"received message": callback_fcn()}`.

    """
    print("Sync'er listening")
    while True:
        msg = await socket.recv_string()
        print('Received sync request: "%s"' % msg)
        response = await callback_dict[msg]()
        socket.send_json(response)


def main():
    context = zmq.asyncio.Context()

    # a socket for publishing changes to the data structure (deltas)
    publisher_socket = context.socket(zmq.PUB)
    publisher_socket.sndhwm = 1100000  # ???
    publisher_socket.bind('tcp://*:5561')

    # the data model to sync
    driver = DataDriver()
    driver.subscribe(publisher_socket.send_json)
    driver.subscribe(print)

    # a socket providing the "update" and "verify" calls
    syncer_socket = context.socket(zmq.REP)
    syncer_socket.bind('tcp://*:5562')

    # add a listener for the "update" and "verify" calls
    asyncio.ensure_future(zmq_listener(syncer_socket, {
        UPDATE_COMMAND: driver.dump,
        VERIFY_COMMAND: driver.checksum}))

    # start the data structure evolving
    asyncio.ensure_future(driver.start())

    try:
        # gogogo
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # stopstopstop
        asyncio.get_event_loop().close()  # perhaps a bit harsh


if __name__ == '__main__':
    main()
