from __future__ import absolute_import
import pytest
import click
import sys
sys.path.append('../cbundle')
from cbundle import cli as cb  # noqa: E402
from pathlib import Path  # noqa: E402

# -----------------------------------------------------------
# Global Variables and Constants

IGNORE_BUNDLE_ARG = 'ignore_this_arg'

# -----------------------------------------------------------
# FIXTURES

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


@pytest.fixture(scope="session")
def test_text_file_names() -> list[str]:
    return ['one.config', 'two.rc', '.three']


@pytest.fixture(scope="session")
def test_bin_file_names() -> list[str]:
    return ['binary', 'startme']


@pytest.fixture(scope="session")
def test_files(test_text_file_names,
               test_bin_file_names,
               tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """Create a directory with pseudo text and binary files."""
    filedir: Path = tmp_path_factory.mktemp("files")
    res = []
    for name in test_text_file_names:
        filename = filedir / name
        with open(filename, 'w') as file:
            file.writelines('dummy content')
            res.append(filename)

    for name in test_bin_file_names:
        filename = filedir / name
        with open(filename, 'w') as file:
            file.writelines(["#!/usr/bin/bash", "echo 'hallo'"])
        filename.chmod(0o777)
    return res


# -----------------------------------------------------------
# TESTS


def test_get_bundles(empty_dir, monkeypatch):
    """Test _get_bundles: if bundle dirs are found."""
    monkeypatch.setattr(cb, "get_repo", lambda: empty_dir)
    path = empty_dir
    dir_names = ['one', 'two', 'three']
    for name in dir_names:
        (path / name).mkdir()
    for f in cb.get_bundles():
        assert f in dir_names


def test_init(empty_dir, monkeypatch):
    monkeypatch.setattr(cb, "get_repo", lambda: empty_dir)
    bundle = 'testbundle'
    cb.init(bundle)
    assert (empty_dir / bundle).is_dir()
    with pytest.raises(click.exceptions.Exit):
        cb.init(bundle)


def test_move(empty_dir):

    def write_test_file(filename):
        with open(filename, 'w') as file:
            file.writelines(['dummy content', 'two lines'])

    src_file = empty_dir / "srcfile"
    dest_file = empty_dir / "destfile"
    write_test_file(src_file)
    assert src_file.exists()
    cb._move(src_file, dest_file)
    assert not src_file.exists()
    assert dest_file.exists()

def test_copy(empty_dir):

    def write_test_file(filename):
        with open(filename, 'w') as file:
            file.writelines(['dummy content', 'two lines'])

    # Copy to file:
    src_file = empty_dir / "srcfile"
    dest_file = empty_dir / "destfile"
    write_test_file(src_file)
    assert src_file.exists()
    cb._copy(src_file, dest_file)
    assert src_file.exists()
    assert dest_file.exists()
    # Copy to dir:
    Path(empty_dir / "testdir").mkdir()
    dest_file = empty_dir / "testdir"
    cb._copy(src_file, dest_file)
    assert Path(dest_file / src_file).exists()



def test_rm(empty_dir, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)

    def write_test_file(filename):
        with open(filename, 'w') as file:
            file.writelines(['dummy content', 'two lines'])

    testfile = empty_dir / "testfile"
    linkfile = testfile.with_suffix(cb.LINK_SUFFIX)
    write_test_file(empty_dir / "testfile")
    linkfile.symlink_to(testfile)

    cb.rm(IGNORE_BUNDLE_ARG, testfile)
    assert not testfile.exists()
    assert not linkfile.exists()


def test_rmdir(empty_dir, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)

    def write_test_file(filename):
        with open(filename, 'w') as file:
            file.writelines(['dummy content', 'two lines'])

    Path(empty_dir / "testdir").mkdir()
    write_test_file(empty_dir / "testfile")
    write_test_file(empty_dir / "testdir" / "testfile")
    write_test_file(empty_dir / ".another_testfile")

    cb.rmdir(IGNORE_BUNDLE_ARG)
    assert not empty_dir.exists()
