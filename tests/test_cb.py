from __future__ import absolute_import
from typing import Any
import pytest
import os
import errno
import click
import typer
import subprocess
import sys
sys.path.append('../cbundle')
from cbundle import cli as cb  # noqa: E402
from pathlib import Path  # noqa: E402

# -----------------------------------------------------------
# Utilities

def _add_if_not_none(p: Path | str,
                     q: Path | str | None) -> Path:
    """Return p/q if q is not None, else p."""
    _res: Path
    if q:
        _res = Path(p) / Path(q)
    else:
        _res = Path(p)
    return _res


def _write_dummy_content(file: Path,
                         content: list[Any] | None = None) -> None:
    """Write some dummy content into FILE."""
    with open(file, 'w') as f:
        f.writelines(content or ['dummy content', 'two lines'])


def _tree(p: Path) -> None:
    """Print directory tree P.
    Only for debugging purposes; does not care about IO Errors."""
    for _line in cb._render_tree(cb._file_tree(p)):
        print(_line)

# -----------------------------------------------------------
# FIXTURES

# Function-local fixtures:
#
@pytest.fixture
def test_text_file(tmp_path: Path) -> Path:
    filename = tmp_path / "textfiles"
    filename.mkdir()
    filename = filename / "test.conf"
    _write_dummy_content(filename)
    return filename


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    """Return an empty directory."""
    filename = tmp_path / "dir"
    filename.mkdir()
    print(f"FIXTURE empty_dir: Creating empty dir {filename}")
    return filename


@pytest.fixture
def empty_repo(empty_dir: Path, monkeypatch) -> Path:
    """Return an empty repo and monkeypatch get_repo."""
    monkeypatch.setattr(cb, "get_repo", lambda: empty_dir)
    return empty_dir


@pytest.fixture(params=["bundledir",
                        "bundledir/"
                        "bundledir/subdir",
                        None])
def req_bundledir_strings(request):
    return request.param


# NOTE As oposed to dirs, file argument 'None' makes no sense
@pytest.fixture(params=["a_file",
                        "bundledir/another_file",
                        "bundledir/subdir/whatafile"])
def req_bundlefile_strings(request):
    return request.param

# Session-wide fixtures:
#
# NONE


# -----------------------------------------------------------
# TESTS
#
# Tests for internal functions:

def test_sanitize_bundle_arg():
    """Test _sanitize_bundle_arg"""
    with pytest.raises(click.exceptions.Exit):
        assert cb._sanitize_bundle_arg("")
        assert cb._sanitize_bundle_arg("/")
        assert cb._sanitize_bundle_arg("")
        assert cb._sanitize_bundle_arg("/")
    assert cb._sanitize_bundle_arg("/file") == "file"
    assert cb._sanitize_bundle_arg("/dir/file") == "dir/file"
    assert cb._sanitize_bundle_arg("dir///file") == "dir/file"
    assert cb._sanitize_bundle_arg("dir/") == "dir/"
    assert cb._sanitize_bundle_arg("/dir/") == "dir/"


# Note _parse_bundle_dir is just wrapping Path(), no need for a test

def test_parse_bundle_file():
    """Test _parse_bundle_file"""
    # NOTE test only what is not already covered by test_sanitize_bundle_arg
    with pytest.raises(click.exceptions.Exit):
        assert cb._parse_bundle_file("dir/")


def test_get_bundle_file(empty_repo, req_bundlefile_strings):
    assert cb._get_bundle_file(req_bundlefile_strings) == Path(empty_repo) / req_bundlefile_strings


def test_get_bundle_dir(empty_repo, req_bundledir_strings):
    assert cb._get_bundle_dir(req_bundledir_strings) == _add_if_not_none(empty_repo, req_bundledir_strings)

def test_get_repo(monkeypatch, empty_dir):
    monkeypatch.setattr(typer, "get_app_dir", lambda _: empty_dir)
    assert cb.get_repo() == empty_dir
    new_dir = empty_dir / "new"
    monkeypatch.setattr(typer, "get_app_dir", lambda _: new_dir)
    assert cb.get_repo() == new_dir
    assert new_dir.exists()
    assert new_dir.is_dir()
    a_file = empty_dir / "a_file"
    _write_dummy_content(a_file)
    monkeypatch.setattr(typer, "get_app_dir", lambda _: a_file)
    with pytest.raises(click.exceptions.Exit):
        cb.get_repo()


def test_bundle_file(test_text_file, empty_dir):
    assert not test_text_file.is_symlink()
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    _tree(test_text_file.parent)
    _tree(empty_dir)
    _bundled_backlink = cb._suffix(_bundled_file)
    assert _bundled_backlink.is_symlink()
    assert os.path.samefile(_bundled_backlink, test_text_file)
    assert test_text_file.is_symlink()
    assert test_text_file.resolve() == _bundled_file
    with pytest.raises(cb.FileAlreadyBundledError):
        cb._bundle_file(_bundled_file, empty_dir)


def test_get_associated_target(test_text_file, empty_dir):
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    assert cb._get_associated_target(_bundled_file) == test_text_file
    _unbundled_file = empty_dir / "iamnotbundled"
    with pytest.raises(cb.NoBacklinkError):
        cb._get_associated_target(_unbundled_file)


