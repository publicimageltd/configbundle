#!/usr/bin/python
from pathlib import Path
import os
import errno
from typing import Callable, Optional, Union, Any
from operator import itemgetter
from itertools import filterfalse
from functools import partial
from typing_extensions import Annotated
import sys
import re
import shutil
# Hack to disable rich output
sys.modules['rich'] = None  # type: ignore
import typer  # noqa: E402


# TODO Rewrite Tests
# TODO Turn assert_xx into validations using Typer
#
# -----------------------------------------------------------
# Global Declarations

APP_NAME = 'configbundle'
cli = typer.Typer(no_args_is_help=True)


class NoBacklinkError(FileNotFoundError):
    """No associated backlink file found."""
    # __init__ mit (errno, message, filename)


class InvalidBundleSpecificationError(Exception):
    """Bundle Specification is invalid (empty or otherwise flawed)."""


class FileAlreadyBundledError(FileExistsError):
    """File already exists in bundle."""


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


def _is_subpath_of(sub: Path, root: Path) -> bool:
    """Check if P1 is a subpath of p2.
    Both paths must be either relative or absolute."""
    try:
        return Path(os.path.commonpath([sub, root])) == root
    except ValueError:
        return False


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
                assertion: Callable[[Path], bool],
                msg: str | None,
                cancel: bool = True) -> bool:
    """Check if path P satisfies ASSERTION, exiting if CANCEL is True."""
    result = assertion(p)
    if not result:
        if msg:
            print(msg.format(p=p))
        if cancel:
            raise typer.Exit(1)
    return result


def assert_exists(p):
    """Raise an error if P does not exist."""
    assert_path(p, Path.exists, msg="{p} does not exist")


def assert_is_dir(p: Path) -> None:
    """Raise an error if P is not a directory."""
    assert_path(p, Path.is_dir, msg="{p} is not a directory")

def assert_is_no_symlink(p: Path) -> None:
    """Raise an error if P is not a symlink."""
    assert_path(p, lambda x: not Path.is_symlink(x), msg="{p} cannot be a symlink")


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


def _get_bundle_dir(bundle_dir: str | None) -> Path:
    """Return BUNDLE_DIR within the repository."""
    _dir = get_repo()
    if bundle_dir:
        _dir = _dir / _parse_bundle_dir(bundle_dir)
    return _dir


def _get_bundle_file(bundle_file: str) -> Path:
    """Return BUNDLE_FILE within the repository."""
    return get_repo() / _parse_bundle_file(bundle_file)


# NOTE No tests
def _ignore(file: Path) -> bool:
    """Return False when file is a bundle file."""
    res = False
    res = file.match(".gitignore")
    res = file.match(".git")
    return res


# NOTE No tests
def _relevant_files(bundle_dir: Path) -> list[Path]:
    """Filter out ignored files in BUNDLE_DIR (recursing)."""
    return list(filter(lambda x: not _ignore(x),
                       bundle_dir.rglob('*')))

# NOTE No tests
def _files_first(pathlist: list[Path]) -> list[Path]:
    """Sort PATHLIST with files first."""
    return sorted(pathlist,
                  key=lambda x: len(x.parts), reverse=True)

# -----------------------------------------------------------
# File and dir functions

# NOTE No tests
def _file_tree(p: Path) -> dict[str, Any]:
    """Recursively build a tree-like dictionary reflecting the contents of P.

    Return a dictionary with the following structure:

       {'path': Pathobject,
        'name': Path.name,
        'type': one of 'link', 'file' or 'dir'}

    Additionally, depending on the 'type', also add the following keys:

        'contents': list of entries of that directory
        'target': target of the link
    """
    _dict: dict[str, Any] = {'path': p,
                             'name': p.name}
    if p.is_dir():
        _dict['type'] = 'dir'
        _dict['contents'] = list(map(_file_tree, p.glob('*')))
    else:
        _dict['type'] = 'file'
        if p.is_symlink():
            _dict['type'] = 'link'
            _dict['target'] = p.readlink()
    return _dict


