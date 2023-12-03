#!/usr/bin/python
from pathlib import Path
from typing import Callable, Optional
from typing_extensions import Annotated
# Hack to disable rich output
import sys
import shutil
import subprocess
sys.modules['rich'] = None  # type: ignore
import typer  # noqa: E402

# -----------------------------------------------------------
# Ideas:
#
# - TODO  We associate the bundled file with its target
# - For this, we either use a second file with informations (say,
#   ".dot_xy")
#    - Can this be a link to the target? Will there be a circular
#      reference? No, it works fine, since the names are not
#      identical.
#      TODO Maybe use instead: original filename -
#     and "original filename.link"
#
# - TODO "Add" register links to the target file.




# -----------------------------------------------------------
# Global Variables

APP_NAME = 'configbundle'
cli = typer.Typer(no_args_is_help=True)
LINK_SUFFIX = '.link'

# -----------------------------------------------------------
# Utilities

def assert_path(p: Path, assertion: Callable[[Path], bool] = Path.exists,
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


def _ignore(file: Path) -> bool:
    """Return False when file is a bundle file."""
    res = False
    res = file.match(".gitignore")
    res = file.match(".git")
    return res


def get_repo() -> Path:
    """Return the path to the bundle repository."""
    repo_path = Path(typer.get_app_dir(APP_NAME))
    assert_path(repo_path, msg="There is no repository directory at {p}")
    assert_path(repo_path, Path.is_dir, msg="{p} is not a directory")
    return repo_path


def get_bundle(bundle: str) -> Path:
    """Find and assert the path to BUNDLE."""
    repo_path = get_repo()
    bundle_path = repo_path / bundle
    assert_path(bundle_path)
    assert_path(bundle_path, Path.is_dir, msg="{p} is not a directory")
    return bundle_path


def get_bundles() -> list[str]:
    """Return a list of all bundles (no paths)."""
    repo_dir = get_repo()
    return [f"{file.name}" for file in repo_dir.glob('*') if file.is_dir()]


def _move(file: Path, target_path: Path) -> Path:
    """Move FILE, returning the new file as Path."""
    target_path = target_path.absolute()
    if target_path.is_dir():
        target_file = target_path / file.name
    else:
        target_file = target_path
    return file.rename(target_file)


def _copy(file: Path, target_path: Path) -> Path:
    """Copy FILE, returning the destination as Path.
    If FILE is a symlink, create a copy of the file FILE
    is referring to."""
    target_path = target_path.absolute()
    if target_path.is_dir():
        target_file = target_path / file.name
    else:
        target_file = target_path
    return shutil.copy2(f"{file}", f"{target_file}")


# TODO Write test
def _link_back(link_file: Path, target_file: Path) -> None:
    """Create a symlink pointing to TARGET_FILE with LINK_SUFFIX added."""
    link_file.with_suffix(LINK_SUFFIX).symlink_to(target_file.absolute())

# TODO Write test
def _bundle_file(file: Path, bundle_dir: Path) -> None:
    """Move FILE into BUNDLE_DIR and replace FILE with a link pointing to the bundled file.
       Additionally create a backlink in the bundle dir."""
    bundled_file = _move(file, bundle_dir)
    _link_back(bundled_file, file)
    # TODO Check relative or absolute links, what do we need?
    file.symlink_to(bundled_file)


# -----------------------------------------------------------
@cli.command()
def init(bundle: str) -> None:
    """Initialize bundle."""
    repo_path = get_repo()
    bundle_path = repo_path / bundle
    assert_path(bundle_path, assertion=lambda p: not Path.exists(p),
                msg="Bundle {p} already exists")
    bundle_path.mkdir(parents=True, exist_ok=True)
    print(f"Created bundle {bundle}")


@cli.command()
def add(bundle: str, file: Path) -> None:
    "Add FILE to BUNDLE, replacing it with a link to the bundled file."
    assert_path(file)
    bundle_dir = get_bundle(bundle)
    _bundle_file(file, bundle_dir)


@cli.command()
def copy(bundle: str, file: Path, target_file: Path) -> None:
    """Copy FILE in BUNDLE to TARGET_FILE.
    FILE's path is relative to the bundle root directory."""
    bundle_file = get_bundle(bundle) / file
    assert_path(bundle_file)
    _move(bundle_file, target_file)


@cli.command()
def restore(bundle: str, file: Path) -> None:
    """Copy FILE to the location defined by its associated .link file."""
    bundle_file = get_bundle(bundle) / file
    link_file = bundle_file.with_suffix(LINK_SUFFIX)
    assert_path(bundle_file)
    assert_path(link_file)
    _copy(bundle_file, link_file.resolve())


@cli.command()
def rm(bundle: str, file: Path) -> None:
    """Remove FILE in the bundle and it associated link."""
    bundle_file = get_bundle(bundle) / file
    assert_path(bundle_file)
    link_file = bundle_file.with_suffix(LINK_SUFFIX)
    if link_file.exists():
        link_file.unlink()
    bundle_file.unlink()


@cli.command()
def rmdir(bundle: str) -> None:
    """Remove BUNDLE and its contents."""
    bundle_dir = get_bundle(bundle)
    assert_path(bundle_dir)
    shutil.rmtree(str(bundle_dir))


@cli.command()
def ls(bundle: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Display the contents of BUNDLE, not descendin in directories.
    If no bundle is given, list all bundles in the repository."""
    if bundle is None:
        for item in get_bundles():
            print(item)
    else:
        bundle_dir = get_bundle(bundle)
        # TODO check if tree is installed
        # TODO Process return value
        subprocess.call(["tree", str(bundle_dir.relative_to(Path.cwd()))])


if __name__ == '__main__':
    cli()
