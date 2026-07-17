"""pcurate.

Usage:
  pcurate PACKAGE_NAME [-u | -s [-t TAG] [-d DESCRIPTION]]
  pcurate ( -c | -r | -m ) [-n | -f] [-v]
  pcurate ( -h | --help | --version)

Options:
  -u --unset              Unset package curated status
  -s --set                Set package curated status
  -t tag --tag tag        Set package tag
  -d desc --desc desc     Set package description
  -c --curated            Display all curated packages
  -r --regular            Display packages not curated
  -m --missing            Display missing curated packages
  -n --native             Limit display to native packages
  -f --foreign            Limit display to foreign packages
  -v --verbose            Display additional info (csv)
  -h --help               Display help
  --version               Display pcurate version

"""

__version__ = '0.1.6'

# standard lib import
import os
import re
import sqlite3
import subprocess

# third party import
from docopt import docopt


class Package:
    """A class to store and retrieve info for Arch Linux software packages.

    Attributes
    ----------
    name : str
        the name of the software package
    curated : int
        value of 1 marks package as a keeper (default 0)
    tag : str
        optional curated package tag (default None)
    description : str
        optional curated package desc (if None will use stock desc)
    native: int
        value of 1 marks package as native (default 0)
    """

    def __init__(self, name, curated=0, tag=None, description=None,
                 native=0) -> None:
        """Init package object representing Arch Linux software package.

        Parameters
        ----------
        name : str
            the name of the software package
        curated : int
            value of 1 marks package as a keeper (default 0)
        tag : str
            optional for curated package categorization (default None)
        description : str
            optional curated package desc (if None will use stock desc)
        native : int
            value of 1 marks package as native (default 0)
        """
        self.name = name
        self.curated = curated
        self.tag = tag
        self.description = description
        self.native = native

    def add(self, db) -> None:
        """Take db connect obj, adds a package and its attributes to db."""
        db.execute("""INSERT OR IGNORE INTO packages VALUES (:name, :curated,
                   :tag, :description, :native)""", {
                   'name': self.name, 'curated': self.curated, 'tag': self.tag,
                   'description': self.description, 'native': self.native})

    def modify(self, db) -> None:
        """Take db connect obj, modifies attributes of a package in db."""
        db.execute("""UPDATE packages SET curated = ifnull(:curated,curated),
                   tag = ifnull(:tag,tag), description = ifnull(:description,
                   description), native = ifnull(:native,native) WHERE name
                   = :name""", {
                   'name': self.name, 'curated': self.curated, 'tag': self.tag,
                   'description': self.description, 'native': self.native})

    def display(self, db) -> str:
        """Take db connect obj, displays attribs stored for package in db."""
        o = db.query('Select * FROM packages WHERE name = :name',
                     {'name': self.name})
        try:
            name, curated, tag, description, native = o[0]
            curated = ',curated,' if curated == 1 else ',regular,'
            native = ',native' if native == 1 else ',foreign'
            print(name + curated + tag + "," + description + native)
            return o
        except IndexError:
            print("package not excplicitly installed (" + self.name + ")")
            return 'no_match'


