from __future__ import absolute_import
from typing import Any
import pytest
import os
import errno
import click
import typer
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


class TestBundleFile:

    def test_with_normal_dir(self, test_text_file, empty_dir):
        _bundled_file = cb._bundle_file(test_text_file, empty_dir)
        _bundled_backlink = cb._suffix(_bundled_file)
        assert _bundled_backlink.is_symlink()
        assert os.path.samefile(_bundled_backlink, test_text_file)
        assert test_text_file.is_symlink()
        assert test_text_file.resolve() == _bundled_file


    def test_with_non_existent_dir(self, test_text_file, empty_dir):
        _dir = empty_dir / "non-existing-dir"
        with pytest.raises(FileNotFoundError):
            _ = cb._bundle_file(test_text_file, _dir)


    def test_adding_to_existent_file(self, test_text_file, empty_dir):
        _ = cb._bundle_file(test_text_file, empty_dir)
        with pytest.raises(cb.FileAlreadyBundledError):
            cb._bundle_file(test_text_file, empty_dir)


def test_get_associated_target(test_text_file, empty_dir):
    _bundled_file = cb._bundle_file(test_text_file, empty_dir)
    assert cb._get_associated_target(_bundled_file) == test_text_file
    _unbundled_file = empty_dir / "iamnotbundled"
    with pytest.raises(cb.NoBacklinkError):
        cb._get_associated_target(_unbundled_file)


class TestRestoreFNs:

    bundled_file: Path
    backlink: Path
    target_file: Path

    @pytest.fixture
    def setup(self, test_text_file, empty_dir):
        self.bundled_file = cb._bundle_file(test_text_file, empty_dir)
        self.target_file = test_text_file
        self.backlink = cb._suffix(self.bundled_file)
        assert self.target_file.is_symlink()
        assert self.bundled_file.exists()
        assert self.backlink.exists()
        assert self.backlink.is_symlink()


    def test_copy_overwrite(self, setup):
        with open(self.bundled_file, 'r') as f:
            contents = f.read()
        cb._restore_copy(self.bundled_file, overwrite=True)
        assert not self.target_file.is_symlink()
        with open(self.target_file, 'r') as f:
            copied_contents = f.read()
        assert contents == copied_contents


    def test_copy_no_overwrite(self, setup):
        with pytest.raises(FileExistsError):
            cb._restore_copy(self.bundled_file, overwrite=False)


    def test_restore_as_link_overwrite(self, setup):
        # Replace link with regular file
        self.target_file.unlink()
        _write_dummy_content(self.target_file)
        assert self.target_file.exists()
        # And restore bundled file 'over' it:
        cb._restore_as_link(self.bundled_file, overwrite=True)
        assert self.target_file.is_symlink()


    def test_restore_as_link_no_overwrite(self, setup):
        # Replace link with regular file
        self.target_file.unlink()
        _write_dummy_content(self.target_file)
        assert self.target_file.exists()
        # And try to restore bundled file 'over' it:
        with pytest.raises(FileExistsError):
            cb._restore_as_link(self.bundled_file, overwrite=False)


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


# NOTE No need to test failing results
def test_act_on_paths_success():
    _chain = []

    def _action_fn(p):
        _chain.append(str(p))
        return p

    _paths = ["/a", "directory", "a/bba", "very/nested/stuff"]
    _result = cb._act_on_paths(_paths, _action_fn)

    assert _chain == [str(x) for x in _paths]
    assert all(entry['success'] for entry in _result)


def test_split_results():

    def _action_fn(p):
        if p == Path("failure"):
            raise FileNotFoundError()
        else:
            return p

    _expected_results = [False, True, True, False, False]
    _input = map(lambda p: Path("success" if p else "failure"),
                 _expected_results)
    _results = cb._act_on_paths(_input, _action_fn)
    _success, _failures = cb._split_results(_results)
    assert len(_success) == 2
    assert len(_failures) == 3
    assert all([entry['success'] for entry in _success])
    assert not any([entry['success'] for entry in _failures])


