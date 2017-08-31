from sys import stderr, stdout

from pathlib import Path
import json
from argh import CommandError
import re
from typing import Sequence
from subprocess import run, PIPE, CalledProcessError
from argh import arg
from . import WORK_DIR, download_file, CacheInfo, current_tacospigot_commit,\
    resolve_maven_dependenices, PAPER_WORK_DIR, minecraft_version, download_file,\
    SPECIALSOURCE_URL, SPECIALSOURCE_JAR
from tempfile import NamedTemporaryFile
from zipfile import ZipFile


included_server_libraries = {
    "net.sf.jopt-simple:jopt-simple": True,
    "io.netty:netty-all": True,
    "com.mojang:authlib": True,
    "org.apache.commons:*": True,  # Allow all apache commons
    "commons-*:commons-*": True,  # Allow all old commons too
    "com.google.guava:guava": True,  # Everybody loves guava
    "com.google.code.gson:gson": True,  # Everybody loves gson
    "org.apache.logging.log4j:*": True,  # Log4j is the server's logging system
    # Client only libs
    "com.ibm.icu:icu4j-core-mojang": False,
    "com.paulscode:*": False,  # All the paulscode things are client-only
    "net.java.dev.jna:*": False,  # JNA is client only
    "org.apache.httpcomponents:*": True,  # Apache HTTP is client-only
    "org.lwjgl.lwjgl:*": True,  # LWJGL is client-only
    "net.java.jinput:*": False,
    "net.java.jutils:jutils": False,
    "com.mojang:realms": False,
    "com.mojang:text2speech": False,  # I didn't know minecraft had this
    "ca.weblite:java-objc-bridge": False,
    # Overridden libraries
    "it.unimi.dsi:fastutil": False,  # We override with the entire fastutil jar
    # Other
    "oshi-project:oshi-core": False,  # What is this?
    "com.mojang:patchy": False,  # What is this?
    "com.mojang:netty": False,  # Use regular netty instead of mojang netty
}
include_patterns = None


def load_version_manifest(refresh=False):
    version_manifest_file = Path(WORK_DIR, "versions", "version_manifest.json")
    if not version_manifest_file.exists() or refresh:
        print("---- Refreshing version manifest", file=stderr)
        download_file(version_manifest_file, "https://launchermeta.mojang.com/mc/game/version_manifest.json")
    with open(version_manifest_file) as f:
        return json.load(f)


def parse_version_metadata(version):
    versions = load_version_manifest()['versions']
    try:
        return versions[version]
    except KeyError:
        versions = load_version_manifest(refresh=True)['versions']
        try:
            return versions[version]
        except KeyError:
            raise CommandError(f"Missing version: {version}")


def parse_version_info(version):
    version_file = Path(WORK_DIR, "versions", f"version-{version}.json")
    if not version_file.exists():
        metadata = parse_version_metadata(version)
        print(f"Downloading {version} version info", file=stderr)
        download_file(version_file, metadata['url'])
    with open(version_file) as f:
        return json.load(f)


def is_included_library(name):
    global include_patterns
    if include_patterns is None:
        from fnmatch import translate
        include_patterns = [
            (re.compile(translate(name)), flag)
            for name, flag in included_server_libraries.items()
            if '*' in name
        ]
    groupId, artifactId, version = name.split(':')
    identifier = f"{groupId}:{artifactId}"
    try:
        return included_server_libraries[identifier]
    except KeyError:
        for pattern, flag in include_patterns:
            if pattern.match(identifier) is not None:
                return flag
        raise CommandError(f"No matching include rule for library: {identifier}")


_cached_classpaths = {}


def determine_server_classpath(version) -> Sequence[str]:
    try:
        return _cached_classpaths[version]
    except KeyError:
        pass
    result = []
    for library in parse_version_info(version)['libraries']:
        name = library['name']
        if is_included_library(name):
            result.append(name)
    _cached_classpaths[version] = tuple(result)
    return result


