import subprocess
import json
import struct


message = {
    "url": "https://1111-releases.cloudflareclient.com/win/latest"
}


data = json.dumps(message).encode("utf-8")


packet = struct.pack(
    "<I",
    len(data)
) + data



process = subprocess.Popen(
    [   "uv",
        "run",
        "python",
        "-m",
        "pydm.native_host"
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE
)



response = process.communicate(
    packet
)[0]


print(response)