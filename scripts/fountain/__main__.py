import shutil
from pathlib import Path
from subprocess import CalledProcessError, run, PIPE
from diffutils.api import PatchFailedException, parse_unified_diff
from diffutils.engine import DiffEngine
from diffutils.output import generate_unified_diff
import os
import sys
from sys import stderr
from collections import namedtuple
import platform

from argh import CommandError, wrap_errors, arg, ArghParser

from . import WORK_DIR, ROOT_DIR, PAPER_WORK_DIR, minecraft_version


def handle_exc(e):
    if isinstance(e, CalledProcessError):
        return 'Error executing command "{}"'.format(' '.join(e.cmd))
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


@wrap_errors([CalledProcessError], processor=handle_exc)
def clean():
    """Remove various cache directories, which may get corrupted"""
    print("---- Cleaning TacoFountain")
    targets = ["patched", "work/unpatched"]
    for target in targets:
        target_path = Path(ROOT_DIR, target)
        if target_path.is_dir():
            shutil.rmtree(str(target_path))
        elif target_path.is_file():
            os.remove(str(target_path))
    print("---- Cleaning TacoSpigot")
    run(["bash", "clean.sh"], cwd=Path(ROOT_DIR, "TacoSpigot"), check=True)

PatchSetup = namedtuple("PatchSetup", ["patches", "unpatched_sources", "patched_sources"])


def setup_patching() -> PatchSetup:
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
        for f in mojang_nms_sources.iterdir():
            assert not f.is_dir(), f"Unexpected directory: {f}"
            unpatched_file = Path(unpatched_nms_sources, f.name)
            if not unpatched_file.exists():
                shutil.copy2(f, unpatched_file)
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
        return None
    return PatchSetup(
        patches=patches,
        unpatched_sources=unpatched_sources,
        patched_sources=patched_sources
    )


@wrap_errors([CalledProcessError], processor=handle_exc)
@arg('--quiet', help="Only print messages when errors occur")
def patch(quiet=False):
    """Applies the patch files to the working directory, overriding any existing work."""
    setup = setup_patching()
    patches, unpatched_sources, patched_sources = setup.patches, setup.unpatched_sources, setup.patched_sources
    print("---- Applying Fountain patches via DiffUtils")
    for patch_root, dirs, files in os.walk(str(patches)):
        for patch_file_name in files:
            patch_file = Path(patch_root, patch_file_name)
            if patch_file.suffix != '.patch':
                raise CommandError(f"Patch file doesn't end with '.patch': {patch_file_name}")
            relative_path = Path(patch_file.parent.relative_to(patches), patch_file.stem)
            original_file = Path(unpatched_sources, relative_path)
            output_file = Path(patched_sources, relative_path)
            if not original_file.exists():
                raise CommandError(f"Couldn't find  original {original_file} for patch {patch_file}!")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            patch_lines = []
            with open(patch_file, 'rt') as f:
                for line in f:
                    patch_lines.append(line.rstrip('\r\n'))
            patch = parse_unified_diff(patch_lines)
            patch_lines = None  # Free
            original_lines = []
            with open(original_file, 'rt') as f:
                for line in f:
                    original_lines.append(line.rstrip('\r\n'))
            try:
                result_lines = patch.apply_to(original_lines)
            except PatchFailedException as e:
                raise CommandError(
                    f"Unable to apply {relative_path}.patch: {e}"
                ) from None
            # TODO: Should we be forcibly overriding files here?
            with open(output_file, 'wt') as f:
                for line in result_lines:
                    f.write(line)
                    f.write('\n')


@wrap_errors([CalledProcessError], processor=handle_exc)
@arg('--quiet', help="Only print messages when errors occur")
@arg('--context', help="The number of context lines to output in the patches")
@arg('--implementation', '--impl', help="Specify the diff implementation to use")
def diff(quiet=False, context=5, implementation=None):
    """Regenerates the patch files from the contents of the working directory."""
    unpatched_sources = Path(WORK_DIR, "unpatched")
    if not unpatched_sources.exists():
        raise CommandError("Couldn't find unpatched sources!")
    patched_dir = Path(Path.cwd(), "patched")
    if not patched_dir.exists():
        raise CommandError("No patched files found!")
    patches = Path(Path.cwd(), "patches")
    patches.mkdir(exist_ok=True)
    if implementation is not None:
        try:
            engine = DiffEngine.create(implementation)
            print(f"Using {repr(engine)} diff implementation.")
        except ImportError as e:
            raise CommandError(
                f"Unable to import {implementation} engine: {e}"
            )
    else:
        try:
            engine = DiffEngine.create('native')
        except ImportError:
            print("WARNING: Unable to import native diff implementation", file=stderr)
            print("Calculating diffs will be over 10 times slower!", file=stderr)
            engine = DiffEngine.create('plain')
    print("---- Recomputing Fountain patches via DiffUtils")
    for revised_root, dirs, files in os.walk(str(patched_dir)):
        for revised_file_name in files:
            if revised_file_name.startswith('.'):
                continue  # Ignore dotfiles
            revised_file = Path(revised_root, revised_file_name)
            relative_path = revised_file.relative_to(patched_dir)
            original_file = Path(unpatched_sources, relative_path)
            if not original_file.exists():
                raise CommandError(f"Revised file {revised_file} doesn't have matching original!")
            patch_file = Path(patches, relative_path.parent, relative_path.name + ".patch")
            patch_file.parent.mkdir(parents=True, exist_ok=True)
            original_lines = []
            revised_lines = []
            with open(original_file, 'rt') as f:
                for line in f:
                    original_lines.append(line.rstrip('\r\n'))
            with open(revised_file, 'rt') as f:
                for line in f:
                    revised_lines.append(line.rstrip('\r\n'))
            result = engine.diff(original_lines, revised_lines)
            original_name = str(original_file.absolute().relative_to(ROOT_DIR))
            revised_name = str(revised_file.absolute().relative_to(ROOT_DIR))
            result_lines = []
            empty = True
            for line in generate_unified_diff(
                original_name,
                revised_name,
                original_lines,
                result,
                context_size=context
            ):
                if empty and line.strip():
                    empty = False
                result_lines.append(line)
            if empty:
                continue
            elif not quiet:
                print(f"Found diff for {relative_path}")
            with open(patch_file, 'wt') as f:
                for line in result_lines:
                    f.write(line)
                    f.write('\n')
        # Strip hidden dotfile dirs
        hidden_dirs = [d for d in dirs if d.startswith('.')]
        for d in hidden_dirs:
            dirs.remove(d)