class Database:
    """A class to handle a sqlite db of Arch linux software package info.

    Attributes
    ----------
    conn
        database connection object
    cursor
        database cursor object
    """

    def __init__(self, db_path) -> None:
        """Take str path to db and initialize it, create it if not exist."""
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS packages (name text
                            PRIMARY KEY,curated integer,tag text,description
                            text,native integer)""")
        # if db is new assign current db version
        current_db_version = 1
        user_ver = int(self.query('PRAGMA user_version')[0][0])
        user_ver = current_db_version if user_ver == 0 else user_ver
        self.cursor.execute("PRAGMA user_version = {v:d}".format(v=user_ver))
        # migration for alpha db
        if len(self.query("PRAGMA table_info('packages')")) == 4:
            self.cursor.execute("""ALTER TABLE packages ADD COLUMN native
                                integer""")

    def __enter__(self) -> 'Database':
        """Bind db instance to context manager."""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        """Call when context mgr leaves context, args are for exceptions."""
        self.close()

    def close(self, commit=True) -> None:
        """Take bool to toggle change commit (default True), and closes db."""
        if commit:
            self.conn.commit()
        self.conn.close()

    def execute(self, sql, params=None) -> None:
        """Take sql str w optional named placeholders."""
        self.cursor.execute(sql, params or ())

    def query(self, sql, params=None) -> list:
        """Take sql str w optional named placeholders and returns rows."""
        self.cursor.execute(sql, params or ())
        return self.cursor.fetchall()

    def repopulate(self) -> None:
        """Rebuild entries for regular pkg and update all pkg native status."""
        self.cursor.execute('DELETE FROM packages WHERE curated = 0')
        pkglist = subprocess.check_output(['pacman', '-Qei'])
        pkglist = pkglist.decode('utf-8')
        nativelist = subprocess.getstatusoutput('pacman -Qqen')
        for line in pkglist.split('\n'):
            if re.search('^Name', line):
                _, name = line.split(': ', 1)
                native = 0
                for record in nativelist[1].split('\n'):
                    native = native + 1 if record == name else native
            elif re.search('^Description', line):
                _, description = line.split(': ', 1)
                # rebuild entries for regular packages that are still installed
                pkg = Package(name, 0, '', description, int(native))
                pkg.add(self.cursor)
                # refresh entries for curated pkg to set their native status
                o = self.query("""Select * FROM packages WHERE curated = 1 and
                               name = :name""", {'name': name})
                for i in range(len(o)):
                    tag = o[i][2]
                    description = o[i][3]
                    pkg = Package(name, 1, tag, description, int(native))
                    pkg.modify(self.cursor)

    def filter(self, filter_file) -> None:
        """Take filter file obj, filter pkg or pkg group members from db."""
        filters = []
        for line in filter_file:
            line = line.split('#')[0].strip()
            if line:
                filters.append(line)
        if not filters:
            return
        
        # apply specified package and package group filters securely
        res = subprocess.run(['pacman', '-Sgq'] + filters, capture_output=True, text=True)
        expanded = res.stdout.splitlines() if res.returncode == 0 else []
        for name in expanded + filters:
            if name:
                self.execute("""DELETE FROM packages WHERE name = :name
                             and curated = 0""", {'name': name})

    def output(self, args) -> list:
        """Take dict of parsed CLI args, sends formatted db info to stdout."""
        if args['--verbose']:
            print("name, status, tag, description, native")
        native = 1 if args['--native'] else None
        native = 0 if args['--foreign'] else native
        if native is not None:
            o = self.query("""SELECT * FROM packages WHERE curated = :curated
                           AND native = :native ORDER BY name""", {
                           'curated': args['--curated'], 'native': native})
        else:
            o = self.query("""SELECT * FROM packages WHERE curated = :curated
                           ORDER BY name""", {'curated': args['--curated']})
        status = ',curated,' if args['--curated'] else ',regular,'
        for i in range(len(o)):
            if not args['--verbose']:
                print(o[i][0])
            else:
                native = ",native" if o[i][4] == 1 else ",foreign"
                print(o[i][0] + status + o[i][2] + ',"' + o[i][3] + '"'
                      + native)
        return o

    def missing(self, args) -> list:
        """Take dict of parsed CLI args, output list of missing curated."""
        if args['--verbose']:
            print("name, status, tag, description, native")
        o = self.query("""SELECT * FROM packages WHERE curated = 1
                       ORDER BY name""")
        pkglist = subprocess.check_output(['pacman', '-Qqe'])
        pkglist = pkglist.decode('utf-8')
        result = ''
        for i in range(len(o)):
            if o[i][0] not in pkglist.split('\n'):
                if not args['--verbose']:
                    print(o[i][0])
                else:
                    print(o[i][0] + ',curated,' + o[i][2]
                          + ',"' + o[i][3] + '"')
                result += o[i][0] + '\n'
        return result


class __Control:
    """A class to set up config and provide a simple control interface.

    Attributes
    ----------
    config_path
        path to configuration directory
    db_path
        path to sqlite database file
    filter_path
        path to optional filter file
    """

    def __init__(self) -> None:
        """Set up file paths; respect XDG_CONFIG_HOME if it exists."""
        xdg = os.environ.get('XDG_CONFIG_HOME')
        if not xdg:
            xdg = os.path.expandvars('$HOME') + '/.config'
        self.config_path = xdg + '/pcurate'
        os.makedirs(self.config_path, exist_ok=True)
        self.db_path = self.config_path + '/pcurate.db'
        self.filter_path = self.config_path + '/filter.txt'

    def output(self, args) -> None:
        """Take args, use to control package list output."""
        with Database(self.db_path) as db:
            self.filter(db)
            db.output(args)

    def missing(self, args) -> None:
        """Take args, use to control display of missing curated pkgs."""
        with Database(self.db_path) as db:
            db.missing(args)

    def display(self, args) -> None:
        """Take args, use to control pkg changes/display."""
        pkg = Package(args['PACKAGE_NAME'], args['--set'],
                      args['--tag'], args['--desc'])
        with Database(self.db_path) as db:
            db.repopulate()
            if args['--set'] or args['--unset']:
                pkg.modify(db)
                db.conn.commit()
            else:
                pkg.display(db)

    def filter(self, db) -> None:
        """Take db reference, use to control repopulate and filter of db."""
        db.repopulate()
        if os.path.isfile(self.filter_path):
            with open(self.filter_path, 'r') as filter_file:
                db.filter(filter_file)


def main() -> None:
    """Dispatch commands based on CLI args parsed by docopt."""
    c = __Control()
    args = docopt(__doc__)
    if args['--curated'] or args['--regular']:
        c.output(args)
    elif args['--missing']:
        c.missing(args)
    elif args['PACKAGE_NAME']:
        c.display(args)
    elif args['--version']:
        print("pcurate version " + __version__)


if __name__ == '__main__':
    main()
