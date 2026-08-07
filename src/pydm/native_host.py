import sys
import json
import struct
import socket


PYDM_HOST = "127.0.0.1"
PYDM_PORT = 8765



def read_message():

    raw_length = sys.stdin.buffer.read(4)

    if not raw_length:
        return None


    message_length = struct.unpack(
        "<I",
        raw_length
    )[0]


    message = sys.stdin.buffer.read(
        message_length
    )


    return json.loads(
        message.decode("utf-8")
    )



def send_native_response(data):

    encoded = json.dumps(
        data
    ).encode("utf-8")


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



def send_to_pydm(url):

    try:

        client = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )


        client.connect(
            (
                PYDM_HOST,
                PYDM_PORT
            )
        )


        client.sendall(
            url.encode("utf-8")
        )


        client.close()


        return True


    except Exception as e:

        print(
            str(e),
            file=sys.stderr
        )

        return False



def show_info() -> None:
    print(
        "PyDM Native Messaging Host\n"
        "This executable is launched by the browser extension.\n"
        "Do not run it directly. Start the PyDM desktop app and use the browser extension instead."
    )


def main():
    if sys.stdin.isatty():
        show_info()



    while True:


        message = read_message()


        if message is None:

            break



        url = message.get(
            "url"
        )


        if url:

            success = send_to_pydm(
                url
            )


            send_native_response(
                {
                    "status":
                    "received"
                    if success
                    else
                    "pydm_not_running"
                }
            )


        else:

            send_native_response(
                {
                    "status":"no_url"
                }
            )



if __name__ == "__main__":

    main()