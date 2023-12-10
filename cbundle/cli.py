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
# Global Variables

APP_NAME = 'configbundle'
cli = typer.Typer(no_args_is_help=True)

# -----------------------------------------------------------
# Utilities


def assert_bundle_arg(s: str) -> None:
    """Assert that bundle arg is not pathlike."""
    if re.search("~|/", s):
        print("Argument BUNDLE has to be a simple term (no path)")
        raise typer.Exit(1)


def _suffix(file: Path) -> Path:
    """Return FILE with the suffix .link added."""
    return Path(f"{file}.link")


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
    if not repo_path.exists():
        repo_path.mkdir()
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
    shutil.move(str(file), str(target_file))
    return Path(target_file)


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
def init(bundle: str) -> None:
    """Initialize bundle."""
    repo_path = get_repo()
    assert_bundle_arg(bundle)
    bundle_path = repo_path / bundle
    assert_path(bundle_path, assertion=lambda p: not Path.exists(p),
                msg="Bundle {p} already exists")
    bundle_path.mkdir(parents=True, exist_ok=True)
    print(f"Created bundle {bundle}")


@cli.command()
def add(bundle: str, file: Path) -> None:
    "Add FILE to BUNDLE, replacing it with a link to the bundled file."
    assert_bundle_arg(bundle)
    assert_path(file)
    bundle_dir = get_bundle(bundle)
    _bundle_file(file, bundle_dir)


@cli.command()
def copy(bundle: str, file: Path, target_file: Path) -> None:
    """Copy FILE in BUNDLE to TARGET_FILE.
    FILE's path is relative to the bundle root directory."""
    assert_bundle_arg(bundle)
    bundle_file = get_bundle(bundle) / file
    assert_path(bundle_file)
    _move(bundle_file, target_file)


@cli.command()
def restore(bundle: str, file: Path) -> None:
    """Copy FILE to the location defined by its associated .link file."""
    assert_bundle_arg(bundle)
    bundle_file = get_bundle(bundle) / file
    link_file = _suffix(bundle_file)
    assert_path(bundle_file)
    assert_path(link_file)
    # TODO That does not handle chained links properly
    # A more stable solution would be to iterate over readlink
    # until the bundle target has been reached, and use result n-1
    target_file = link_file.readlink()
    if target_file.exists():
        target_file.unlink()
    print(f"Restoring {target_file} from bundle {bundle}")
    _copy(bundle_file, target_file)


@cli.command()
def rm(bundle: str, file: Path) -> None:
    """Remove FILE in the bundle and it associated link."""
    assert_bundle_arg(bundle)
    bundle_file = get_bundle(bundle) / file
    assert_path(bundle_file)
    link_file = _suffix(bundle_file)
    if link_file.exists():
        link_file.unlink()
    bundle_file.unlink()


@cli.command()
def rmdir(bundle: str) -> None:
    """Remove BUNDLE and its contents."""
    assert_bundle_arg(bundle)
    bundle_dir = get_bundle(bundle)
    shutil.rmtree(str(bundle_dir))


@cli.command()
def ls(bundle: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Display the contents of BUNDLE, not descending into directories.
    If no bundle is given, list all bundles in the repository."""
    if bundle is None:
        for item in get_bundles():
            print(item)
    else:
        assert_bundle_arg(bundle)
        bundle_dir = get_bundle(bundle)
        path = bundle_dir # .relative_to(Path.cwd())
        # TODO Replace external tree with handmade internal f()
        cmd = [str(path)]
        if shutil.which("tree"):
            cmd.insert(0, "tree")
        elif shutil.which("ls"):
            cmd.insert(0, "ls")
            cmd.append("-al")
        else:
            print("Need either ls or tree to list contents")
            raise typer.Exit(1)
        subprocess.call(cmd)


if __name__ == '__main__':
    cli()
