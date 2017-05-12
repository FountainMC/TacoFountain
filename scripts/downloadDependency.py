#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from io import TextIOWrapper
from os import path
from shutil import copyfileobj, rmtree
from sys import exit, stderr
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile


def try_clean(target):
    try:
        if path.isdir(target):
            rmtree(target)
        elif path.exists(target):
            os.remove(target)
    except OSError as e:
        print("WARNING: Unable to cleanup {}: {}".format(target, e), file=stderr)


def hash_file(target, algorithim=hashlib.sha256):
    m = algorithim()
    buffer = bytearray(8192)  # Hash 8KB at a time since python is slow
    with open(target, 'br') as f:
        while True:
            size = f.readinto(buffer)  # type: ignore
            if size == 0:
                break
            m.update(buffer[:size])
    return m.hexdigest()


name = sys.argv[1]
version = sys.argv[2]
expected_hash = sys.argv[3]

try:
    print("Fetching package info for {} {}".format(name, version))
    with urlopen("https://pypi.python.org/pypi/{}/{}/json".format(name, version)) as response:
        package_info = json.load(TextIOWrapper(response, 'utf-8'))  # type: ignore # io  is broken
except URLError as e:
    print("ERROR: Unable to fetch package info for {} {}".format(name, version), file=stderr)
    if isinstance(e, HTTPError):
        print("Unexpected response code: {}".format(e.code), file=stderr)
    else:
        print("Error contacting server: {}".format(e.reason), file=stderr)
    exit(1)
except json.JSONDecodeError as e:
    print("ERROR: Invalid package info json: {}".format(e))
    exit(1)

wheels = []
for package in package_info['urls']:
    if package['packagetype'] == 'bdist_wheel':
        wheels.append(package['url'])
if not wheels:
    print("ERROR: No wheels for {} {} found!", file=stderr)
    exit(1)
elif len(wheels) > 1:
    print("ERROR: Multiple wheels for {} {} found: [{}]", ', '.join(wheels), file=stderr)
    exit(1)
else:
    wheel_url = wheels[0]

cached_package = "work/python_packages/{}/{}".format(name, version)
cached_wheel = "work/python_packages/{}-{}.whl".format(name, version)

os.makedirs(path.dirname(cached_wheel), exist_ok=True)

if not path.exists(cached_wheel):
    try:
        print("Downloading wheel for {} {}".format(name, version))
        with urlopen(wheel_url) as remote:
            with open(cached_wheel, 'bw+') as local:
                copyfileobj(remote, local)  # type: ignore # io typing is broken
    except (URLError, OSError) as e:
        print("ERROR: Unable to download wheel for {}v{}".format(name, version), file=stderr)
        if isinstance(e, HTTPError):
            print("ERROR: Unexpected response code: {}".format(e.code), file=stderr)
        elif isinstance(e, URLError):
            print("Error contacting server: {}".format(e.reason), file=stderr)
        else:
            print("Error writing to file: {}".format(e), stderr)
        try_clean(cached_wheel)
        exit(1)

# Verify the hash
actual_hash = hash_file(cached_wheel)
if actual_hash != expected_hash:
    print("ERROR: Unexpected hash for {}: {}".format(cached_wheel, actual_hash), file=stderr)
    print("ERROR: Expected hash {} for {} {}".format(expected_hash, name, version), file=stderr)
    exit(1)

if not path.exists(cached_package):
    try:
        print("Extracting {}".format(path.basename(cached_wheel)))
        os.makedirs(cached_package)
        with ZipFile(cached_wheel) as archive:
            archive.extractall(cached_package)
    except OSError as e:
        print("ERROR: Unable to extract {}: {}".format(path.basename(cached_wheel), e), file=stderr)
        try_clean(cached_package)
        exit(1)
    except BadZipFile as e:
        print("ERROR: {} isn't a valid zipfile: {}".format(path.basename(cached_wheel), e), file=stderr)
        try_clean(cached_package)
        exit(1)
