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

def _suffix(file: Path) -> Path:
    """Return FILE with the suffix .link added."""
    return Path(f"{file}.link")


def _has_parents(path: Path) -> bool:
    """Check if PATH has parent directories."""
    return (path.parent == Path('.'))


def _short_bundle_name(path: Path, root: Path | None = None) -> str:
    """Return path as a path relative to ROOT, if possible."""
    if not root:
        _root = get_repo()
    _res = path
    if path.is_relative_to(_root):
        _res = path.relative_to(_root)
    return f"{_res}"


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


def _sanitize_bundle_arg(bundle_arg: str) -> str:
    """Remove unnecessary characters in BUNDLE_ARG."""
    _arg = re.sub("/{2,}", "/", bundle_arg)
    _arg = _arg.lstrip("/")
    if _arg == "" or _arg.isspace():
        print("Bundle specification cannot be empty")
        raise typer.Exit(1)
    return _arg


def _parse_bundle_dir(bundle_dir: str) -> Path:
    """Parse BUNDLE_DIR, returning a directory path."""
    return Path(_sanitize_bundle_arg(bundle_dir))


def _parse_bundle_file(bundle_file: str) -> Path:
    """Parse BUNDLE_FILE, returning a file path.
    A trailing slash will throw an error."""
    _arg = _sanitize_bundle_arg(bundle_file)
    if _arg.endswith("/"):
        print("Bundle path must be a file specification")
        raise typer.Exit(1)
    return Path(_arg)


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
@cli.command()
def add(file: Path,
        bundle_dir: Annotated[Optional[str],
                              typer.Argument(help="Relative path to bundle directory")] = None) -> None:
    "Add FILE to BUNDLE_DIR, replacing it with a link to the bundled file."
    assert_path(file)
    _repo = get_repo()
    _dir = _repo
    if bundle_dir:
        _dir = _dir / _parse_bundle_dir(bundle_dir)
    if Path(_dir / file.name).exists():
        print("File is already bundled")
        raise typer.Exit(1)
    if file.is_symlink() and file.resolve().is_relative_to(_repo):
        _bundled_path_name = _short_bundle_name(file.resolve())
        print(f"File is already bundled in {_bundled_path_name}")
        raise typer.Exit(1)
    _dir.mkdir(parents=True, exist_ok=True)
    _bundle_file(file, _dir)


@cli.command()
def copy(bundle_file: str, target_file: Path) -> None:
    """Copy BUNDLE_FILE to TARGET_FILE."""
    _file = _parse_bundle_file(bundle_file)
    if target_file.exists():
        typer.confirm(f"File {target_file} already exists, overwrite? ",
                      default=False, abort=True)
    _bundled_file = get_repo() / _file
    assert_path(_bundled_file)
    _copy(_bundled_file, target_file)


# TODO Test manually output of --as-link (shortened path)
@cli.command()
def restore(bundle_file: str,
            as_link: Annotated[Optional[bool],
                               typer.Option(help="Restore link to the bundled file")] = False,
            overwrite: Annotated[Optional[bool],
                                 typer.Option(help="Overwrite existing target file")] = True) -> None:
    """Copy BUNDLE_FILE to the location defined by its associated .link file."""
    _file = _parse_bundle_file(bundle_file)
    _bundled_file = get_repo() / _file
    _backlink = _suffix(_bundled_file)
    assert_path(_bundled_file)
    assert_path(_backlink, os.path.lexists)
    # FIXME That does not handle multiple chained links properly
    # A more stable solution would be to iterate over readlink
    # until the bundle target has been reached, and use result n-1
    # See also RM which uses .readlink(), too
    _target_file = _backlink.readlink()

    # Prepare target:
    if _target_file.exists():
        if overwrite:
            _target_file.unlink()
        else:
            print(f"Target file {_target_file} already exists")
            raise typer.Exit(1)

    # Copy the target file or create a link to the bundled file:
    if as_link:
        _target_file.symlink_to(_bundled_file.absolute())
        _shortened_file_name = _short_bundle_name(_bundled_file)
        _action_name = f"{_target_file} linking to {_shortened_file_name}"
    else:
        _copy(_bundled_file, _target_file)
        _action_name = f"{_target_file}"
    print(f"Restoring {_action_name}")


# TODO Write automated test
# TODO Test manually output of confirmation message (shortened file)
@cli.command()
def rm(bundle_file: str,
       force: Annotated[Optional[bool],
                        typer.Option(help="Do not ask for confirmation")] = False) -> None:
    """Remove BUNDLE_FILE and its associated link."""
    _bundle_file = get_repo() / _parse_bundle_file(bundle_file)
    assert_path(_bundle_file)
    _backlink_file = _suffix(_bundle_file)
    if not force:
        _shortened_file_name = _short_bundle_name(_bundle_file)
        _linked_info = ""
        if _backlink_file.exists():
            _backlinked_file = _backlink_file.readlink()
            _linked_shortname = _short_bundle_name(_backlinked_file, Path.home())
            if _backlinked_file.exists():
                _linked_info = f" This will break the link stored in {_linked_shortname}"
        _backlink_action = ""
        if _backlink_file.exists():
            _backlink_action = " and its backlink"
        typer.confirm(f"Delete bundled file {_shortened_file_name}{_backlink_action}?{_linked_info}",
                      default=False, abort=True)
    _backlink_file.unlink(missing_ok=True)
    _bundle_file.unlink()


# TODO Test manually
# TODO Write automated test
@cli.command()
def rmdir(bundle_dir: str,
          force: Annotated[Optional[bool],
                           typer.Option("--force", "-f",
                                        help="Delete non-empty dirs")] = False,
          recursively: Annotated[Optional[bool],
                                 typer.Option("--recurse", "-r",
                                              help="Recursively delete subdirectories")] = False):
    """Delete bundle directory BUNDLE_DIR."""
    _dir = get_repo() / _parse_bundle_dir(bundle_dir)
    _dir_name = _short_bundle_name(_dir)
    assert_path(_dir)
    _contents = _dir.rglob('**')
    if _contents and not force:
        print(f"{_dir_name} is not empty. Use --force to delete anyways.")
        raise typer.Exit(1)
    _dirs = [x for x in _contents if x.is_dir()]
    if _dirs and not force and not recursively:
        print("f{_dir_name} contains directories. Use --recursive or --force to delete subdirectories")
    shutil.rmtree(str(_dir))


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


# TODO Implement tree instead of calling external binary
@cli.command()
def ls(bundle_dir: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Display the contents of BUNDLE_DIR.
    If no bundle dir is given, list the repository root."""
    _repo = get_repo()
    if bundle_dir is None:
        _dir = _repo
    else:
        _dir = _repo / _parse_bundle_dir(bundle_dir)
    assert_path(_dir)
    if not _dir.is_dir():
        print(f"{_dir} is not a directory")
        raise typer.Exit(1)
    cmd = ["tree", str(_dir)]
    if not shutil.which("tree"):
        print("Binary tree not available")
        raise typer.Exit(1)
    subprocess.call(cmd)


if __name__ == '__main__':
    cli()