def determine_bukkit_classpath(force=False):
    """Parse the craftbukkit pom to determine their classpath, reusing cached info if possible"""
    current_commit = current_tacospigot_commit()
    cache = CacheInfo.load()
    if not force and cache.bukkitClasspathCommit == current_commit:
        result = cache.bukkitClasspath
        assert result, f"Unexpected cached result: {result}"
        return result
    print("---- Recomputing bukkit classpath", file=stderr)
    try:
        proc = run(["mvn", "dependency:tree", "-B"], check=True, cwd="TacoSpigot", stdout=PIPE, stderr=PIPE, encoding='utf-8')
    except CalledProcessError as e:
        error_lines = e.stderr.splitlines()
        if not error_lines:
            error_lines = e.stdout.splitlines()
        print("Error running mvn dependency tree:", file=stderr)
        for line in error_lines:
            print(line, file=stderr)
        raise CommandError("Error running mvn dependency tree")
    start_pattern = re.compile("maven-dependency-plugin:.*:tree")
    artifact_pattern = re.compile("(.*):(.*):(\w+):([^:]+)(?::(.*))?")
    end_marker = '-' * 10
    output = iter(proc.stdout.splitlines())
    result = []
    for line in output:
        if start_pattern.search(line) is None:
            continue
        while True:
            try:
                line = next(output)
            except StopIteration:
                raise CommandError("Unexpected end of output parsing maven dependency tree")
            if end_marker in line:
                break
            assert line.startswith('[INFO]'), f"Unexpected line: {line}"
            line = line.lstrip("[INFO]").lstrip('\|-+ ').strip()
            if not line:
                continue  # Ignore blank lines
            match = artifact_pattern.match(line)
            assert match, f"Unexpected line: {line}"
            groupId, artifactId, classifier, version, scope = match.groups()
            if classifier == "pom":
                continue
            assert classifier == "jar", f"Unexpected classifier: {classifier}"
            assert scope in (None, "runtime", "compile", "test", "provided"), f"Unkown scope {scope} in {line}"
            if scope in ("compile", None) and 'tacospigot' not in groupId:
                result.append(f"{groupId}:{artifactId}:{version}")
    assert result, f"Unexpected result: {result}"
    cache.bukkitClasspath = result
    cache.bukkitClasspathCommit = current_commit
    cache.save()
    return tuple(result)

_valid_tacospigot_unshaded = False
def unshaded_tacospigot(force=False):
    global _valid_tacospigot_unshaded
    tacospigot_unshaded_jar = Path(WORK_DIR, "jars", "TacoSpigot-unshaded.jar")
    if force or not _valid_tacospigot_unshaded or not tacospigot_unshaded_jar.exists():
        # NOTE: Now we just remap the TacoSpigot jar to undo the shading
        cache = CacheInfo.load()
        current_commit = current_tacospigot_commit()
        if not tacospigot_unshaded_jar.exists() or cache.tacospigotUnshadedCommit != current_commit:
            print("---- Detecting NMS package versioning")
            name_pattern = re.compile("net/minecraft/server/(\w+)/MinecraftServer.class")
            version_signature = None
            with ZipFile('TacoSpigot/build/TacoSpigot-illegal.jar') as z:
                for name in z.namelist():
                    match = name_pattern.match(name)
                    if match is not None:
                        version_signature = match.group(1)
                        break
            if version_signature is None:
                raise CommandError("Unable to detect NMS package versioning")    
            if not SPECIALSOURCE_JAR.exists():
                print("---- Downloading SpecialSource")
                download_file(SPECIALSOURCE_JAR, SPECIALSOURCE_URL)
            print(f"---- Reversing TacoSpigot version shading for {version_signature}")
            with NamedTemporaryFile('wt', encoding='utf-8', prefix='package') as f:
                f.write(f"PK: net/minecraft/server/{version_signature} net/minecraft/server\n")
                f.write(f"PK: org/bukkit/craftbukkit/{version_signature} org/bukkit/craftbukkit\n")
                f.flush()
                run([
                    "java", "-jar", str(SPECIALSOURCE_JAR), "-i", "TacoSpigot/build/TacoSpigot-illegal.jar",
                    "-o", str(tacospigot_unshaded_jar), "-m", f.name
                ], check=True)
            cache.tacospigotUnshadedCommit = current_commit
            cache.save()
        _valid_tacospigot_unshaded = True
    assert tacospigot_unshaded_jar.exists()
    return tacospigot_unshaded_jar

def tacospigot_classpath():
    return [unshaded_tacospigot()]
    #version = minecraft_version()
    # Use the mojang jar itself as a library
    #server_classpath = [Path(PAPER_WORK_DIR, version, f"{version}-mapped.jar")]
    #server_classpath.extend(resolve_maven_dependenices(determine_bukkit_classpath()))
    #server_classpath.append(Path(f"TacoSpigot/TacoSpigot-API/target/tacospigot-api-{version}-R0.1-SNAPSHOT.jar"))
    #assert all(p.exists() for p in server_classpath)
    #return server_classpath


@arg('version', help="The version to determine the classpath for")
def print_server_classpath(version):
    """Print the server classpath as a json list"""
    from . import classpath
    result = determine_server_classpath(version)
    # NOTE: Pretty print to make it easier to read
    json.dump(result, stdout, sort_keys=True, indent=4)


@arg('--force', help="Forcibly recompute the bukkit classpath")
def print_bukkit_classpath(force=False):
    """Print the bukkit classpath as a json list"""
    result = determine_bukkit_classpath(force=force)
    # NOTE: Pretty print to make it easier to read
    json.dump(result, stdout, sort_keys=True, indent=4)
