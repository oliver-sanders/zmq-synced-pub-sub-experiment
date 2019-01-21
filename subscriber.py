import asyncio
import json
import time
import sys

import zmq
import zmq.asyncio

from common import DataModel, UPDATE_COMMAND, VERIFY_COMMAND


class DataUpdater(DataModel):
    """The client end of the data structure."""

    def __init__(self):
        super(DataUpdater, self).__init__()
        self.queue = []
        self.paused = True

    async def subscribe(self, socket):
        """Subscribe to updates from the provided socket."""
        print('Subscriber running')
        while True:
            msg = await socket.recv_string()
            timestamp, delta = json.loads(msg)

            if self.paused:
                # TODO: let zmq handle the queue
                print('# queueing:', timestamp, delta)
                self.queue.append((timestamp, delta))
            else:
                self.apply_delta(timestamp, delta)

    async def update(self, socket):
        """Request a clean update from the provided socket.

        Args:
            socket (zmq.Socket): Socket supporting the "update" request.

        """
        print('Clean update requested')
        # pause the model
        self.paused = True

        # request the whole data structure
        socket.send_string(UPDATE_COMMAND)
        timestamp, data = await socket.recv_json()
        await asyncio.sleep(10)  # simulate the update taking really long
        self.reset(data, timestamp)  # replace the old data with the new
        print('Fast-forwarded to - %s' % timestamp)

        # clear out the message queue
        print('Applying queued deltas:')
        while self.queue:
            delta_t, delta = self.queue.pop(0)
            if delta_t > timestamp:
                self.apply_delta(delta_t, delta)
            else:
                print('# ignoring old delta: %s' % delta_t)

        # resume subscription deltas
        print('Update completed')
        self.paused = False

        # NOTE: call the verify method to see it work. This should probably run
        #       periodically?
        await asyncio.sleep(2)  # grace period for queues, important!
        await self.verify(socket)

    async def verify(self, socket):
        """Verify against the remote copy to ensure they are in sync.

        Args:
            socket (zmq.Socket): Socket supporting the "verify" request.

        Returns:
            bool - True if model is in sync with remote copy, False if
                   verification blocked by an update.

        Raises:
            RuntimeError: If the model is out of sync with the remote copy.

        """
        if self.paused:
            # TODO: the verify and update methods are not thread safe
            # queue them.
            return False

        # pause the model
        self.paused = True

        print('Verifying')
        socket.send_string(VERIFY_COMMAND)
        await asyncio.sleep(6)  # simulate the verification taking really long
        remote_timestamp, remote_checksum = await socket.recv_json()
        await asyncio.sleep(6)  # simulate the verification taking really long

        # apply changes until the local copy is in the same state the remote
        # copy was in when the hash was made.
        print('Applying queued deltas')
        while self.queue and remote_timestamp > self.timestmap:
            self.apply_delta(*self.queue.pop(0))

        # compare checksums.
        local_timestamp, local_checksum = await self.checksum()
        if local_checksum != remote_checksum:
            print('Verification failed!')
            import pdb; pdb.set_trace()
            raise RuntimeError('Hash does not match remote copy.')
        print('Verification successful')

        # apply any remaining queued items
        while self.queue:
            self.apply_delta(*self.queue.pop(0))

        self.paused = False
        return True

    def apply_delta(self, timestamp, delta):
        """TEMP: print out the deltas as they are applied."""
        print('# applying:', timestamp, delta)
        super(DataUpdater, self).apply_delta(timestamp, delta)


def main():
    context = zmq.asyncio.Context()

    # the local copy of the data model
    data = DataUpdater()

    # socket for receiving updates from the remote copy
    subscriber_socket = context.socket(zmq.SUB)
    subscriber_socket.connect('tcp://localhost:5561')
    subscriber_socket.setsockopt(zmq.SUBSCRIBE, b'')
    asyncio.ensure_future(data.subscribe(subscriber_socket))

    # socket for sending "update" and "verify" requests
    sync_socket = context.socket(zmq.REQ)
    sync_socket.connect('tcp://localhost:5562')
    asyncio.ensure_future(data.update(sync_socket))

    # run Python run
    asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    main()
