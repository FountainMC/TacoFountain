from argh import ArghParser, arg
from subprocess import run, PIPE
import re
from pathlib import Path
import shutil
import tempfile
import json
import os
from .classpath import tacospigot_classpath
from . import minecraft_version, grouper, ROOT_DIR, WORK_DIR,\
    regenerate_unmapped_sources, download_file, read_file, write_file
from diffutils import generate_unified_diff
from diffutils.engine import DiffEngine

@arg('--recompile', help="Forcibly recompile the jar")
@arg('--dont-restore', help="Don't restore blacklisted files before ")
def find_decompile_errors(recompile=False, dont_restore=False):
    """Compile the decompiled sources with javac, to find which files have errors"""
    if not dont_restore:
        restore_blacklisted(quiet=True)
    version = minecraft_version()
    nms_dir = Path("work/unmapped/net/minecraft/server")
    assert nms_dir.exists()
    scripts_dir = Path(ROOT_DIR, "scripts")
    jar_file = Path(WORK_DIR, "jars", "findDecompileErrors.jar")
    if not jar_file.exists() or recompile:
        with tempfile.TemporaryDirectory() as class_files:
            run(["javac", "-d", class_files, "FindDecompileErrors.java"], cwd=scripts_dir, check=True)
            run(["jar", "-cf", str(jar_file), "-C", class_files, "."], check=True)
        assert jar_file.exists()
    proc = run([
            "java", "-Xmx512M", "-XX:+UseG1GC", "-XX:+HeapDumpOnOutOfMemoryError",
            "-cp", str(jar_file), "FindDecompileErrors",
            ':'.join(str(p) for p in tacospigot_classpath()),
            "work/unmapped",
            nms_dir,
            "buildData/errors.json"
        ]
    )
    # Propagate failure
    exit(proc.returncode)

def load_decompile_errors():
    try:        
        with open('buildData/errors.json') as f:
            data = json.load(f)
        return data['errors']
    except FileNotFoundError:
        raise CommandError("Missing output of find-decompile-errors")

# Files that fail with the JDT compiler, but not with javac
ADDITIONAL_BLACKLISTED_FILES = {}
def regenerate_blacklist():
    """Regenerate the decompile blacklist from the output of find-decompile-errors"""
    errors = load_decompile_errors()
    blacklistedFiles = set(ADDITIONAL_BLACKLISTED_FILES)
    tacospigot_sources = Path("TacoSpigot", "TacoSpigot-Server", "src/main/java", "net/minecraft/server")
    for file_name in errors.keys():
        blacklistedFiles.add(Path(file_name).stem)
    for blacklisted in blacklistedFiles:
        tacospigot_file = Path(tacospigot_sources, file_name + ".java")
        if tacospigot_file.exists():
            print(f"WARNING: Found errors for TacoSpigot file {file_name}")
    print(f"Found {len(blacklistedFiles)} blacklisted files")
    with open('buildData/decompile_blacklist.json', 'wt') as f:
        json.dump(sorted(blacklistedFiles), f)


def generate_fixes():
    """Generate compilation fixing patches"""
    unfixed_sources = Path(WORK_DIR, "unfixed/net/minecraft/server")
    unmapped_sources = Path(WORK_DIR, "unmapped/net/minecraft/server")
    fixes = Path(ROOT_DIR, "buildData/fixes")
    fixes.mkdir(exist_ok=True)
    existing_fixes = list(fixes.iterdir())
    if existing_fixes:
        print("Removing existing fixes")
        for p in existing_fixes:
            os.remove(p)
    engine = DiffEngine.create()
    for unfixed_file in unfixed_sources.iterdir():
        unmapped_file = Path(unmapped_sources, unfixed_file.name)
        original_lines = read_file(unfixed_file)
        fixed_lines = read_file(unmapped_file)
        patch = engine.diff(original_lines, fixed_lines)
        patch_lines = list(generate_unified_diff(
            str(unfixed_file.relative_to(ROOT_DIR)),
            str(unmapped_file.relative_to(ROOT_DIR)),
            original_lines,
            patch
        ))
        if patch_lines:
            print(f"Found diff for {unfixed_file.name}")
            fix_file = Path(fixes, unfixed_file.name + ".patch")
            write_file(fix_file, patch_lines)

@arg('file_name', help="The name of the file to output errors for")
def print_errors(file_name):
    """Print compilation errors for a specified class, based on the output of find-decompile-errors"""
    if not file_name.endswith('.java'):
        file_name += ".java"
    try:
        errors = load_decompile_errors()[file_name]
    except KeyError:
        errors = []
    print(f"Found {len(errors)} errors for {file_name}")
    for value in errors:
        print("ERROR: " + value)

@arg('--quiet', help="Only print a message if files were restored")
def restore_blacklisted(quiet=False):
    """Restore all blacklisted decompiled files"""
    decompiled_dir = Path(WORK_DIR, minecraft_version(), "decompiled", "net/minecraft/server")
    unmapped_dir = Path(WORK_DIR, "unmapped", "net/minecraft/server")
    num_restored = 0
    if any(not Path(unmapped_dir, source.name).exists()
            for source in decompiled_dir.iterdir()):
        regenerate_unmapped_sources(respect_blacklist=False)

if __name__ == "__main__":
    parser = ArghParser(prog="fountain.sh", description="TacoFountain utilities")
    parser.add_commands([find_decompile_errors, restore_blacklisted, regenerate_blacklist, print_errors, generate_fixes])
    parser.dispatch()