import sys
import json
import struct

from PySide6.QtCore import QObject, Signal


class NativeHost(QObject):

    url_received = Signal(str)


    def read_message(self):

        raw_length = sys.stdin.buffer.read(4)

        if not raw_length:
            return None


        length = struct.unpack(
            "<I",
            raw_length
        )[0]


        data = sys.stdin.buffer.read(
            length
        ).decode("utf-8")


        return json.loads(data)



    def send_message(self, data):

        encoded = json.dumps(data).encode("utf-8")


        sys.stdout.buffer.write(
            struct.pack(
                "<I",
                len(encoded)
            )
        )


        sys.stdout.buffer.write(
            encoded
        )


        sys.stdout.buffer.flush()



    def run(self):

        while True:

            message = self.read_message()


            if message is None:
                break


            url = message.get("url")


            if url:

                self.url_received.emit(
                    url
                )


            self.send_message(
                {
                    "status":"ok"
                }
            )



native_host = NativeHost()



def start_native_host():

    native_host.run()