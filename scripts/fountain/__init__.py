from pathlib import Path
from subprocess import run, PIPE, CalledProcessError, Popen
import json
from urllib.request import urlopen
import shutil
from argh import CommandError
import hashlib
from typing import Iterable, Mapping, List
import glob
from itertools import zip_longest
from diffutils import parse_unified_diff
import os

def _determine_root_dir():
    location = Path.cwd()
    while True:
        try:
            process = run(
                ["git", "rev-parse", "--git-dir"],
                cwd=location, check=True, stdout=PIPE,
                encoding='utf-8'
            )
            git_dir = Path(location, process.stdout.strip())
        except CalledProcessError:
            raise RuntimeError(
                f"Unable to find root dir from {Path.cwd()}"
            )
        assert git_dir.is_dir(), f"Git dir doesn't exist: {git_dir}"
        result = git_dir.parent
        # Stupid herustics to try and determine if we are the root repo
        if Path(result, 'patches').exists() or Path(result, 'scripts', 'fountain').exists():
            return result
        else:
            location = location.parent

def regenerate_unmapped_sources(regenerate_unfixed=False, respect_blacklist=True):
    unfixed_sources = Path(WORK_DIR, "unfixed")
    if regenerate_unfixed or not unfixed_sources.exists():
        regenerate_unfixed_sources()
    unmapped_sources = Path(WORK_DIR, "unmapped")
    unfixed_nms_sources = Path(unfixed_sources, "net/minecraft/server")
    unmapped_nms_sources = Path(unmapped_sources, "net/minecraft/server")
    if unmapped_sources.exists():
        print("---- Removing existing unmapped sources")
        shutil.rmtree(unmapped_sources)
    print("---- Copying unmapped files")
    shutil.copytree(unfixed_sources, unmapped_sources)
    blacklist = decompile_blacklist() if respect_blacklist else ()
    removed_files = 0
    for path in unmapped_nms_sources.iterdir():
        if path.stem in blacklist:
            removed_files += 1
            os.remove(path)
    if removed_files:
        print(f"Removed {removed_files} blacklisted files")
    print("---- Applying compile fixes")
    fixes = Path(ROOT_DIR, "buildData/fixes")
    for fix in fixes.iterdir():
        patch = parse_unified_diff(read_file(fix))
        original_file = Path(unfixed_nms_sources, fix.stem)
        fixed_file = Path(unmapped_nms_sources, fix.stem)
        print(f"Applying fix to {fix.stem}")
        original_lines = read_file(original_file)
        revised_lines = patch.apply_to(original_lines)
        write_file(fixed_file, revised_lines)

def read_file(path):
    result = []
    with open(path) as f:
        for line in f.readlines():
            result.append(line.rstrip("\r\n"))
    return result

def write_file(path, lines, override=True):
    assert override, "unsupported"
    with open(path, 'wt') as f:
        for line in lines:
            f.write(line)
            f.write('\n')

def regenerate_unfixed_sources():
    unfixed_sources = Path(WORK_DIR, "unfixed")
    decompiled_sources = Path(WORK_DIR, minecraft_version(), "decompiled")
    if unmapped_sources.exists():
        print("---- Removing existing unfixed sources")
        shutil.rmtree(unmapped_sources)
    server_repo = Path(Path.cwd(), "TacoSpigot", "TacoSpigot-Server")
    if not server_repo.exists():
        raise CommandError("Couldn't find TacoSpigot-Server")
    tacospigot_sources = Path(server_repo, "src", "main", "java")
    if not tacospigot_sources.exists():
        raise CommandError("Couldn't find TacoSpigot sources!")
    mojang_sources = Path(PAPER_WORK_DIR, minecraft_version())
    if not mojang_sources.exists():
        raise CommandError("Couldn't find mojang sources!")
    print("---- Copying original sources from TacoSpigot")
    shutil.copytree(tacospigot_sources, unfixed_sources)
    # Copy the decompiled sources that aren't already in TacoSpigot
    # This makes it so we don't have to depend on the mojang server fat jar,
    # giving us complete control over our dependencies.
    # Make sure to use the ones decompiled with forge fernflower, or they won't work
    print("---- Copying remaining sources from forge fernflower decompiled mojang jar")
    decompiled_nms_sources = Path(decompiled_sources, "net/minecraft/server")
    unfixed_nms_sources = Path(unfixed_sources, "net/minecraft/server")
    assert decompiled_nms_sources.exists()
    for f in decompiled_nms_sources.iterdir():
        assert not f.is_dir(), f"Unexpected directory: {f}"
        unfixed_file = Path(unfixed_sources, f.name)
        if not unfixed_file.exists():
            shutil.copy2(f, unfixed_file)

