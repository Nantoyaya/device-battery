"""extract_asar.py —— 解包 Electron 的 app.asar（纯标准库，只解文本文件）。"""

import json
import os
import struct
import sys

src = sys.argv[1]
dst = sys.argv[2]
only = sys.argv[3].split(",") if len(sys.argv) > 3 else [".js", ".json", ".ts", ".html", ".txt"]

with open(src, "rb") as f:
    data = f.read()

json_start = data.find(b'{"files"')
if json_start < 0:
    raise SystemExit("not an asar archive")
header_str_len = struct.unpack("<I", data[json_start - 4:json_start])[0]
json_bytes = data[json_start:json_start + header_str_len]
header = json.loads(json_bytes.decode("utf-8"))
base = json_start + header_str_len
base += (-base) % 4

count = 0
total = 0
for path, info in header["files"].items():
    stack = [(path, info)]
    while stack:
        name, node = stack.pop()
        if "files" in node:
            for k, v in node["files"].items():
                stack.append((name + "/" + k, v))
            continue
        if "offset" not in node:
            continue
        ext = os.path.splitext(name)[1].lower()
        if only and ext not in only:
            continue
        off = base + int(node["offset"])
        size = int(node["size"])
        out = os.path.join(dst, name.replace("/", os.sep))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as g:
            g.write(data[off:off + size])
        count += 1
        total += size

print("extracted %d files, %.1f MB -> %s" % (count, total / 1e6, dst))
