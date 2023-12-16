#!/usr/bin/python
from pathlib import Path
import os
import errno
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

# Custom Exceptions:


class NoBacklinkError(FileNotFoundError):
    """No associated backlink file found."""
    # __init__ mit (errno, message, filename)


class InvalidBundleSpecification(Exception):
    """Bundle Specification is invalid (empty or otherwise flawed)."""


# TODO Implement this error in add
class FileAlreadyBundledError(Exception):
    """File already exists in bundle."""
    file: Path
    bundle: str

    def __init__(self, file, bundle, *args, **kwargs):
        self.file = file
        self.bundle = bundle
        super().__init__(*args, **kwargs)


# -----------------------------------------------------------
# Utilities

def _suffix(file: Path) -> Path:
    """Return FILE with the suffix .link added."""
    return Path(f"{file}.link")


def _is_suffixed(file: Path) -> bool:
    """Check if FILE has the suffix .link"""
    return file.suffix == ".link"


def _has_parents(path: Path) -> bool:
    """Check if PATH has parent directories."""
    return (path.parent == Path('.'))


def _rooted_name(path: Path, root: Path | None = None) -> str:
    """Return path as a path relative to ROOT, if possible."""
    _root_str = ""
    if not root:
        _root = get_repo()
        _root_str = "bundle path "
    else:
        _root = root
        if root == Path.home():
            _root_str = "~/"
    _res = path
    if path.is_relative_to(_root):
        _res = path.relative_to(_root)
    return f"{_root_str}{_res}"


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
    """Return the path to the bundle repository, possibly creating it on the fly."""
    repo_path = Path(typer.get_app_dir(APP_NAME))
    if not repo_path.exists():
        repo_path.mkdir(parents=True, exist_ok=True)
    assert_path(repo_path, Path.is_dir, msg="Error: {p} is not a directory, cannot proceed")
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
    file.symlink_to(bundled_file)


def _get_associated_target(file: Path) -> Path:
    """Get the target file associated with FILE via backlink.
    Raise a NoBackLinkError if no backlink has been found.
    Do not check whether the target file exists."""
    _backlink = _suffix(file)
    try:
        _target_file = _backlink.readlink()
    except FileNotFoundError as err:
        raise NoBacklinkError(err.errno, f"File {file} has no backlink file", err.filename)
    return _target_file


def _restore_copy(bundled_file: Path, overwrite: bool) -> Path:
    """Copy BUNDLED_FILE into the target defined by its backlink file.
    If OVERWRITE is True, overwrite existing files, else raise an error.
    Return the Path to the restored file."""
    _target_file = _get_associated_target(bundled_file)
    if not overwrite and _target_file.exists():
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), f"{_target_file}")
    # Delete target to avoid symlink looping
    _target_file.unlink(missing_ok=True)
    _copy(bundled_file, _target_file)
    return _target_file


def _restore_as_link(bundled_file: Path, overwrite: bool) -> Path:
    """Create a link to BUNDLED_FILE at the target defined by its backlink file.
    If OVERWRITE is True, overwrite existing files, else raise an error.
    Return the Path to the link file."""
    _target_file = _get_associated_target(bundled_file)
    if not overwrite and _target_file.exists():
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), f"{_target_file}")
    _target_file.unlink(missing_ok=True)
    _target_file.symlink_to(bundled_file.absolute())
    return _target_file


def _remove_bundle_and_backlink(bundled_file: Path) -> None:
    """Remove the bundle and its backlink file.
    Do not raise an error if no backlink file is found."""
    _backlink = _suffix(bundled_file)
    bundled_file.unlink(missing_ok=True)
    _backlink.unlink(missing_ok=True)


# -----------------------------------------------------------
# TODO CLI allow to add multiple files by using multiple arguments
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
        _bundled_path_name = _rooted_name(file.resolve())
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


@cli.command()
def restore(bundle_file: str,
            as_link: Annotated[Optional[bool],
                               typer.Option(help="Restore link to the bundled file")] = False,
            overwrite: Annotated[Optional[bool],
                                 typer.Option(help="Overwrite existing target file")] = True,
            remove: Annotated[Optional[bool],
                              typer.Option(help="Delete bundled file after restoring target")] = False) -> None:
    """Copy BUNDLE_FILE to the location defined by its associated .link file."""
    _bundled_file = get_repo() / _parse_bundle_file(bundle_file)
    assert_path(_bundled_file)
    _overwrite = bool(overwrite) # Silence type checker
    if remove and as_link:
        print("Option --remove cannot be used when restoring as link")
        raise typer.Exit(1)
    _action_name: str
    try:
        if as_link:
            _target_file = _restore_as_link(_bundled_file, _overwrite)
            _action_name = f"{_target_file} now links to {_bundled_file}"
        else:
            _target_file = _restore_copy(_bundled_file, _overwrite)
            _action_name = f"Restored {_target_file}"
    except (NoBacklinkError, FileExistsError) as err:
        print(err)
        raise typer.Exit(1)
    if remove:
        _remove_bundle_and_backlink(_bundled_file)
    print(_action_name)