@arg('--ignore-unresolved', '-i', help="Emit a warning when unresolvable conflicts are found, instead of failing entirely.")
def wiggle(ignore_unresolved=False):
    """Attempt to apply the patches via the wiggle command"""
    def remove_porig(*files: Path):
        """Remove wiggle's backup filess, which aren't nessicarry since we're already using VCS"""
        for f in files:
            porig_file = Path(f.parent, f.name + ".porig")
            if porig_file.exists():
                os.remove(porig_file)
    if not shutil.which("wiggle"):
        error_message = ["Wiggle command not found in PATH"]
        if os.name == 'posix':
            if sys.platform == "darwin":
                install_system = "Homebrew, available from https://brew.sh"
            else:
                install_system = "your system package manager (apt-get, pacman, etc)"
            error_message.append(f"Please install wiggle with {install_system}!")
        else:
            error_message.append("Wiggle isn't supported on windows and other non POSIX systems!")
        raise CommandError(error_message)
    # NOTE: We have to use wiggle directly, since wigglePatches.py doesn't work for some reason
    python_executable = sys.executable
    setup = setup_patching()
    patches, unpatched_sources, patched_sources = setup.patches, setup.unpatched_sources, setup.patched_sources
    has_unresolved = False
    for patch_root, dirs, files in os.walk(str(patches)):
        for patch_file_name in files:
            patch_file = Path(patch_root, patch_file_name)
            if patch_file.suffix != '.patch':
                raise CommandError(f"Patch file doesn't end with '.patch': {patch_file_name}")
            relative_path = Path(patch_file.parent.relative_to(patches), patch_file.stem)
            original_file = Path(unpatched_sources, relative_path)
            output_file = Path(patched_sources, relative_path)
            if not original_file.exists():
                raise CommandError(f"Couldn't find  original {original_file} for patch {patch_file}!")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            remove_porig(original_file, patch_file, output_file)
            command = [
                "wiggle",
                "--replace",
                #"--patch",
                #"--strip=0", # Our paths are correct
                str(output_file.relative_to(Path.cwd())),  # Target
                str(patch_file.relative_to(Path.cwd()))  # Patch
            ]
            remove_porig(original_file, patch_file, output_file)
            try:
                run(command, check=True, encoding='utf-8', stdout=PIPE, stderr=PIPE)
            except CalledProcessError as e:
                if e.stderr.strip():
                    # Prefer stderr for error message
                    error_message = e.stderr.strip().splitlines()
                elif e.stdout.strip():
                    error_message = e.stdout.strip().splitlines()
                else:
                    error_message = None
                if e.returncode == 1:
                    if error_message is None:
                        error_message = []
                    error_message.insert(0, f"Unresolved conflicts found while wiggling {relative_path}.patch")
                    if not ignore_unresolved:
                        raise CommandError(error_message)
                    else:
                        print(f"WARNING: Unresolved conflicts found while wiggling {relative_path}.patch", file=stderr)
                        has_unresolved = True
                else:
                    if error_message is None:
                        error_message = [f"Unkown error patching {relative_path} with {' '.join(command)}"]
                    else:
                        error_message.insert(0, f"Error patching {relative_path} with {' '.join(command)}")
                    raise CommandError(error_message)
            else:
                print(f"Successfully wiggled {patch_file}!")
    if has_unresolved:
        assert ignore_unresolved
        print("WARNING: Unresolved conflicts found, please manually resolve!", file=stderr)
        sys.exit(2)  # Exit with an 'error' value to make them notice!
    else:
        print("All patches successfully applied!")


if __name__ == "__main__":
    parser = ArghParser(prog="fountain.sh", description="The TacoFountain build system")
    parser.add_commands([setup, patch, diff, wiggle, clean])
    parser.dispatch()