# NOTE No tests
def _render_tree(entry: dict[str, Any],
                 depth: int = 0,
                 tree_char: str = "") -> list[str]:
    """Recursively render a directory tree stored in ENTRY.
    Return a list of strings representing ENTRY and, if given,
    its subdirectories.

    Typical usage: _render_tree(_file_tree(Path("/home/user/")))

    DEPTH and TREE_CHAR are internal arguments for recursion."""
    _name = f"{tree_char}─{entry['name']}"
    _res: list[str]
    match entry['type']:
        case 'file':
            _res = [_name]
        case 'link':
            _res = [ _name + f" -> {entry['target']}"]
        case 'dir':
            _res = [ _name + "/"]
            if entry['contents']:
                # Recursion hack: We can't know beforehand if we are
                # the last subtree, so we change the drawing after the
                # fact.  If the argument passed to tree_char below
                # changes (e.g. some spaces after f"{_char}"), this
                # hack has to be adapted accordingly.
                if depth > 0:
                    tree_char = tree_char[:-1] + "│"
                # Construct array (└ or ├, ├ ..., └)
                _n = len(entry['contents'])
                if _n == 1:
                    _tree_chars = ["└"]
                else:
                    _first_char = "├"
                    _middle = ["├"] * (_n - 2) # this can be an empty list
                    _last_char = "└"
                    _tree_chars = [_first_char] + _middle + [_last_char]
                # poor man's mapcat:
                for _e, _char in zip(entry['contents'], _tree_chars):
                    _res += _render_tree(_e, depth + 1, f"{tree_char} {_char}")
        case _:
            raise ValueError(entry['type'])
    return [str(x) for x in _res]


def get_repo() -> Path:
    """Return the path to the bundle repository, possibly creating it on the fly."""
    repo_path = Path(typer.get_app_dir(APP_NAME))
    if not repo_path.exists():
        repo_path.mkdir(parents=True, exist_ok=True)
    assert_path(repo_path, Path.is_dir, msg="Error: {p} is not a directory, cannot proceed")
    return repo_path


def _bundle_file(file: Path, bundle_dir: Path) -> Path:
    """Move FILE into BUNDLE_DIR and replace FILE with a link pointing to the bundled file.
    Additionally create a backlink in the bundle dir.
    Throw an error if bundled file or backlink already exist.
    Return the bundled file."""
    _bundled_file = bundle_dir.absolute() / file.name
    _link_file = _suffix(_bundled_file)
    # FIXME These assertions should be somewhere else
    if _bundled_file.exists():
        raise FileAlreadyBundledError(errno.EEXIST, os.strerror(errno.EEXIST), f"{_bundled_file}")
    if _link_file.exists():
        raise FileAlreadyBundledError(errno.EEXIST, os.strerror(errno.EEXIST), f"{_link_file}")
    shutil.move(str(file), str(_bundled_file))
    _link_file.symlink_to(file.absolute())
    file.symlink_to(_bundled_file)
    return _bundled_file


def _get_associated_target(file: Path) -> Path:
    """Get the target file associated with FILE via backlink.
    Raise a NoBackLinkError if no backlink has been found.
    Do not check whether the target file exists."""
    _backlink = _suffix(file)
    try:
        _target_file = _backlink.readlink()
    except FileNotFoundError as err:
        raise NoBacklinkError(errno.ENOENT, f"File {file} has no backlink file", err.filename)
    except OSError as err:
        if err.errno == errno.EINVAL:   # 'Invalid Argument'
            raise NoBacklinkError(errno.ENOENT, "Backlink file is invalid", f"{_backlink}")
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
    shutil.copy2(str(bundled_file), str(_target_file))
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


# NOTE No tests
def _restore_dry_run(bundled_file: Path, overwrite: bool) -> Path:
    """Only simulate restoring (copy).
    Check for files, but do nothing with them."""
    _target_file = _get_associated_target(bundled_file)
    if not overwrite and _target_file.exists():
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), f"{_target_file}")
    return _target_file


def _act_on_path(path: Path,
                 action_fn: Callable[[Path], Path]) -> dict:
    """Act on PATH, storing the result in a dictionary.
    Return a dictionary {'path', 'result', 'sucess'} with the path name,
    the result of calling ACTION_FN with the path, and a boolean
    indicating the success."""
    _result: Union[Path, OSError]
    _success: bool
    try:
        _result = action_fn(path)
        _success = True
    except OSError as err:
        _result = err
        print(err)
        _success = False
    return {'path': path,
            'result': _result,
            'success': _success}


