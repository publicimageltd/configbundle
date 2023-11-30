# Configbundle

Organize configuration files, no matter where they are. Bundle them as
links in a directory to gain uniform access to them.

## Motivation

The central motivation is to provide an easy way to address all those
configuration data spread all across your filesystem in a uniform and
semantically pleasing way. 

Take, for example, your shell setup. If you are on Linux, you will
most probably have some of the following
files on your `/home` partition:  

  - `.bash_completion`
  - `.bash_profile`
  - `.bashrc`
  
 Now imagine you want to backup your shell configuration, or you
 decide to add some feature and thus add yet another file which is,
 say, included during startup (located at `bin/somefile`). In order
 to reproduce this setup, you have to remember all these file names.
 And you will not be able to put these specific files under revision
 control unless you are willing to `git init` your whole home folder.
 So in short, it is a rather cumbersome process to remember, backup
 and track all your different configurations -- for the shell, for
 your security setup, for your mail, or for your favorite editor.
 
 This is where `configbundle` is helping you. By adding a file to a
 configurationn bundle, the script:
  
   - moves the file in a special "bundle" directory and
  - replaces the previous file with a link, pointing to that
     "bundled" file.
	  
 In this setup, the 'bundle' remains the sole "source of truth". It
 can be backed up, put under version control, and treated generally
 as a logical unit -- which it is, after all, since it is just a
 directory. 
  
## Repository Setup

The idea of handling links in this way is heavily inspired by
[Pass](https://www.passwordstore.org/), which is a shell script which
delegates all the bookkeeping logic to the file system. I really liked
that idea and wanted to implement something like this, but not as a
shell script. I chose Python to have an opportunity to learn how to
write a Python script with modern tools, including virtual
environment, testing and all. Part of that is that I want to install
the script as an executable binary, without having to activate the
development `venv` all the time, and to accomplish this goal in an
un-hacky way.

So here's the setup:

 - Develop the script in a `venv` managed by
   [Poetry](https://python-poetry.org/docs/).
 - Use [Pytest](https://python-poetry.org/docs/) for testing.
 - TODO Install the Python script locally as a package
 