ROOT_DIR = _determine_root_dir().absolute()
WORK_DIR = Path(ROOT_DIR, "work")
PAPER_WORK_DIR = Path(ROOT_DIR, "TacoSpigot", "Paper", "work")

MAVEN_REPOSITORIES = {
    "central": "https://repo1.maven.org/maven2/",
    "forge": "https://files.minecraftforge.net/maven",
    "eclipse": "https://repo.eclipse.org/content/groups/eclipse/"
}
SUPERSRG_VERSION = "0.1.0"
_supersrg_jar = None
def supersrg_jar() -> Path:
    global _supersrg_jar
    result = _supersrg_jar
    if result is not None:
        return result
    dev_jar = Path(WORK_DIR, "jars", "SuperSrg-dev.jar")
    if dev_jar.exists() and os.getenv("SUPERSRG_DEV") not in (None, "0"):
        result = dev_jar
    else:
        raise AssertionError("TODO: Download SuperSrg jar")
    _supersrg_jar = result
    return result
_supersrg_binary = None
def supersrg_binary() -> Path:
    global _supersrg_binary
    result = _supersrg_binary
    if result is not None:
        return result
    dev_binary = Path(WORK_DIR, "bin", "supersrg-dev")
    if dev_binary.exists() and os.getenv("SUPERSRG_DEV") not in (None, "0"):
        result = dev_binary
    else:
        raise AssertionError("TODO: Download SuperSrg binary")
    _supersrg_binary = result
    return result

LOCAL_REPOSITORY = Path(Path.home(), ".m2", "repository")
FORGE_FERNFLOWER_COMMIT = "32a04b9"
FORGE_FERNFLOWER_REMOTE = "https://github.com/MinecraftForge/ForgeFlower.git"
FORGE_FERNFLOWER_JAR = Path(WORK_DIR, "jars", f"forge-fernflower-{FORGE_FERNFLOWER_COMMIT}.jar")
FERNFLOWER_OPTIONS = {
    "din": True,  # Decompile inner classes
    "dgs": True,  # Decompile generic signatures
    "asc": True,  # Escape non-ASCII characters
    "rsy": True,  # Remove synthetic class members
    "rbr": True,  # Remove bridge members
    "udv": False  # Ignore variable names, since they lie
}
SPECIALSOURCE_BUILD = 112
SPECIALSOURCE_URL = f"https://ci.md-5.net/job/SpecialSource/{SPECIALSOURCE_BUILD}/artifact/target/SpecialSource-1.7.5-SNAPSHOT-shaded.jar"
SPECIALSOURCE_JAR = Path(WORK_DIR, "jars", f"SpecialSource-{SPECIALSOURCE_BUILD}.jar")
_cached_decompile_blacklist = None
def decompile_blacklist():
    """Classes that are broken even with the improved fernflower decompiler"""
    global _cached_decompile_blacklist
    result = _cached_decompile_blacklist
    if result is not None:
        return result
    with open('buildData/decompile_blacklist.json') as f:
        result = frozenset(json.load(f))
    tacospigot_sources = Path("TacoSpigot/TacoSpigot-Server/src/main/java", "net/minecraft/server")
    for value in result:
        tacospigot_file = Path(tacospigot_sources, value + ".java")
        if tacospigot_file.exists():
            raise CommandError(f"Blacklisted file exists in TacoSpigot: {value}")
    _cached_decompile_blacklist = result
    return result