def test_removable():
    def _fail(p):
        def _action_fn(p):
            raise FileNotFoundError()
        return cb._act_on_path(Path(p), _action_fn)

    def _okay(p):
        def _action_fn(p):
            return p
        return cb._act_on_path(Path(p), _action_fn)

    # The files marked with comments should be returned -----------------------#
    _results = [_okay("/home/user/config/subdir/file"),                        #
                _okay("/home/user/config/subdir/file.link"),                   #
                _okay("/home/user/config/subdir"),                             # x
                _okay("/home/user/config/whatadir"),                           # x
                _okay("/home/user/config/whatadir/andasubdir"),                # x
                # This failure blocks the two  subdirs above:
                _fail("/home/user/config/whatadir/andasubdir/failed.man"),     #
                _okay("/home/user/config/anotherdir/"),                        #
                _okay("/home/user/config/anotherdir/file"),                    # x
                _okay("/home/user/config/anotherdir/subdir/file"),             # x
                _okay("/home/user/config/anotherdir/subdir/secondsubdirfile"), # x
                # Due to this failure, "anotherdir"cannot be deleted:
                _fail("/home/user/config/anotherdir/file.broken.link"),        #
                _okay("/home/user/config/deletethisdir"),                      # x
                _okay("/home/user/config/deletethisdir/andthisfile"),          # x
                # This affects no top directory
                _fail("/home/user/config/top-level-file-which-fails")]         #

    _expected = [ '/home/user/config/subdir/file',
                  '/home/user/config/subdir/file.link',
                  '/home/user/config/subdir',
                  '/home/user/config/anotherdir/file',
                  '/home/user/config/anotherdir/subdir/file',
                  '/home/user/config/anotherdir/subdir/secondsubdirfile',
                  '/home/user/config/deletethisdir',
                  '/home/user/config/deletethisdir/andthisfile']

    for _entry in _results:
        print(_entry['path'], _entry['success'])
    print()
    _removable = cb._removable(_results)
    assert _removable == list(map(Path, _expected))


class TestRMFileAndBacklink:

    bundled_file: Path
    backlink: Path

    @pytest.fixture
    def setup(self, empty_dir, test_text_file):
        self.bundled_file = cb._bundle_file(test_text_file, empty_dir)
        self.backlink = cb._suffix(self.bundled_file)
        assert self.bundled_file.exists()
        assert self.backlink.is_symlink()

    def test_delete_files(self, setup):
        cb._rm_file_and_backlink(self.bundled_file)
        assert not self.bundled_file.exists()
        assert not self.backlink.exists()

    def test_no_error_if_file_missing(self, setup):
        self.bundled_file.unlink()
        cb._rm_file_and_backlink(self.bundled_file)
        assert not self.backlink.exists()

    def test_no_error_if_backlink_missing(self, setup):
        self.backlink.unlink()
        cb._rm_file_and_backlink(self.bundled_file)
        assert not self.bundled_file.exists()


# -----------------------------------------------------------
# Test CMDs:

class TestCMDAdd:

    cmd_bundle_dir: str | None
    bundled_file: Path
    file: Path

    @pytest.fixture
    def setup(self, test_text_file, empty_repo, req_bundledir_strings):
        _dir = _add_if_not_none(empty_repo, req_bundledir_strings)
        _bundled_file = _dir / test_text_file.name
        self.bundled_file = _bundled_file
        self.cmd_bundle_dir = req_bundledir_strings
        self.file = test_text_file

    def test_add(self, setup):
        cb.add(self.file, self.cmd_bundle_dir)
        assert self.bundled_file.exists()

    def test_add_twice(self, setup):
        cb.add(self.file, self.cmd_bundle_dir)
        assert self.bundled_file.exists()
        with pytest.raises(click.exceptions.Exit):
            cb.add(self.file, self.cmd_bundle_dir)


class TestCMDRestore:

    bundled_file: Path
    bundle_dir: Path
    target_file: Path
    cmd_arg: str

    @pytest.fixture
    def setup(self, test_text_file, empty_repo, req_bundledir_strings):
        """Bundle TEST_TEXT_FILE in REQ_BUNDLEDIR_STRINGS, which could be None."""
        if req_bundledir_strings:
            _cmd_arg = Path(req_bundledir_strings, test_text_file.name)
            _bundle_dir = empty_repo / req_bundledir_strings
        else:
            _cmd_arg = Path(test_text_file.name)
            _bundle_dir = empty_repo
        print(f"_bundle_dir = {_bundle_dir}")
        _bundle_dir.mkdir(parents=True, exist_ok=True)
        self.bundled_file = cb._bundle_file(test_text_file, _bundle_dir)
        self.bundle_dir = _bundle_dir
        self.target_file = test_text_file
        self.cmd_arg = str(_cmd_arg)

    def test_cmd_restore_as_file(self, setup):
        # First overwrite target_file
        cb.restore(self.cmd_arg, False, True, False)
        assert self.target_file.exists()
        assert not self.target_file.is_symlink()
        # Now raise error
        with pytest.raises(click.exceptions.Exit):
            cb.restore(self.cmd_arg, False, False, False)


    def test_cmd_restore_remove(self, setup):
        # Overwrite target and remove bundled file:
        cb.restore(self.cmd_arg, False, True, True)
        assert self.target_file.exists()
        assert not self.target_file.is_symlink()
        assert not self.bundled_file.exists()
        assert not cb._suffix(self.bundled_file).exists()


    def test_cmd_restore_as_link(self, setup):
        # Overwrite
        self.target_file.unlink()
        cb.restore(self.cmd_arg, True, True, False)
        assert self.target_file.exists()
        assert self.target_file.is_symlink()
        assert os.path.samefile(self.target_file, self.bundled_file)
        # Raise error when overwriting
        with pytest.raises(click.exceptions.Exit):
            cb.restore(self.cmd_arg, True, False, False)




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
