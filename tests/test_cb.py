from __future__ import absolute_import
import pytest
import click
import subprocess
import sys
sys.path.append('../cbundle')
from cbundle import cli as cb  # noqa: E402
from pathlib import Path  # noqa: E402

# -----------------------------------------------------------
# Global Variables and Constants

IGNORE_BUNDLE_ARG = 'ignore_this_arg'

# -----------------------------------------------------------
# FIXTURES

# Function-local fixtures:
#
@pytest.fixture
def test_text_file(tmp_path: Path) -> Path:
    filename = tmp_path / "textfiles"
    filename.mkdir()
    filename = filename / "test.conf"
    with open(filename, 'w') as file:
        file.writelines(['dummy content', 'two lines'])
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


# Session-wide fixtures:
#
# NONE


# -----------------------------------------------------------
# TESTS
#
# Tests for internal functions:

def test_parse_bundle():
    """Test _parse_bundle"""
    with pytest.raises(click.exceptions.Exit):
        assert cb._parse_bundle("")
        assert cb._parse_bundle("/")
        assert cb._parse_bundle("", True)
        assert cb._parse_bundle("/", True)
    tests = [["file", False, (None, Path("file"))],
             ["/file", False, (None, Path("file"))],
             ["dir/", False, (Path("dir/"), None)],
             ["dir/subdir/", False, (Path("dir/subdir"), None)],
             ["/dir/", False, (Path("dir/"), None)],
             ["/dir/subdir/", False, (Path("dir/subdir"), None)],
             ["dir/file", False, (Path("dir"), Path("file"))],
             ["dir/subdir/file", False, (Path("dir/subdir"), Path("file"))],
             ["dir", True, (Path("dir"), None)],
             ["dir/subdir", True, (Path("dir/subdir"), None)],
             ["dir/subdir/subsubdir", True, (Path("dir/subdir/subsubdir"), None)]]
    for arg, dir_only, res in tests:
        print(f"Testing _parse_bundle({arg}{dir_only})")
        assert cb._parse_bundle(arg, dir_only) == res


# def test_get_bundles(empty_dir, monkeypatch):
#     """Test _get_bundles."""
#     path = empty_dir
#     dir_names = ['one', 'two', 'three']
#     for name in dir_names:
#         (path / name).mkdir()
#     for f in cb.get_bundles():
#         assert f in dir_names


def test_move(empty_dir):
    """Test _move."""
    def write_test_file(filename):
        with open(filename, 'w') as file:
            file.writelines(['dummy content', 'two lines'])

    # Test moving to a file
    src_file = empty_dir / "srcfile"
    dest_file = empty_dir / "destfile"
    write_test_file(src_file)
    assert src_file.exists()
    cb._move(src_file, dest_file)
    assert not src_file.exists()
    assert dest_file.exists()

    # Test moving into a dir
    dest_dir = empty_dir / "destdir"
    dest_dir.mkdir()
    cb._move(dest_file, dest_dir)
    assert Path(dest_dir / dest_file.name).exists()


def test_link_back():
    """Test _link_back"""
    pass

# TODO Rewrite using the new bundlepath arg
# def test_bundle_file(test_text_file, empty_dir, monkeypatch):
#     monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
#     cb._bundle_file(test_text_file, empty_dir)
#     moved_file = empty_dir / test_text_file.name
#     # backlink = cb._suffix(moved_file)
#     subprocess.call(["tree", str(test_text_file.parent)])
#     subprocess.call(["tree", str(empty_dir)])
#     assert test_text_file.is_symlink()
#     assert test_text_file.resolve() == moved_file


# -----------------------------------------------------------
# Test CMDs:

def test_cmd_init():
    pass


def test_cmd_add():
    pass


def test_cmd_copy(empty_dir):
    """Test copy"""
    def write_test_file(filename):
        with open(filename, 'w') as file:
            file.writelines(['dummy content', 'two lines'])

    # Test copy to file:
    src_file = empty_dir / "srcfile"
    dest_file = empty_dir / "destfile"
    write_test_file(src_file)
    assert src_file.exists()
    cb._copy(src_file, dest_file)
    assert src_file.exists()
    assert dest_file.exists()

    # Test copy to dir:
    Path(empty_dir / "testdir").mkdir()
    dest_file = empty_dir / "testdir"
    cb._copy(src_file, dest_file)
    assert Path(dest_file / src_file).exists()


def test_cmd_restore():
    pass


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
