# Configbundle

## DISCONTINUED

After several changes and revisions, I was close to release a first
"workable" version. And then I discovered
[stow](https://www.gnu.org/software/stow/manual/stow.html), which does
exactly what I envisioned, and has a much better way of 'stowing away'
(bundling) configuration files. They found a way to solve the
conceptual problem of how to track the "bundled" files and their
targets which needs no "backlinks". Instead, they just store the
configuration files in a directory structure which mirrors the target
directory tree. This is really much more robust than my approach and
simply a very, very good idea. In particular, this approach eliminates
all risk of losing data, since all information about the configuration
files (their target location) is hard-coded into the directory
structure of the configuration bundle. This is transparent, solid, and
simply good,

So for the moment being, I call it a day and leave the repository as
it is for now. I did some Python exercises, so that's fine for me, but
don't use this script.

## Project description

Organize configuration files in bundles.

CLI tool to bundle configuration files in a directory, replacing the
original files with symlinks. Bundling the file in a separate
directory allows the user to treat configuration files which are
spread all over the file system as one meaningful unit, e.g. by
keeping the bundle under version control or exporting it as an archive
for backup.

## State of development

See the introductory note above. If one would want to revive the
script, there is currently still a bug in the way the "unbundling"
works (see the comments in the code). Since this bug is caused by my
original approach to store a backlink with every file, this bug is
actually an expression of a bad conceptual approach and actually need
not be.

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
