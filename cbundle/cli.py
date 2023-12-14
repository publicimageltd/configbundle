#!/usr/bin/python
from pathlib import Path
import os
from typing import Callable, Optional
from typing_extensions import Annotated
import sys
import re
import shutil
import subprocess
# Hack to disable rich output
sys.modules['rich'] = None  # type: ignore
import typer  # noqa: E402


# TODO Make main arg in cmds path-like: bundle/file
# TODO Rewrite Tests
# TODO Turn assert_xx into validations using Typer
#
# -----------------------------------------------------------
# Global Variables

APP_NAME = 'configbundle'
cli = typer.Typer(no_args_is_help=True)

# -----------------------------------------------------------
# Utilities

# TODO Replace with typer.confirm("....")
def _ask(prompt: str, default: str) -> bool:
    """Prompt the user for a decision.
    DEFAULT is the default option (one of 'y','n','yes','no')."""
    choice = None
    option_set = {'y', 'n', 'yes', 'no'}
    yes_set = {'y', 'yes'}
    default_set = {default}
    options = [str.upper(e) if e in default_set else e
               for e in option_set]
    prompt += f" {options} "
    while choice is None:
        _input = str.lower(input(prompt) or default)
        if _input in option_set:
            choice = _input in yes_set
        else:
            print("Please pick one of the options.")
    return choice


def _suffix(file: Path) -> Path:
    """Return FILE with the suffix .link added."""
    return Path(f"{file}.link")


def assert_path(p: Path,
                assertion: Callable[[Path], bool] = Path.exists,
                msg: str | None = '{p} does not exist',
                cancel: bool = True) -> bool:
    """Check if path P satisfies ASSERTION, exiting if CANCEL is True."""
    result = assertion(p)
    if not result:
        if msg:
            print(msg.format(p=p))
        if cancel:
            raise typer.Exit(1)
    return result

# TODO Refactor into two fns for dir and file, with distinct return types
def _parse_bundle(bundle: str, dir_only: bool = False) -> tuple[Path | None, Path | None]:
    """Parse BUNDLE, returning a directory and a file path.

    If DIR_ONLY is true, treat it unconditionally as a directory specification:

          'dir/subdir/further_subdir'

    Else split the path into a file and a directory part, using the last slash
    as separator:

          'dir/subdir/file'

    If the string contains no slash, treat the complete string as a file specification:

         'file'

    A trailing slash will turn the last part of the string into a directory name:

         'dir/subdir/'

    For that reason, the function might not return a value for the file even if
    DIR_ONLY is set to False.

    Always ignore slash at the beginning. Return None for a missing dir or file specification.
    """
    # Some sanity checks:
    bundle = re.sub("/{2,}", "/", bundle)
    bundle = bundle.lstrip("/")
    if bundle == "" or bundle.isspace():
        print("Bundle specification cannot be empty")
        raise typer.Exit(1)
    # Split:
    _dir: Path | None
    _file: Path | None
    if bundle.endswith("/") or dir_only:
        _dir, _file = Path(bundle), None
    else:
        _dir, _, _file = [Path(x) if x != '' else None for x in bundle.rpartition("/")]
    return _dir, _file


def _ignore(file: Path) -> bool:
    """Return False when file is a bundle file."""
    res = False
    res = file.match(".gitignore")
    res = file.match(".git")
    return res


def get_repo() -> Path:
    """Return the path to the bundle repository."""
    repo_path = Path(typer.get_app_dir(APP_NAME))
    if not repo_path.exists():
        repo_path.mkdir()
    assert_path(repo_path, Path.is_dir, msg="{p} is not a directory")
    return repo_path


def _move(file: Path, target_path: Path) -> Path:
    """Move FILE, returning the new file as Path."""
    target_path = target_path.absolute()
    if target_path.is_dir():
        target_file = target_path / file.name
    else:
        target_file = target_path
    shutil.move(str(file), str(target_file))
    return Path(target_file)


def _copy(file: Path, target_path: Path) -> Path:
    """Copy FILE, returning the destination as Path.
    If TARGET_PATH is a directory, copy the file into this directory.
    If TARGET_PATH is a file, use this file name as destination.
    If FILE is a symlink, create a copy of the file FILE
    is referring to."""
    target_path = target_path.absolute()
    if target_path.is_dir():
        target_file = target_path / file.name
    else:
        target_file = target_path
    return shutil.copy2(f"{file}", f"{target_file}")


def _link_back(link_file: Path, target_file: Path) -> None:
    """Create a suffixed symlink pointing to TARGET_FILE."""
    link_file = _suffix(link_file)
    link_file.symlink_to(target_file.absolute())


