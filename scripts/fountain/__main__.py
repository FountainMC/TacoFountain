import shutil
from pathlib import Path
from subprocess import CalledProcessError, run
from urllib.request import urlopen

from argh import CommandError, wrap_errors, arg, ArghParser

from . import *


def handle_exc(e):
    if isinstance(e, CalledProcessError):
        return 'Error executing command "{}"'.format(' '.join(e.cmd))
    elif isinstance(e, JDiffException):
        return f"Error running JDiff: {e}"
    else:
        raise RuntimeError("Unexpected exception") from e


@wrap_errors([CalledProcessError], processor=handle_exc)
def setup():
    """Setup the development environment, re-applying all the Paper and TacoSpigot patches."""
    WORK_DIR.mkdir(exist_ok=True)
    repository = Path(Path.cwd(), "TacoSpigot")
    if not repository.exists():
        raise CommandError("TacoSpigot repository not found!")
    print("---- Cleaning TacoSpigot")
    run(["bash", "clean.sh"], cwd=repository, check=True)
    print("---- Preparing upstream repositories")
    run(["bash", "prepare-build.sh"], cwd=repository, check=True)
    if not JDIFF_JAR.exists():
        print(f"---- Downloading JDiff {JDIFF_VERSION}")
        with urlopen(JDIFF_URL) as r:
            with open(JDIFF_JAR, 'wb+') as f:
                shutil.copyfileobj(r, f)


@wrap_errors([JDiffException, CalledProcessError], processor=handle_exc)
@arg('--quiet', help="Only print messages when errors occur")
def patch(quiet=False):
    """Applies the patch files to the working directory, overriding any existing work."""
    server_repo = Path(Path.cwd(), "TacoSpigot", "TacoSpigot-Server")
    if not server_repo.exists():
        raise CommandError("Couldn't find TacoSpigot-Server")
    tacospigot_sources = Path(server_repo, "src", "main", "java")
    if not tacospigot_sources.exists():
        raise CommandError("Couldn't find TacoSpigot sources!")
    mojang_sources = Path(PAPER_WORK_DIR, minecraft_version())
    if not mojang_sources.exists():
        raise CommandError("Couldn't find mojang sources!")
    unpatched_sources = Path(WORK_DIR, "unpatched")
    if unpatched_sources.exists():
        print("---- Reusing cached original sources")
    else:
        print("---- Copying original sources from TacoSpigot")
        shutil.copytree(tacospigot_sources, unpatched_sources)
        # Copy the remaining mc-dev sources that aren't already in TacoSpigot
        # This makes it so we don't have to depend on the mojang server fat jar,
        # giving us complete control over our dependencies.
        print("---- Copying remaining sources from decompiled mojang jar")
        mojang_nms_sources = Path(mojang_sources, "net/minecraft/server")
        unpatched_nms_sources = Path(unpatched_sources, "net/minecraft/server")
        for file in mojang_nms_sources.iterdir():
            assert not file.is_dir(), f"Unexpected directory: {file}"
            unpatched_file = Path(unpatched_nms_sources, file.name)
            if not unpatched_file.exists():
                shutil.copy2(file, unpatched_file)
    patches = Path(Path.cwd(), "patches")
    patches.mkdir(exist_ok=True)
    patched_sources = Path(Path.cwd(), "patched")
    if patched_sources.exists():
        print("---- Clearing existing patched sources")
        shutil.rmtree(patched_sources)
    print("---- Copying unpatched sources into patched directory")
    shutil.copytree(unpatched_sources, patched_sources)
    if not patches.exists() or not list(patches.iterdir()):
        print("---- No patches to apply")
        return
    print("---- Applying Fountain patches via JDiff")
    run_jdiff("patch", unpatched_sources, patched_sources, patches, quiet=quiet)

@wrap_errors([JDiffException, CalledProcessError], processor=handle_exc)
@arg('--quiet', help="Only print messages when errors occur")
def diff(quiet=False):
    """Regenerates the patch files from the contents of the working directory."""
    unpatched_sources = Path(WORK_DIR, "unpatched")
    if not unpatched_sources.exists():
        raise CommandError("Couldn't find unpatched sources!")
    patched_dir = Path(Path.cwd(), "patched")
    if not patched_dir.exists():
        raise CommandError("No patched files found!")
    patches = Path(Path.cwd(), "patches")
    patches.mkdir(exist_ok=True)
    print("---- Recomputing Fountain patches via JDiff")
    run_jdiff("diff", unpatched_sources, patched_dir, patches, quiet=quiet)

if __name__ == "__main__":
    parser = ArghParser(prog="fountain.sh", description="The TacoFountain build system")
    parser.add_commands([setup, patch, diff])
    parser.dispatch()
