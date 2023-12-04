# Configbundle

**WORK IN PROGRESS**

Organize configuration files in bundles.

CLI tool to bundle configuration files in a directory, replacing the
original files with symlinks. Bundling the file in a separate
directory allows the user to treat configuration files which are
spread all over the file system as one meaningful unit, e.g. by
keeping the bundle under version control or exporting it as an archive
for backup.

## Example

TODO

## Command Overview

`add` : Add FILE to BUNDLE, replacing it with a link to the bundled file.

`copy` : Copy FILE in BUNDLE to TARGET_FILE.

`init` : Initialize bundle.

`ls` : Display the contents of BUNDLE, not descending into directories.

`restore` : Copy FILE to the location defined by its associated .link file.

`rm` : Remove FILE in the bundle and it associated link.

`rmdir`  :Remove BUNDLE and its contents.

## About the repository

The idea of handling links in this way is heavily inspired by
[Pass](https://www.passwordstore.org/), which is a shell script which
delegates all the bookkeeping logic to the file system. I really liked
that idea and wanted to implement something like this, but not as a
shell script. I chose Python to have an opportunity to learn how to
write a Python script with modern tools, including virtual
environment, testing and all. Part of this is to install the script as
an executable binary, without having to activate the development
`venv` all the time.

So here's the setup:

 - Develop the script in a `venv` managed by
   [Poetry](https://python-poetry.org/docs/).
 - Use [Pytest](https://python-poetry.org/docs/) for testing.
 - Install the Python script locally with  [pipx](https://pipx.pypa.io/stable/)
