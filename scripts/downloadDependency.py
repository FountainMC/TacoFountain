#!/usr/bin/env python3
import json
import os
import sys
import platform
import re
from io import TextIOWrapper
from os import path
from shutil import copyfileobj, rmtree
from sys import exit, stderr
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile
import operator


def try_clean(target):
    try:
        if path.isdir(target):
            rmtree(target)
        elif path.exists(target):
            os.remove(target)
    except OSError as e:
        print("WARNING: Unable to cleanup {}: {}".format(target, e), file=stderr)


name = sys.argv[1]
version = sys.argv[2]

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

wheel_pattern = re.compile('\w+-[\w\.]+-([\w\.]+)-(\w+)-(\w+).whl')


def parse_wheel_tags(filename):
    """
    Parse the tags of the specified wheelfile name.
    Should output the same result as wheel.install.WheelFile().tags
    """
    match = wheel_pattern.match(filename)
    if match is None:
        raise RuntimeError(f"Unable to parse wheelfile name: {filename}")
    version_tags, abi_tags, platform_tags = match.groups()
    version_tags = version_tags.split('.')
    abi_tags = abi_tags.split('.')
    platform_tags = platform_tags.split('.')
    result = []
    for version_tag in version_tags:
        for abi_tag in abi_tags:
            for platform_tag in platform_tags:
                result.append((version_tag, abi_tag, platform_tag))
    return result


short_version_id = ''.join(map(str, sys.version_info[:2]))
possible_version_tags = {"py3", f"py{short_version_id}", f"cp{short_version_id}"}
possible_abi_tags = {f"cp{short_version_id}{sys.abiflags}", "none"}
possible_platform_tags = {"any"}

machine = platform.machine()
if sys.platform == "linux":
    possible_platform_tags.add(f"manylinux1_{machine}")
elif sys.platform == "win32":
    if machine == "i386":
        possible_platform_tags.add("win32")
    elif machine == "x86_64":
        possible_platform_tags.add("win_amd64")
    else:
        raise RuntimeError(f"Unknown machine: {machine}")
elif sys.platform == "darwin":
    mac_version = machine.mac_ver()[0]
    assert machine == 'x86_64', f"Unknown machine: {machine}"
    if mac_version:
        possible_platform_tags.add('macosx_{}_x86_64'.format(
            '_'.join(mac_version.split('.')[:2])
        ))
    else:
        # Empty string, fallback to arbitrary version
        possible_platform_tags.add('macosx_10_10_x86_64')
else:
    raise RuntimeError(f"Unknown platform: {sys.platform}")
wheels = {}
for package in package_info['urls']:
    if package['packagetype'] == 'bdist_wheel':
        wheels[package['filename']] = package['url']
if not wheels:
    print(f"ERROR: No wheels for {name} {version} found!", file=stderr)
    exit(1)
else:
    matching_wheels = set(wheels.keys())

    def filter_wheels(actual_tags, acceptable_tags, tag_name):
        old_matching_wheels = frozenset(matching_wheels)
        for wheel_name in old_matching_wheels:
            does_match = False
            for tag in actual_tags(wheel_name):
                if tag in acceptable_tags:
                    does_match = True
                    break
            if not does_match:
                matching_wheels.remove(wheel_name)
        if not matching_wheels:
            raise RuntimeError(''.join([
                f"No wheels found with acceptable {tag_name}s ",
                '{', ', '.join(acceptable_tags), '}',
                " for matching wheels ",
                '{', ', '.join(old_matching_wheels), '}',
                " out of available ",
                '{', ', '.join(wheels.keys()), '}'
            ]))
    wheel_tags = {wheel_name: parse_wheel_tags(wheel_name) for wheel_name in wheels.keys()}
    filter_wheels(
        lambda wheel_name: map(operator.itemgetter(0), wheel_tags[wheel_name]),
        possible_version_tags,
        tag_name='version'
    )
    filter_wheels(
        lambda wheel_name: map(operator.itemgetter(1), wheel_tags[wheel_name]),
        possible_abi_tags,
        tag_name='abi'
    ),
    filter_wheels(
        lambda wheel_name: map(operator.itemgetter(2), wheel_tags[wheel_name]),
        possible_platform_tags,
        tag_name='platform'
    )
    assert matching_wheels, "No wheels found!"
    if len(matching_wheels) > 1:
        raise RuntimeError(
            f"Multiple matching wheels: {matching_wheels}"
        )
    wheel_name = next(iter(matching_wheels))
    wheel_url = wheels[wheel_name]

assert wheel_name.endswith('.whl'), f"Invalid wheel: {wheel_name}"
cached_package = f"work/python_packages/{name}/{version}"
cached_wheel = f"work/python_packages/{name}/{wheel_name}"

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
