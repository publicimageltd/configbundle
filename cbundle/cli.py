#!/usr/bin/python
from pathlib import Path
from typing import Callable, Optional, Any
from typing_extensions import Annotated
# Hack to disable rich output
import sys
sys.modules['rich'] = None  # type: ignore
import typer  # noqa: E402


APP_NAME = 'configbundle'
cli = typer.Typer(no_args_is_help=True)


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

def get_link_dir(bundle: str, link_type: str) -> Path:
    """Get directory for bundled links of type LINKE_TYPE."""
    bundle_path = get_bundle(bundle)
    if link_type not in ['bin', 'data', 'config']:
        print(f"Unsupported link type {link_type}")
        raise typer.Exit(1)
    if link_type == 'config':
        return bundle_path
    else:
        return bundle_path / link_type


def linked_files(path: Path, subdir: Path = Path('')) -> list[Path]:
    """Return all linked files in PATH."""
    return [f for f in (Path(path) / subdir).glob('*') if f.is_symlink()]


def get_bundles() -> list[str]:
    """Return a list of all bundles (no paths)."""
    repo_dir = get_repo()
    return [f"{file.name}" for file in repo_dir.glob('*') if file.is_dir()]


def get_bundle_files(bundle: str) -> list[Path]:
    """Return a sorted list of all files bundled in PATH."""
    path = get_bundle(bundle)
    res = []
    res.extend(sorted(linked_files(path)))
    res.extend(sorted(linked_files(path, Path("bin"))))
    res.extend(sorted(linked_files(path, Path("data"))))
    return res


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


@cli.command("add")
@cli.command()
def ln(bundle: str,
       target: Path,
       link_type: Annotated[str, typer.Argument()] = 'config') -> None:
    """Create a link to TARGET in BUNDLE."""
    assert_path(target, msg="Target {p} does not exist")
    link_dir = get_link_dir(bundle, link_type)
    if link_type != 'config':
        link_dir.mkdir(parents=True, exist_ok=True)
    link = link_dir / target.name
    if link.exists():
        print(f"Link {link} already exists")
        raise typer.Exit(1)
    # print(f"Creating file {link} pointing to {target.resolve()}")
    link.symlink_to(target.resolve())


@cli.command()
def rm(bundle: str,
       file: Path,
       link_type: Annotated[str, typer.Argument()] = 'config') -> None:
    """Remove (unlink) FILE in BUNDLE."""
    link_dir = get_link_dir(bundle, link_type)
    target: Path = link_dir / file
    if not target.exists():
        print(f"File {target} does not exist")
        raise typer.Exit(1)
    if target.is_dir():
        # TODO Test fails, solve this!
        # USE os.unlink() for both cases
        print(f"TEST Trying to remove {target}, but it is a directory")
    else:
        target.unlink()


@cli.command()
def check(bundle: str) -> None:
    """Check if all links in BUNDLE point to existing files."""
    bundled = get_bundle_files(bundle)
    for file in bundled:
        path = file.resolve()
        if not path.exists():
            print(f"File {file} links to non-existing file {path}")


@cli.command()
def cleanup(bundle: str) -> None:
    """Remove invalid links."""
    bundled = get_bundle_files(bundle)
    for file in bundled:
        path = file.resolve()
        if not path.exists():
            print(f"Removing link to non-existing file {path}")
            file.unlink()


@cli.command()
def ls(bundle: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Display the contents of BUNDLE. If no bundle is given, list all bundles in the repository."""
    list_this: list[Any]
    if bundle is None:
        list_this = get_bundles()
    else:
        list_this = get_bundle_files(bundle)
    for item in list_this:
        print(item)


if __name__ == '__main__':
    cli()
