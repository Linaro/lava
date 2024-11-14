#!/usr/bin/python3

# This script should no longer be necessary with sphinx > 7.2.7

import json
import re
import subprocess
import sys

os = subprocess.check_output(
    ["sh", "-c", ". /etc/os-release; echo $ID-$VERSION_ID"], text=True
).strip()

index = sys.argv[1]
data = open(index).read()

# turn data into proper JSON
data = re.sub(r"^Search.setIndex\(", "", data)
data = re.sub(r"\)$", "", data)

# sphinx in bullseye does not produce proper JSON data with quoted keys
if os == "debian-11":
    data = re.sub(r"(\w+):", r'"\g<1>":', data)

# load JSON
j = json.loads(data)

# reorder entries in alltitles
if "alltitles" in j:
    for k, v in j["alltitles"].items():
        j["alltitles"][k] = sorted(v, key=lambda i: i[0])

# dump JSON
result = json.dumps(j, sort_keys=True, separators=(",", ":"))

if os == "debian-11":
    # fixup for debian 11
    result = re.sub('"filenames":', "filenames:", result)

# output
with open(index, "w") as output:
    print("Search.setIndex(", end="", file=output)
    print(result, end="", file=output)
    print(")", file=output)