# TODO Write automated test
# TODO Test manually output of confirmation message (shortened file)
@cli.command()
def rm(bundle_file: str,
       force: Annotated[Optional[bool],
                        typer.Option("--force", "-f",
                                     help="Do not ask for confirmation")] = False) -> None:
    """Remove BUNDLE_FILE and its associated link."""
    _bundled_file = get_repo() / _parse_bundle_file(bundle_file)
    assert_path(_bundled_file)
    _backlink_file = _suffix(_bundled_file)
    if not force:
        # - Prepare permission for the deletion
        _shortened_bundle_file = _rooted_name(_bundled_file)
        if _backlink_file.exists():
            _shortened_bundle_file += 'and its associated backlink'
        # - Prepare warning if backlink points to a link, which would thus be broken:
        _broken_link_warning = ''
        try:
            _target_file = _get_associated_target(_bundled_file)
        except NoBacklinkError:
            _target_file = None
        if _target_file and _target_file.is_symlink():
            _shortened_target_file = _rooted_name(_target_file, Path.home())
            _broken_link_warning = f" This will break the link stored in {_shortened_target_file}"
        typer.confirm(f"Delete bundled file {_shortened_bundle_file}{_broken_link_warning}",
                      default=False, abort=True)
    _backlink_file.unlink(missing_ok=True)
    _bundled_file.unlink()


# TODO Test manually
# TODO Write automated test
@cli.command()
def rmdir(bundle_dir: str,
          force: Annotated[Optional[bool],
                           typer.Option("--force", "-f",
                                        help="Delete non-empty dirs")] = False) -> None:
    """Delete bundle directory BUNDLE_DIR and all of its subdirectories."""
    _dir = get_repo() / _parse_bundle_dir(bundle_dir)
    _dir_name = _rooted_name(_dir)
    assert_path(_dir)
    if _dir.glob("*") and not force:
        print(f"{_dir_name} is not empty. Use --force to delete anyways")
        raise typer.Exit(1)
    shutil.rmtree(str(_dir))


# TODO Test deletion of subdirs if some files are skipped
@cli.command()
def unbundle(bundle_dir: Annotated[Optional[str],
                                   typer.Argument()] = None) -> None:
    """Restore BUNDLE_FILE_OR_DIR and delete bundled files.
    Note: This uncondtionally replaces all backlinked files with the bundled files."""
    # First determine what is to be deleted
    _bundle_dir = get_repo()
    if bundle_dir:
        _bundle_dir = _bundle_dir / _parse_bundle_dir(bundle_dir)
    else:
        typer.confirm("Are you sure you want to unbundle the whole repository?",
                      default=False, abort=True)
    # Now do the deletion
    _delete_dirs: list[str] = []
    _repo = get_repo()
    for _root, _dirs, _files in os.walk(str(_bundle_dir), topdown=False):
        print("Looking for bundled files...")
        _delete_dirs.append(_root)
        for _file in filter(lambda f: not (_ignore(f) or _is_suffixed(f)), map(Path, _files)):
            _src_file = Path(_root) / _file
            _src_file_name = _rooted_name(_src_file, _repo)
            try:
                _target_file = _restore_copy(_src_file, True)
                print(f"Restoring {_target_file} from {_src_file_name}")
            except NoBacklinkError:
                print(f"{_src_file_name} WARNING: No backlink file found, skipping")
                _delete_dirs.pop()
    for _dir in _delete_dirs[::-1]:
        print(f"Deleting {_dir}")
        shutil.rmtree(_dir)
#    subprocess.call(["tree", str(_bundle_dir)])

# TODO Write tests
@cli.command()
def destroy() -> None:
    """Delete the repository and its containing directory."""
    _repo_dir = Path(typer.get_app_dir(APP_NAME))
    if not _repo_dir.exists():
        print("There is no repository to delete")
        raise typer.Exit(1)
    assert_path(_repo_dir, Path.is_dir, msg="Error: {p} is not a directory, cannot proceed")
    # _is_empty = bool(_repo_dir.glob('*'))
    typer.confirm(f"Delete the repository at {_repo_dir} and everything it contains?",
                  default=False, abort=True)
    shutil.rmtree(str(_repo_dir))


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