def compile_forgeflower(commit=FORGE_FERNFLOWER_COMMIT):
    result_jar = Path(WORK_DIR, "jars", f"forge-fernflower-{commit}.jar")
    assert not result_jar.exists(), f"Jar already exists: {result_jar}"
    fernflower_repo = Path(WORK_DIR, "ForgeFlower")
    if not fernflower_repo.exists():
        run(["git", "clone", "https://github.com/MinecraftForge/ForgeFlower.git", str(fernflower_repo)], check=True)
    else:
        try:
            # See if we already have the commit
            run(["git", "rev-parse", commit], cwd=fernflower_repo, check=True)
        except CalledProcessError:
            run(["git", "fetch", "https://github.com/MinecraftForge/ForgeFlower.git", "master"], cwd=fernflower_repo, check=True)
    run(["git", "reset", "--hard", commit], cwd=fernflower_repo, check=True)
    run(["git", "submodule", "update", "--recursive", "--init"], cwd=fernflower_repo)
    run(["bash", "gradlew", "clean", "build", "--no-daemon", "-x", "test"], cwd=fernflower_repo, check=True)
    compiled_jars = glob.glob("work/ForgeFlower/ForgeFlower/build/libs/forgeflower-*.jar")
    assert len(compiled_jars) == 1, f"Unexpected compiled jars: {compiled_jars}"
    shutil.copy2(compiled_jars[0], result_jar)


def run_fernflower(classes: Path, output: Path, libraries=[], verbose=True, options=FERNFLOWER_OPTIONS):
    assert classes.is_dir(), f"Classes don't exist: {classes}"
    assert not output.exists(), f"Ouptut already exists: {output}"
    assert FORGE_FERNFLOWER_JAR.exists(), f"Fernflower jar doesn't exist: {FORGE_FERNFLOWER_JAR}"
    output.mkdir(parents=True)
    command = ["java", "-jar", str(FORGE_FERNFLOWER_JAR)]
    for key, value in options.items():
        if isinstance(value, bool):
            value = "1" if value else "0"
        elif not isinstance(value, str):
            raise TypeError(f"Unexpected option type: {type(value)}")
        command.append(f"-{key}={value}")
    for library in libraries:
        if isinstance(library, Path):
            library = str(library)
        elif not isinstance(library, str):
            raise TypeError(f"Unexpected library type: {type(library)}")
        command.append(f"-e={library}")
    command.extend((str(classes), str(output)))
    # NOTE: Use popen so we can output info while running
    with Popen(command, encoding='utf-8', stdout=PIPE, stderr=PIPE) as proc:
        while proc.poll() is None:
            line = proc.stdout.readline().rstrip("\r\n")
            print(line)
        if proc.wait() != 0:
            error_message = proc.stderr.read().splitlines()
            shutil.rmtree(output)  # Cleanup partial output
            raise CommandError(["Error running fernflower:", *error_message])


_current_tacospigot_commit = None
def current_tacospigot_commit() -> str:
    global _current_tacospigot_commit
    result = _current_tacospigot_commit
    if result is not None:
        return result
    result = run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=True, cwd=Path(Path.cwd(), "TacoSpigot"),
        stdout=PIPE, encoding='utf-8'
    ).stdout.strip()
    _current_tacospigot_commit = result
    return result


def download_file(target: Path, url: str):
    with urlopen(url) as r:
        target.parent.mkdir(exist_ok=True, parents=True)
        with open(target, 'wb') as f:
            shutil.copyfileobj(r, f)


def resolve_maven_dependenices(dependencies, repos=MAVEN_REPOSITORIES):
    classpath = []
    remotes = ",".join(f"{name}::default::{url}" for name, url in repos.items())
    for dependency in dependencies:
        parts = dependency.split(":")
        assert len(parts) == 3, f"Invalid dependency: {dependency}"
        groupId, artifactId, version = parts
        expected_location = Path(LOCAL_REPOSITORY, groupId.replace('.', '/'), artifactId, version, f"{artifactId}-{version}.jar")
        if not expected_location.exists():
            print(f"Downloading {dependency}")
            try:
                command = ["mvn", "dependency:get", "-q",
                           f"-DgroupId={groupId}", f"-DartifactId={artifactId}",
                           f"-Dversion={version}", f"-DremoteRepositories={remotes}"
                           ]
                run(command, check=True)
                if not expected_location.exists():
                    raise CommandError(f"Unable to download {dependency} to {expected_location}")
            except CalledProcessError:
                raise CommandError(f"Maven failed to download {dependency}")
        assert expected_location.exists()
        classpath.append(expected_location)
    return classpath


_minecraft_version = None


