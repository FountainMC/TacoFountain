from pathlib import Path
from subprocess import run, PIPE, CalledProcessError
import json


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


ROOT_DIR = _determine_root_dir().absolute()
WORK_DIR = Path(ROOT_DIR, "work")
PAPER_WORK_DIR = Path(ROOT_DIR, "TacoSpigot", "Paper", "work")


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

__all__ = (
    "minecraft_version",
    # 'Constants'
    "ROOT_DIR",
    "WORK_DIR",
    "PAPER_WORK_DIR",
)
