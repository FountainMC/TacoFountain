from pathlib import Path
from subprocess import run, PIPE, CalledProcessError
from typing import Union
from os import PathLike, fspath
import json

WORK_DIR = Path(Path.cwd(), "work")
PAPER_WORK_DIR = Path(Path.cwd(), "TacoSpigot", "Paper", "work")
JDIFF_VERSION = "1.0.1"
JDIFF_JAR = Path(WORK_DIR, f"JDiff-{JDIFF_VERSION}.jar")
JDIFF_URL = f"https://github.com/Techcable/JDiff/releases/download/v{JDIFF_VERSION}/JDiff.jar"


class JDiffException(Exception):
    def __init__(self, mode, message):
        self.mode = mode
        self.message = message

    def __str__(self):
        return self.message


def run_jdiff(mode, *args: Union[str, PathLike], parallel=True, quiet=False):
    if not JDIFF_JAR.exists():
        raise RuntimeError(f"JDiff jar not found at {JDIFF_JAR}!")
    command = ["java", "-jar", JDIFF_JAR, mode]
    if parallel:
        command.append("--parallel")
    if quiet:
        command.append("--quiet")
    for arg in args:
        if isinstance(arg, PathLike):
            command.append(str(Path(arg).absolute()))
        elif isinstance(arg, str):
            command.append(arg)
        else:
            raise TypeError(f"Unexpected argument type: {type(arg)}")
    try:
        run(command, check=True)
    except CalledProcessError:
        simple_args = []
        for arg in args:
            if isinstance(arg, PathLike):
                simple_args.append(str(Path(arg).relative_to(Path.cwd())))
            elif isinstance(arg, str):
                simple_args.append(arg)
            else:
                raise TypeError(type(arg))
        raise JDiffException(
            mode,
            f"Unknown {mode} error with args: " + ' '.join(simple_args)
        ) from None

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
    _minecraft_version = version # Cache
    return version

__all__ = (
    "run_jdiff",
    "minecraft_version",
    # 'Constants'
    "WORK_DIR",
    "PAPER_WORK_DIR",
    "JDIFF_VERSION",
    "JDIFF_JAR",
    "JDIFF_URL",
    # Types
    "JDiffException"
)