def test_restore_copy_overwrite(test_text_file, empty_dir):
    with open(test_text_file, 'r') as f:
        contents = f.read()
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    assert test_text_file.is_symlink()
    cb._restore_copy(_bundled_file, True)
    assert not test_text_file.is_symlink()
    with open(test_text_file, 'r') as f:
        copied_contents = f.read()
    assert contents == copied_contents


def test_restore_copy_no_overwrite(test_text_file, empty_dir):
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    assert test_text_file.is_symlink()
    with pytest.raises(FileExistsError):
        cb._restore_copy(_bundled_file, False)


def test_restore_as_link_overwrite(test_text_file, empty_dir):
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    test_text_file.unlink()
    _write_dummy_content(test_text_file)
    assert test_text_file.exists()
    assert not test_text_file.is_symlink()
    cb._restore_as_link(_bundled_file, True)
    assert test_text_file.is_symlink()


def test_restore_as_link_no_overwrite(test_text_file, empty_dir):
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    test_text_file.unlink()
    _write_dummy_content(test_text_file)
    assert test_text_file.exists()
    assert not test_text_file.is_symlink()
    with pytest.raises(FileExistsError):
        cb._restore_as_link(_bundled_file, False)


# AH, I love testing pure functions!
def test_act_on_path_sucess():
    def _action_fn(p):
        return p
    p = Path.home()
    assert cb._act_on_path(p, _action_fn) == {'path': p,
                                              'result': p,
                                              'success': True}

def test_act_on_path_failure(empty_dir):
    _non_existent_file = Path(empty_dir / "non-existent-file")

    def _action_fn(p):
        _non_existent_file.unlink()

    _result = cb._act_on_path(empty_dir, _action_fn)
    assert _result['path'] == empty_dir
    assert not _result['success']
    # We can't compare the exception directly, for some reason,
    # so we just check the basics:
    assert isinstance(_result['result'], FileNotFoundError)
    assert _result['result'].errno == errno.ENOENT
    assert _result['result'].strerror == os.strerror(errno.ENOENT)


# -----------------------------------------------------------
# Test CMDs:

def test_cmd_add(test_text_file,
                 empty_repo,
                 req_bundledir_strings):
    """Test add"""
    _bundle_str = req_bundledir_strings
    cb.add(test_text_file, _bundle_str)
    _dir = _add_if_not_none(cb.get_repo(), _bundle_str)
    _repo_file = _dir / test_text_file.name
    assert _dir.exists()
    assert _repo_file.exists()
    with pytest.raises(click.exceptions.Exit):
        cb.add(test_text_file, _bundle_str)


def test_cmd_restore_as_file(test_text_file, empty_repo,
                             req_bundledir_strings):
    """Test restoring bundled link as a file."""
    _bundle_str = req_bundledir_strings
    _bundle_dir = _add_if_not_none(cb.get_repo(), _bundle_str)
    _bundle_dir.mkdir(parents=True, exist_ok=True)
    cb._bundle_file(test_text_file, _bundle_dir)
    test_text_file.unlink()
    # Test restoring the bundled file at its original location
    assert not test_text_file.exists()
    if _bundle_str:
        _tmp = Path(_bundle_str) / test_text_file.name #
    else:
        _tmp = test_text_file.name
    _bundle_file_arg = f"{_tmp}"
    _bundle_file = _bundle_dir / test_text_file.name
    cb.restore(_bundle_file_arg)
    assert test_text_file.exists()
    # Test --no-overwrite
    with pytest.raises(click.exceptions.Exit):
        cb.restore(_bundle_file_arg, overwrite=False)
    # Test --as-link
    assert not test_text_file.is_symlink()
    cb.restore(_bundle_file_arg, as_link=True)
    assert test_text_file.is_symlink()
    assert os.path.samefile(test_text_file, _bundle_file)


# TODO Rewrite using the new bundlepath arg
# def test_cmd_rm(empty_bundle):
#     """Test rm"""
#     def write_test_file(filename):
#         with open(filename, 'w') as file:
#             file.writelines(['dummy content', 'two lines'])

#     testfile = empty_bundle / "testfile"
#     linkfile = cb._suffix(testfile)
#     write_test_file(empty_bundle / "testfile")
#     linkfile.symlink_to(testfile)

#     cb.rm(IGNORE_BUNDLE_ARG, testfile)
#     assert not testfile.exists()
#     assert not linkfile.exists()


# TODO Rewrite using the new bundlepath arg
# def test_cmd_rmdir(empty_dir, monkeypatch):
#     monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)

#     def write_test_file(filename):
#         with open(filename, 'w') as file:
#             file.writelines(['dummy content', 'two lines'])

#     Path(empty_dir / "testdir").mkdir()
#     write_test_file(empty_dir / "testfile")
#     write_test_file(empty_dir / "testdir" / "testfile")
#     write_test_file(empty_dir / ".another_testfile")

#     cb.rmdir(IGNORE_BUNDLE_ARG)
#     assert not empty_dir.exists()


def test_cmd_destroy(test_text_file, empty_dir):
    pass


def test_cmd_path():
    pass