def _act_on_paths(paths: list[Path],
                  action_fn: Callable[[Path], Path]) -> list[dict]:
    """Act on each path in PATHS for side-effects and store the results.
    Return a list of dicts with the path name and the the result or the
    error code, respectively. The value 'success' stores whether an error
    occured or not."""
    return [_act_on_path(p, action_fn) for p in paths]


def _split_results(results: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split results into successful tries and failures."""
    return (list(filter(itemgetter('success'), results)),
            list(filterfalse(itemgetter('success'), results)))


# NOTE No tests
def _restore_dir_copy(bundle_dir: Path, overwrite: bool) -> list[dict]:
    """Restore (copy) all files bundled in BUNDLE_DIR and subdirectories."""
    def _restore_fn(p: Path) -> Path:
        return _restore_copy(p, overwrite)
    return _act_on_paths(_relevant_files(bundle_dir), _restore_fn)


# NOTE No tests
def _restore_dir_as_link(bundle_dir: Path, overwrite: bool) -> list[dict]:
    """Restore (as link) all files bundled in BUNDLE_DIR and its subdirectories."""
    def _restore_fn(p: Path) -> Path:
        return _restore_as_link(p, overwrite)
    return _act_on_paths(_relevant_files(bundle_dir), _restore_fn)


# NOTE No tests
def _restore_dir_dry_run(bundle_dir: Path, overwrite: bool) -> list[dict]:
    """Restore (dry run) all files bundled in BUNDLE_DIR and its subdirectories."""
    def _restore_fn(p: Path) -> Path:
        return _restore_dry_run(p, overwrite)
    return _act_on_paths(_relevant_files(bundle_dir), _restore_fn)


def _removable(result_list: list[dict]) -> list[Path]:
    """Return all paths with successful action which do not contain a failed path."""
    _successes, _failures = _split_results(result_list)
    _files = list(map(itemgetter("path"), _successes))
    for _path in map(itemgetter("path"), _failures):
        _files = [x for x in _files if x not in _path.parents]
    return _files


def _rm_file_and_backlink(bundled_file: Path) -> None:
    """Remove the bundle file and its associated backlink file.
    Do not raise an error if no backlink file is found."""
    _backlink = _suffix(bundled_file)
    bundled_file.unlink(missing_ok=True)
    _backlink.unlink(missing_ok=True)


# -----------------------------------------------------------
# CLI Commands

# TODO CLI allow to add multiple files by using multiple arguments
@cli.command()
def add(file: Path,
        bundle_dir: Annotated[Optional[str],
                              typer.Argument(help="Bundle directory")] = None) -> None:
    "Add FILE to BUNDLE_DIR, replacing it with a link to the bundled file."
    assert_exists(file)
    assert_is_no_symlink(file)
    _dir = _get_bundle_dir(bundle_dir)
    _dir.mkdir(parents=True, exist_ok=True)
    try:
        _bundle_file(file, _dir)
    except FileAlreadyBundledError as err:
        print(err)
        raise typer.Exit(1)


@cli.command()
def copy(bundle_file: str, target_file: Path) -> None:
    """Copy BUNDLE_FILE to TARGET_FILE."""
    _bundled_file = _get_bundle_file(bundle_file)
    assert_exists(_bundled_file)
    if target_file.exists():
        typer.confirm(f"File {target_file} already exists, overwrite? ",
                      default=False, abort=True)
    try:
        shutil.copy2(str(_bundled_file), str(target_file))
    except OSError as err:
        print(err)
        raise typer.Exit(1)


# TODO Check tests
# FIXME Instead of calling remove explicitly, why not "chain on success"?
@cli.command()
def restore(bundle_file: str,
            as_link: Annotated[Optional[bool],
                               typer.Option(help="Restore link to the bundled file")] = False,
            overwrite: Annotated[Optional[bool],
                                 typer.Option(help="Overwrite existing target file")] = True,
            remove: Annotated[Optional[bool],
                              typer.Option(help="Delete bundled file after restoring target")] = False) -> None:
    """Copy BUNDLE_FILE to the location defined by its associated .link file."""
    _bundled_file = _get_bundle_file(bundle_file)
    assert_exists(_bundled_file)
    if _bundled_file.is_dir():
        print(f"{bundle_file} must be a file. To restore whole directories, use unbundle")
    if remove and as_link:
        print("Option --remove cannot be used when restoring as a link")
        raise typer.Exit(1)

    _action: dict
    if as_link:
        _action = {'fn': partial(_restore_as_link, overwrite=overwrite),
                   'msg': "{path} now links to {result}"}
    else:
        _action = {'fn': partial(_restore_copy, overwrite=overwrite),
                   'msg': "Restored {result}"}

    _result = _act_on_path(_bundled_file, _action['fn'])
    if remove:
        _rm_file_and_backlink(_bundled_file)

    if _result['success']:
        str.format(_action['msg'], **_result)
    else:
        print(_result['result'])
        raise typer.Exit(1)


# TODO Write automated test
# TODO Test manually output of confirmation message (shortened file)
@cli.command()
def rm(bundle_file: str,
       force: Annotated[Optional[bool],
                        typer.Option("--force", "-f",
                                     help="Do not ask for confirmation")] = False) -> None:
    """Remove BUNDLE_FILE and its associated link."""
    _bundled_file = _get_bundle_file(bundle_file)
    assert_exists(_bundled_file)
    _backlink_file = _suffix(_bundled_file)
    # Create explicit warning if --force is not set:
    if not force:
        _backlink_warning = ''
        if _backlink_file.exists():
            _backlink_warning = " and its associated backlink"
        _target_warning = ''
        try:
            _target_file = _get_associated_target(_bundled_file)
        except NoBacklinkError:
            _target_file = None
        if _target_file and _target_file.is_symlink():
            _target_warning = f" This will break the link stored in {_rooted_name(_target_file, Path.home())}"
        msg = f"Delete {_rooted_name(_bundled_file)}{_backlink_warning}?{_target_warning}"
        typer.confirm(msg, default=False, abort=True)
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
    _dir = _get_bundle_dir(bundle_dir)
    assert_exists(_dir)
    if _dir.glob("*") and not force:
        _dir_name = _rooted_name(_dir)
        print(f"{_dir_name} is not empty. Use --force to delete anyways")
        raise typer.Exit(1)
    shutil.rmtree(str(_dir))


# TODO Write test
@cli.command()
def unbundle(bundle_dir: Annotated[Optional[str],
                                   typer.Argument()] = None) -> None:
    """Restore BUNDLE_DIR and delete bundled files.
    Note: This uncondtionally replaces all backlinked files with the bundled files."""
    if not bundle_dir:
        typer.confirm("Are you sure you want to unbundle the whole repository?",
                      default=False, abort=True)

    _bundle_dir = _get_bundle_dir(bundle_dir)
    # NOTE Dry run active!
#    _results = _restore_dir_copy(_bundle_dir, True)
    _results = _restore_dir_dry_run(_bundle_dir, True)
    _restored, _failed = _split_results(_results)
    for _dict in _restored:
        print(f"{_dict['path']} has been restored as {_dict['result']}")
    for _dict in _failed:
        print(f"{_dict['path']} could not be restored: {_dict['result']}")
    for _path in _files_first(_removable(_results)):
        print(f"Deleting {_path}")


# TODO Write tests
@cli.command()
def destroy() -> None:
    """Delete the repository and its containing directory."""
    _repo_dir = Path(typer.get_app_dir(APP_NAME))
    if not _repo_dir.exists():
        print("There is no repository to delete")
        raise typer.Exit(1)
    assert_path(_repo_dir, Path.is_dir, msg="Error: {p} is not a directory, cannot proceed")
    typer.confirm(f"Delete the repository at {_repo_dir} and everything it contains?",
                  default=False, abort=True)
    shutil.rmtree(str(_repo_dir))


# TODO Implement tree instead of calling external binary
@cli.command()
def ls(bundle_dir: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Display the contents of BUNDLE_DIR.
    If no bundle dir is given, list the repository root."""
    _dir = _get_bundle_dir(bundle_dir)
    assert_exists(_dir)
    assert_is_dir(_dir)
    try:
        _list = _file_tree(_dir)
    except OSError as err:
        print(err)
        raise typer.Exit(1)
    for _line in _render_tree(_list):
        print(_line)


if __name__ == '__main__':
    cli()
