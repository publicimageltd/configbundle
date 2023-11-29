from __future__ import absolute_import
import pytest
import click
import sys
sys.path.append('../cbundle')
from cbundle import cli as cb  # noqa: E402
from pathlib import Path  # noqa: E402

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
    print(f"TEST Creating empty dir {filename}")
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


@pytest.fixture(scope="session")
def test_bundle(test_files,
                tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create an example bundle for the tests."""
    bundledir: Path = tmp_path_factory.mktemp("linked-bundle")
    bin_dir = bundledir / "bin"
    data_dir = bundledir / "data"
    for f in test_files:
        link = bundledir / f.name
        link.symlink_to(f)
    data_dir.mkdir()
    bin_dir.mkdir()
    return bundledir


# -----------------------------------------------------------
# TESTS

def test_linked_files(test_text_file_names,
                      test_bundle):
    """Test if linked_files returns the bundle's linked files."""
    # Limit to text files, because the others are in subdirs
    expected_files = [Path(f).name for f in test_text_file_names]
    found_files = cb.linked_files(test_bundle)
    for f in found_files:
        assert f.is_symlink()
    for f in found_files:
        assert f.name in expected_files


def test_get_bundles(empty_dir, monkeypatch):
    """Test if bundle dirs are found."""
    monkeypatch.setattr(cb, "get_repo", lambda: empty_dir)
    path = empty_dir
    dir_names = ['one', 'two', 'three']
    for name in dir_names:
        (path / name).mkdir()
    for f in cb.get_bundles():
        assert f in dir_names


def test_get_link_dir(test_bundle, monkeypatch):
    """Test get_link_dir with a mock bundle."""
    monkeypatch.setattr(cb, "get_bundle", lambda x: test_bundle)
    bundle = "bundle"
    assert cb.get_link_dir(bundle, 'config') == test_bundle
    assert cb.get_link_dir(bundle, 'bin') == test_bundle / "bin"
    assert cb.get_link_dir(bundle, 'data') == test_bundle / "data"


def test_init(empty_dir, monkeypatch):
    monkeypatch.setattr(cb, "get_repo", lambda: empty_dir)
    bundle = 'testbundle'
    cb.init(bundle)
    assert (empty_dir / bundle).is_dir()
    with pytest.raises(click.exceptions.Exit):
        cb.init(bundle)


def test_ln_config_file(empty_dir, test_text_file, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    cb.ln("ignored_argument", test_text_file)
    linkfile = empty_dir / test_text_file.name
    assert linkfile.exists()
    assert linkfile.resolve() == test_text_file.resolve()
    with pytest.raises(click.exceptions.Exit):
        cb.ln('ignored argument', test_text_file)


def test_ln_bin_file(empty_dir, test_text_file, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    cb.ln("ignored_argument", test_text_file, 'bin')
    linkfile = empty_dir / "bin" / test_text_file.name
    print(linkfile)
    assert linkfile.exists()
    assert linkfile.resolve() == test_text_file.resolve()
    with pytest.raises(click.exceptions.Exit):
        cb.ln('ignored argument', test_text_file, 'bin')

def test_cleanup_config(empty_dir, test_text_file, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    linkfile = empty_dir / test_text_file.name
    cb.ln("ignored", test_text_file)
    assert linkfile.exists()
    assert linkfile.is_symlink()
    test_text_file.unlink()
    # exists() follows links, so we cannot check here that
    # the link file still exists.
    # in Python 3.12:  assert linkfile.exists(follow_symlinks=False)
    cb.cleanup("ignored")
    assert not linkfile.is_symlink()
    assert not linkfile.exists()

def test_cleanup_bin(empty_dir, test_text_file, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    linkfile = empty_dir / "bin" / test_text_file.name
    cb.ln("ignored", test_text_file, "bin")
    assert linkfile.exists()
    assert linkfile.is_symlink()
    test_text_file.unlink()
    # exists() follows links, so we cannot check here that
    # the link file still exists.
    # in Python 3.12:  assert linkfile.exists(follow_symlinks=False)
    cb.cleanup("ignored")
    assert not linkfile.is_symlink()
    assert not linkfile.exists()


def test_rm_config_link(empty_dir, test_text_file, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    linkfile = empty_dir / test_text_file.name
    cb.ln("ignore_this", test_text_file)
    assert linkfile.exists()
    assert linkfile.is_symlink()
    cb.rm("ignore this", test_text_file.name)
    assert not linkfile.exists()
    assert test_text_file.exists()
    with pytest.raises(click.exceptions.Exit):
        cb.rm("ignorabimus", test_text_file.name)

def test_link_dir(empty_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    dir_to_link = tmp_path / "targetdir"
    dir_to_link.mkdir()
    cb.ln("ignore", dir_to_link)
    linkfile = empty_dir / "targetdir"
    assert linkfile.exists()
    assert linkfile.is_symlink()
    with pytest.raises(click.exceptions.Exit):
        cb.ln("ignorabimus", dir_to_link)
    

def test_rm_dir(empty_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "get_bundle", lambda x: empty_dir)
    dir_to_link = tmp_path / "targetdir"
    dir_to_link.mkdir()
    cb.ln("ignore", dir_to_link)
    cb.rm("ignore", dir_to_link)
    assert dir_to_link.exists()
    assert not (empty_dir / "targetdir").exists()
    
