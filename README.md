## pcurate

Pcurate is a universal command-line utility with the purpose of 'curating' or carefully arranging lists of explicitly installed software packages across different operating systems.

It was originally built for Arch Linux, but has been modernized to support **macOS (Homebrew)** and **Debian/Ubuntu (APT)**, acting as a single, unified tool to track your curated software stack across an entire fleet of machines.

This utility provides a convenient way to organize software stacks into package lists which can either be fed back to the package manager for automatic installation, or simply used for reference and planning.

### Features include

 - **Universal Support**: Works seamlessly with `pacman` (Arch), `brew` (macOS), and `apt`/`dpkg` (Debian).
 - **Git-Friendly Storage**: Uses a lightweight JSON flat-file (`~/.config/pcurate/curated.json`) to store package metadata instead of a binary database, making it 100% version-controllable.
 - **Zero Dependencies**: Built entirely with the Python standard library.
 - Tagging/categorization of curated packages for easier filtering and sorting.
 - Alternate package descriptions can be set, such as the reason for installation.
 - Data is exportable to a simple package list or comma delimited (CSV) format.
 - Optional `filter.txt` file for specifying packages or package groups to be excluded.
 - Option to limit display output to only include either native or foreign packages.

Note: Package version information is intentionally untracked to support rolling release distributions or rapidly updating systems. If needed, notes on versioning can be stored in a package tag or description attribute.

### Installation

Install using `uv` (recommended) or `pip`:

```bash
uv tool install pcurate
# OR
pip install pcurate --user --upgrade
```

### Usage

```bash
$ pcurate -h
pcurate: A tool to organize and curate package lists.

usage: pcurate [-h] [--version] [-u] [-s] [-t TAG] [-d DESC] [-c | -r | -m]
               [-n | -f] [-v]
               [PACKAGE_NAME]

positional arguments:
  PACKAGE_NAME          Package name to query or set/unset curated status

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -u, --unset           Unset package curated status
  -s, --set             Set package curated status
  -t TAG, --tag TAG     Set package tag
  -d DESC, --desc DESC  Set package description
  -c, --curated         Display all curated packages
  -r, --regular         Display packages not curated
  -m, --missing         Display missing curated packages
  -n, --native          Limit display to native packages
  -f, --foreign         Limit display to foreign packages
  -v, --verbose         Display additional info in CSV format
```

### Examples

Display information for a package:

```bash
$ pcurate firefox
```

Set a package as curated status (a keeper):

```bash
$ pcurate -s vim
```

Unset a package to revoke its curated status (and remove any tag or custom description):

```bash
$ pcurate -u emacs
```

Set a package with an optional tag and custom description:

```bash
$ pcurate -s mousepad -t editors -d "my cat installed this"
```

#### Package List Examples

Display a list of regular packages (those which are installed but not yet curated):

```bash
$ pcurate -r
```

Display a list of curated packages that are missing (either no longer installed or their install reason has been changed to dependency):

```bash
$ pcurate -m
```

Set curated status for all packages listed in an existing `pkglist.txt` file (a simple text file containing a newline-separated list of package names):

```bash
$ cat pkglist.txt | xargs -I % pcurate -s %
```

Export all curated native packages to a new `pkglist.txt` file:

```bash
$ pcurate -cn > pkglist.txt
```

Send the resulting `pkglist.txt` to your package manager for automatic installation (example for pacman):

```bash
$ pacman -S --needed - < pkglist.txt
```

Write a detailed list of curated packages to CSV format so you can view it as a spreadsheet:

```bash
$ pcurate -cv > pkglist.csv
```

#### Configuration

**`~/.config/pcurate`** (or `$XDG_CONFIG_HOME/pcurate`) is the default location for the package configuration.

- **`curated.json`**: Contains the explicitly curated packages and their tags/descriptions.
- **`filter.txt`** (Optional): A simple newline-separated list of packages or package groups. Single line comments (`#`) can be added. Any packages or members of package groups listed in `filter.txt` will be excluded from command output. Filter rules are only applied against regular packages.

### License
The MIT License (MIT)

Copyright © 2021 Scott Reed