def _bundle_file(file: Path, bundle_dir: Path) -> None:
    """Move FILE into BUNDLE_DIR and replace FILE with a link pointing to the bundled file.
       Additionally create a backlink in the bundle dir."""
    bundled_file = _move(file, bundle_dir)
    _link_back(bundled_file, file)
    # TODO Check relative or absolute links, what do we need?
    file.symlink_to(bundled_file)


# -----------------------------------------------------------
# TODO Test manually
# TODO Add test for already bundled file
@cli.command()
def add(file: Path, bundle_dir: str) -> None:
    "Add FILE to BUNDLE_DIR, replacing it with a link to the bundled file."
    assert_path(file)
    _repo = get_repo()
    _dir, _ = _parse_bundle(bundle_dir, True)
    # FIXME Currently BUNDLE_DIR is not optional, but
    #       it could be a useful feature to add. This
    #       would have to be intercepted before the call
    #       to _parse_bundle
    if _dir is None:
        _dir = _repo
    else:
        _dir = _repo / _dir
    if Path(_dir / file.name).exists():
        print("File is already bundled")
        raise typer.Exit(1)
    _dir.mkdir(parents=True, exist_ok=True)
    _bundle_file(file, _dir)


# TODO Add test
@cli.command()
def copy(bundle_file: str, target_file: Path) -> None:
    """Copy BUNDLE_FILE to TARGET_FILE."""
    _dir, _file = _parse_bundle(bundle_file, dir_only=False)
    if _file is None:
        print(f"{bundle_file} is not a valid file specification")
        raise typer.Exit(1)
    if target_file.exists():
        typer.confirm(f"File {target_file} already exists, overwrite? ",
                      default=False, abort=True)
    _repo = get_repo()
    if _dir is None:
        _bundled_file = _repo / _file
    else:
        _bundled_file = _repo / _dir / _file
    assert_path(_bundled_file)
    _copy(_bundled_file, target_file)

# TODO Add test
# TODO Currently this restores the original file, without link.
#      How should we call a command which restores the file AS LINK?
#      Or add an option "--as-link"
@cli.command()
def restore(bundle_file: str) -> None:
    """Copy BUNDLE_FILE to the location defined by its associated .link file."""
    _dir, _file = _parse_bundle(bundle_file, dir_only=False)
    if not _file:
        print("Invalid path to bundled file")
        raise typer.Exit(1)
    _bundled_file = get_repo() / _dir / _file # type: ignore
    _backlink = _suffix(_bundled_file)
    assert_path(_bundled_file)
    assert_path(_backlink, os.path.lexists)
    # FIXME That does not handle multiple chained links properly
    # A more stable solution would be to iterate over readlink
    # until the bundle target has been reached, and use result n-1
    _target_file = _backlink.readlink()
    if _target_file.exists():
        _target_file.unlink()
    print(f"Restoring {_target_file} from bundle {_dir}")
    _copy(_bundled_file, _target_file)


# TODO Adapt to new argument scheme
# TODO Automatically recognize directories and do rmdir
# TODO Add option -f (don't ask)
# TODO Add option -r (delete recursively)
@cli.command()
def rm(bundle: str, file: Path) -> None:
    """Remove FILE in the bundle and it associated link."""
    pass
    # assert_bundle_arg(bundle)
    # bundle_file = get_bundle(bundle) / file
    # assert_path(bundle_file)
    # link_file = _suffix(bundle_file)
    # if link_file.exists():
    #     link_file.unlink()
    # bundle_file.unlink()


# TODO Add option to not filter ignored files
# TODO Write tests
@cli.command()
def destroy() -> None:
    """Delete the repository."""
    _repo_dir = get_repo()
    _glob = [x for x in _repo_dir.rglob('**/*') if not _ignore(x)]
    _files = [x for x in _glob if x.is_file()]
    _dirs = [x for x in _glob if x.is_dir()]
    n_files = len(_files)
    n_dirs = len(_dirs)
    n_total = n_files + n_dirs
    if n_total > 0 and typer.confirm(f"Deleting the repository would delete {n_files} files and {n_dirs} directories. Proceed?",
                                     default=False, abort=True):
        shutil.rmtree(str(_repo_dir))
    else:
        print("Repository is empty")


# TODO Test manually
@cli.command()
def ls(bundle_dir: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Display the contents of BUNDLE_DIR.
    If no bundle dir is given, list the repository root."""
    _repo = get_repo()
    if bundle_dir is None:
        _dir = _repo
    else:
        _dir, _ = _parse_bundle(bundle_dir, dir_only=True) # type: ignore
        _dir = _repo / _dir
    assert_path(_dir)
    cmd = ["tree", str(_dir)]
    if not shutil.which("tree"):
        print("Binary tree not available")
        raise typer.Exit(1)
    subprocess.call(cmd)


if __name__ == '__main__':
    cli()