def minecraft_version() -> str:
    global _minecraft_version
    if _minecraft_version is not None:
        return _minecraft_version
    build_data_info = Path(PAPER_WORK_DIR, "BuildData", "info.json")
    assert build_data_info.exists(), f"Can't find BuildData info.json: {build_data_info}"
    with open(build_data_info, 'rt') as f:
        info = json.load(f)
    version = info['minecraftVersion']
    _minecraft_version = version  # Cache
    return version


def hash_file(location, algorithm='sha256'):
    try:
        h = getattr(hashlib, algorithm)()
    except AttributeError:
        h = hashlib.new(algorithm)

    buffer = bytearray(1024 * 16)
    view = memoryview(buffer)
    with open(location, 'rb') as f:
        while True:
            numRead = f.readinto(buffer)
            if not numRead:
                return h.digest()
            h.update(view[:numRead])


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

def secure_hash(target, algorithm='sha256'):
    try:
        h = getattr(hashlib, algorithm)()
    except AttributeError:
        h = hashlib.new(algorithm)

    def update_hash(target):
        if isinstance(target, bytes):
            h.update(target)
        elif isinstance(target, str):
            h.update(target.encode('utf-8'))
        elif isinstance(target, Iterable):
            target = tuple(target)
            h.update(b'\0')
            for element in target:
                update_hash(target)
                h.update(b'\0')
        elif isinstance(target, Mapping):
            target = dict(target)
            h.update(b'\0')
            for key, value in target.items():
                update_hash(key)
                h.update(b'\0')
                update_hash(value)
                h.update(b'\0')
        else:
            raise TypeError(f"Unsupported type: {type(target)}")
    update_hash(target)
    return h.digest()

_configuration = None
def configuration():
    global _configuration
    result = _configuration
    if result is not None:
        # Defensive copy
        return result.copy()
    try:
        with open(Path(ROOT_DIR, "buildData", "config.json")) as f:
            result = json.load(f)
    except FileNotFoundError:
        raise CommandError("Missing config file")
    _configuration = result
    return result.copy()

class CacheInfo:
    rangeMapCommit: str
    lastBuiltTacoSpigot: str
    bukkitClasspath: List[str]
    bukkitClasspathCommit: str
    tacospigotUnshadedCommit: str

    def __init__(self, **kwargs):
        self.rangeMapCommit = kwargs.get('rangeMap.commit')
        self.lastBuiltTacoSpigot = kwargs.get('tacospigot.lastBuild')
        bukkitClasspath = kwargs.get('bukkitClasspath')
        self.tacospigotUnshadedCommit = kwargs.get('tacospigot.unshadedCommit')
        if bukkitClasspath is not None:
            self.bukkitClasspathCommit = bukkitClasspath['commit']
            self.bukkitClasspath = bukkitClasspath['entries']
        else:
            self.bukkitClasspathCommit = None
            self.bukkitClasspath = None

    def serialize(self):
        result = {}
        if self.rangeMapCommit is not None:
            result["rangeMap.commit"] = self.rangeMapCommit
        if self.lastBuiltTacoSpigot is not None:
            result['tacospigot.lastBuild'] = self.lastBuiltTacoSpigot
        if self.tacospigotUnshadedCommit is not None:
            result['tacospigot.unshadedCommit'] = self.tacospigotUnshadedCommit
        if self.bukkitClasspath is not None:
            assert self.bukkitClasspathCommit is not None
            result['bukkitClasspath'] = {
                'commit': self.bukkitClasspathCommit,
                'entries': self.bukkitClasspath
            }
        return result

    def save(self):
        data = self.serialize()
        CacheInfo._CACHED_DATA = None
        with open(CacheInfo.LOCATION, 'wt') as f:
            # NOTE: Pretty print so the humans can see our beautiful cache info
            json.dump(data, f, sort_keys=True, indent=4)
            CacheInfo._CACHED_DATA = data.copy()


    _CACHED_DATA = None
    LOCATION = Path(WORK_DIR, "cache-info.json")

    @staticmethod
    def load() -> "CacheInfo":
        data = CacheInfo._CACHED_DATA
        if data is None:
            try:
                with open(CacheInfo.LOCATION, "rt") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {}
            CacheInfo._CACHED_DATA = data
        return CacheInfo(**data)



__all__ = (
    "minecraft_version",
    "CacheInfo",
    # 'Constants'
    "ROOT_DIR",
    "WORK_DIR",
    "PAPER_WORK_DIR",
)
