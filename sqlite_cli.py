#!/usr/bin/env python
#
# Author: hdjgithub@oblig.at
# Date  : 2015.02
# Description:
#   A commandline interface to sqlite.
#   Uses heavily auto completion in nearly any place.
#
import os
import sqlite3 as DB
import sys
import logging
import re
import readline
import glob

from cmd2 import Cmd


# =============================================================================
# readline config/setup/...
# =============================================================================
# history file setup
histfile = os.path.join(os.path.expanduser("~"), ".sqlite_cli.history")
try:
    readline.read_history_file(histfile)
except IOError:
    pass
import atexit
atexit.register(readline.write_history_file, histfile)

# / should not be a delimiter for path completitions,
# so we set our own delimiters.
readline.set_completer_delims(' \t\n;')
# =============================================================================


# =============================================================================
# System Core Settings = START ================================================
# TODO: There is a len() overhead with this colors of 13 characters,
# TODO: so every print with a fieldlength has to add 13 to get the expected width.
# =============================================================================
NOCOLOR = False
if NOCOLOR:
    def BLACK(text):        return text
    def BLUE(text):         return text
    def BROWN(text):        return text
    def CYAN(text):         return text
    def DARK_GRAY(text):    return text
    def GREEN(text):        return text
    def LIGHT_BLUE(text):   return text
    def LIGHT_CYAN(text):   return text
    def LIGHT_RED(text):    return text
    def LIGHT_GRAY(text):   return text
    def LIGHT_GREEN(text):  return text
    def LIGHT_PURPLE(text): return text
    def PURPLE(text):       return text
    def RED(text):          return text
    def WHITE(text):        return text
    def YELLOW(text):       return text
else:
    def BLACK(text):        return "\033[0;30m%s\033[0;0m" % (text,)
    def BLUE(text):         return "\033[0;34m%s\033[0;0m" % (text,)
    def BROWN(text):        return "\033[0;33m%s\033[0;0m" % (text,)
    def CYAN(text):         return "\033[0;36m%s\033[0;0m" % (text,)
    def DARK_GRAY(text):    return "\033[1;30m%s\033[0;0m" % (text,)
    def GREEN(text):        return "\033[0;32m%s\033[0;0m" % (text,)
    def LIGHT_BLUE(text):   return "\033[1;34m%s\033[0;0m" % (text,)
    def LIGHT_CYAN(text):   return "\033[1;36m%s\033[0;0m" % (text,)
    def LIGHT_RED(text):    return "\033[1;31m%s\033[0;0m" % (text,)
    def LIGHT_GRAY(text):   return "\033[0;37m%s\033[0;0m" % (text,)
    def LIGHT_GREEN(text):  return "\033[1;32m%s\033[0;0m" % (text,)
    def LIGHT_PURPLE(text): return "\033[1;35m%s\033[0;0m" % (text,)
    def PURPLE(text):       return "\033[0;35m%s\033[0;0m" % (text,)
    def RED(text):          return "\033[0;31m%s\033[0;0m" % (text,)
    def WHITE(text):        return "\033[1;37m%s\033[0;0m" % (text,)
    def YELLOW(text):       return "\033[1;33m%s\033[0;0m" % (text,)

ISOLATION_LEVELS            = (
    'DEFERRED',
    'IMMEDIATE',
    'EXCLUSIVE',
    'Autocommit',
)
LOG_LEVELS                  = {
    'CRITICAL'  : logging.CRITICAL,
    'ERROR'     : logging.ERROR,
    'WARNING'   : logging.WARNING,
    'INFO'      : logging.INFO,
    'DEBUG'     : logging.DEBUG,
    'UNSET'     : 0,
}
# patch python logger to be more colorful -------------------------------------
logging.addLevelName( logging.DEBUG,   "\033[0;34m%-8s\033[0;0m" % logging.getLevelName(logging.DEBUG))
logging.addLevelName( logging.INFO,    "\033[1;33m%-8s\033[0;0m" % logging.getLevelName(logging.INFO))
logging.addLevelName( logging.WARNING, "\033[1;36m%-8s\033[0;0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName( logging.ERROR,   "\033[0;31m%-8s\033[0;0m" % logging.getLevelName(logging.ERROR))
logging.addLevelName( logging.CRITICAL,"\033[0;35m%-8s\033[0;0m" % logging.getLevelName(logging.CRITICAL))
# setup logging ---------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')
log = logging.getLogger('sqlite_cli')
# -----------------------------------------------------------------------------
INTRO_TEXT = GREEN(
    '\n'
    'Welcome to a better(?) SQLite shell.\n\n'
    '   help or ?  : for documentation\n'
    '   py         : Start a python shell.\n'
    '   shell or ! : Run a command in your shell.\n'
    '                like: "!ls -la"\n'
    '\n'
)
# ENUMS - START----------------------------------------------------------------
# --- Outputformat: Output Types
CSV                         = 'CSV'
FILE                        = 'FILE'
LINE                        = 'LINE'
TABLE                       = 'TABLE'
# --- Outputformat: General Tuning Parameter Names
MAX_WIDTH                   = 'MAX_WIDTH'
TRUNCATE_LINE               = 'TRUNCATE_LINE'
# --- Outputformat: CSV Tuning
SEPARATOR                   = 'SEPARATOR'
# --- Outputformat: Table Tuning
COLUMN_WIDTHS         = 'COLUMN_WIDTHS'
COLUMN_IDX            = 'COLUMN_IDX'
COLUMN_MAX_WIDTH      = 'COLUMN_MAX_WIDTH'
COLUMN_MIN_WIDTH      = 'COLUMN_MIN_WIDTH'
# ENUMS - END -----------------------------------------------------------------
# System Core Settings = END ==================================================
# =============================================================================

_max_width = 80
_data  = os.popen('stty -a', 'r').read()
_match = re.search('columns (\d+)', _data)
if _match:
    _max_width = _match.group(1)

FORMATS = {
    TABLE   : { MAX_WIDTH     : _max_width,
                COLUMN_WIDTHS : {},   # {  2: { COLUMN_MAX_WIDTH: 20, COLUMN_MIN_WIDTH: 20, },
                                      #   10: { COLUMN_MAX_WIDTH: 10, TRUNCATE_LINE: True, },
                                      # }
                },
    LINE    : { MAX_WIDTH     : -1,
                TRUNCATE_LINE : True,
                },
    CSV     : { SEPARATOR     : ',',
                },
}

DATABASE_FILENAME_SUFFIXES  = ['db', 'sqlite',]
SQL_GET_TABLE_NAMES         = "SELECT tbl_name as name from sqlite_master where type in ('table', 'view');"
# SQL_KEYWORDS                = (
#     'SELECT', 'FROM', 'UPDATE', 'SET', 'ON', 'ORDER BY', 'LIMIT', 'AS', 'DROP', 'PRAGMA',
#     'JOIN', 'LEFT', 'RIGHT', 'NOT', 'IN',
# )

CONFIG_FILES = [ '/etc/sqlite_cli.cfg',
                 os.path.join(os.path.expanduser('~'), '.sqlite_cli.cfg'),
                 './.sqlite_cli.cfg',
                 './sqlite_cli.cfg',]

# Color Theme Settings = START ================================================
COLUMN_NAME_COLOR   = YELLOW
FRAME_COLOR         = BLUE
DATA_COLOR          = LIGHT_GRAY
HIGHLIGHT           = WHITE
# Color Theme Settings = END ==================================================

class SQLiteCli(Cmd):
    def __init__(self):
        Cmd.__init__(self)
        # FIXME: dont use color on prompt because readline gets confused with this
        # FIXME: and \001 + \002 dont work everywere
        self.prompt             = '==> '
        self.ruler              = DARK_GRAY("=")
        self.doc_header         = RED('Documented commands (type help <topic>):')
        self.undoc_header       = RED('Undocumented commands:')
        self.name               = None
        self.connection         = None
        self.mode               = LINE
        self.isolation_level    = None # autocommit
        self.loglevel           = 'DEBUG'
        self._set_loglevel()

        self.cache_table_names  = []
        self.cache_column_names = {} # { TABLE_NAME: [COLUMN_NAME_0, COLUMN_NAME_1, COLUMN_NAME_N,], }

    # =========================================================================
    def do_load_config(self, filename):
        log.error('load_config is not implemented!')

    @staticmethod
    def help_load_config():
        print
        print HIGHLIGHT("<<< load_config [FILENAME]")
        print "   Load configuration from FILENAME."
        print
        print "   Without FILENAME configfiles will be "
        print "   searched and loaded (adaptive) from:"
        for filename in CONFIG_FILES:
            print "      o) %s" % (filename,)
        print

    @staticmethod
    def complete_load_config(text, line, begidx, endidx):
        text_new    = "%s*" % (line[len('load_config') + 1:].strip(),)
        completions = glob.glob(text_new)
        # print
        # print "text          : ", text
        # print "text_new      : ", text_new
        # print "line          : ", line
        # print "begidx|endidx : %s|%s" % (begidx, endidx,)
        # print "completitions : ", completions
        # print
        return completions

    # =========================================================================
    def do_mode(self, line):
        if line.upper() in FORMATS.keys():
            self.mode = line.upper()
        elif len(line) == 0:
            print "Actual mode is %s." % (HIGHLIGHT(self.mode),)
        else:
            log.error('Mode "%s" is unknown!', line)

    @staticmethod
    def help_mode():
        print
        print HIGHLIGHT(">>> mode [MODE]")
        print "   Set output mode to MODE."
        print "   Use "
        print "      mode <TAB><TAB>"
        print "   to see all available modes."
        print

    def complete_mode(self, text, line, begidx, endidx):
        return self._complete(text, FORMATS.keys())

    # =========================================================================
    @staticmethod
    def do_cfg_table_column(line):
        params = line.split(' ')
        if len(params) == 1:
            print('Configuration for Outputformat %s:' % HIGHLIGHT('TABLE'))
            print('Maximum Table Width: %s' % FORMATS[TABLE].get(MAX_WIDTH, 'unset'))
            available_configs = FORMATS[TABLE].get(COLUMN_WIDTHS, {})

            if len(available_configs) > 0:
                print('Column Configurations:')
                for col_idx, data in available_configs.iteritems():
                    print('\tCol Index: %16s, max_width: %16s, min_width: %16s, truncate line: %s' % (
                             DATA_COLOR(col_idx),
                             DATA_COLOR(data.get(COLUMN_MAX_WIDTH, 'unset')),
                             DATA_COLOR(data.get(COLUMN_MIN_WIDTH, 'unset')),
                             DATA_COLOR(data.get(TRUNCATE_LINE, 'unset')),)
                    )
        else:
            if FORMATS[TABLE].get(COLUMN_WIDTHS, None) is None:
                FORMATS[TABLE][COLUMN_WIDTHS] = {}

            if params[0].upper() == 'DEL':
                if len(params) >= 2:
                    col_idx = FORMATS[TABLE][COLUMN_WIDTHS][params[1]]
                    del(FORMATS[TABLE][COLUMN_WIDTHS][col_idx])
            else:
                if params[0] not in FORMATS[TABLE][COLUMN_WIDTHS]:
                    FORMATS[TABLE][COLUMN_WIDTHS][params[0]] = {}

                if len(params) >= 2:
                    if params[1].isdigit():
                        FORMATS[TABLE][COLUMN_WIDTHS][params[0]][COLUMN_MAX_WIDTH] = int(params[1])
                    else:
                        log.error('Parameter for COLUMN_MAX_WIDTH is not numeric!')

                if len(params) >= 3:
                    if params[2].isdigit():
                        FORMATS[TABLE][COLUMN_WIDTHS][params[0]][COLUMN_MIN_WIDTH] = int(params[2])
                    else:
                        log.error('Parameter for COLUMN_MIN_WIDTH is not numeric!')

                if len(params) >= 4:
                    value = params[3].upper()
                    if value in ('TRUE', 'YES',):
                        FORMATS[TABLE][COLUMN_WIDTHS][params[0]][TRUNCATE_LINE] = True
                    elif value in ('FALSE', 'NO',):
                        FORMATS[TABLE][COLUMN_WIDTHS][params[0]][TRUNCATE_LINE] = False
                    else:
                        log.error("Value for TRUNCATE_LINE is not one of (TRUE|FALSE|YES|NO)! It's %s.", params[3])

    @staticmethod
    def help_cfg_table_column():
        print
        print HIGHLIGHT(">> %s [COLUMN_INDEX] [MAX_WIDTH] [MIN_WIDTH] [TRUNCATE_LINE]") % (RED("cfg_table_column"),)
        print "   Sets formating parameter for output-mode TABLE for a single column."
        print
        print "   If called without parameters the actual configuration is shown."
        print
        print "   [TRUNCATE_LINE] True/False/Yes/No (case insensitive) "
        print "      if True or Yes the column data will be truncated at MAX_WIDTH."
        print "   All parameters from right to left are optional."
        print

    # =========================================================================
    def do_sys_update_table_names(self, line):
        """ update cache for table names. """
        self._update_cache_table_names()

    def do_show_column_names(self, table_name):
        for name in self.cache_column_names[table_name]:
            print "%s.%s" % (LIGHT_GRAY(table_name), YELLOW(name),)

    # =========================================================================
    def do_loglevel(self, level):
        """ Get/Set loglevel. """
        if len(level) == 0:
            log.info('Actual loglevel is %s', self.loglevel)
        elif level in LOG_LEVELS.keys():
            self.loglevel = level
            self._set_loglevel()
        else:
            log.error('Unknown loglevel "%s"! Known levels are: %s', level, LOG_LEVELS.keys())

    def complete_loglevel(self, text, line, begidx, endidx):
        return self._complete(text, LOG_LEVELS.keys())

    # =========================================================================
    def do_isolation_level(self, level):
        """ Set's or get's the database isolation level."""
        if not self._connected():
            return

        if len(level) == 0:
            level_description = self.isolation_level
            if self.isolation_level is None:
                level_description = 'Autocommit'
            log.info("Actual isolation_level is %s" % (level_description,))
        elif level in ISOLATION_LEVELS:
            if level == 'Autocommit':
                level = None
            self.isolation_level            = level
            self.connection.isolation_level = level
        else:
            log.error('Unknown/handled isolation_level: %s', level)
    @staticmethod
    def help_isolation_level():
        print
        print HIGHLIGHT(">> %s [LEVEL]") % (RED('isolation_level'),)
        print "   Sets the Database isolation level to [LEVEL]."
        print
        print "   Hint:"
        print "      isolation_level <TAB><TAB>"
        print "   to see all available levels."
        print
        print "   Called without parameter the actual isolation level is shown."
        print

    def complete_isolation_level(self, text, line, begidx, endidx):
        return self._complete(text, ISOLATION_LEVELS)

    # =========================================================================
    @staticmethod
    def emptyline():
        return

    # =========================================================================
    def do_use(self, db_name):
        """ Open a sqlite database file. """
        self.name                   = db_name
        self.connection             = DB.connect(db_name, isolation_level=self.isolation_level)
        #self.connection            = DB.connect(db_name, detect_types=DB.PARSE_DECLTYPES|DB.PARSE_COLNAMES)
        self.connection.row_factory = DB.Row
        # .....................................................................
        cur                         = self.connection.cursor()
        cur.execute('SELECT SQLITE_VERSION() as version')
        data = cur.fetchone()
        log.debug("Connected to database '%s'.", db_name)
        log.debug("SQLiteVersion is '%s'.", data['version'])
        log.debug("Updateing table names cache...")
        self._update_cache_table_names()
        log.debug("done.")

    @staticmethod
    def help_use():
        print
        print HIGHLIGHT(">> %s [DATABASE FILE NAME]") % (RED('use'),)
        print "   Opens the given SQLite Database file."
        print
        print "   Hint:"
        print "      use <TAB><TAB>"
        print "   To see a list of potential database files in the actual working directory"
        print "   with a filter of *.db, *.sqlite (Filter is configurable)."
        print

    @staticmethod
    def complete_use(text, line, begidx, endidx):
        text_new    = "%s*" % (text,)
        completions = []
        for fn in glob.glob(text_new):
            if os.path.isfile(fn):
                for ending in DATABASE_FILENAME_SUFFIXES:
                    if fn.endswith(ending):
                        completions.append(fn)
            else:
                completions.append(fn)
        return completions

    # =========================================================================
    def complete_load(self, text, line, begidx, endidx):
        filenames = []
        for entry in os.listdir('./'):
            if os.path.isfile(entry):
                filenames.append(entry)
        return self._complete(text, filenames)

    # =========================================================================
    def do_quit(self, args):
        """ Exit shell. """
        log.info("== Exit shell ==")
        sys.exit(0)

    # =========================================================================
    def do_shell(self, line):
        """ Run a shell command. """
        log.debug("running shell command: %s", line)
        output = os.popen(line).read()
        print output

    # =========================================================================
    def do_EOF(self, line):
        return True

    # =========================================================================
    def do_commit(self, line):
        """ Commit actual transactions. """
        if self.connection is not None:
            self.connection.commit()

    # =========================================================================
    def do_rollback(self, line):
        """Rollback actual transaction. """
        if self.connection is not None:
            self.connection.rollback()

    # =========================================================================
    def default(self, line):
        if not self._connected():
            return

        cur = self.connection.cursor()
        try:
            cur.execute(line)
            log.debug('rowcount after executing "%s" is %s.', line, cur.rowcount)

            data = cur.fetchall()
            log.debug('rowcount after fetchall() "%s" is %s.', line, cur.rowcount)
            log.debug('len(data) is %s.', len(data))

            if len(data) == 0: #cur.rowcount <= 0:
                cur.execute('select changes() as changes;')
                for row in cur:
                    log.info('%s rows changed.', row['changes'])
            else:
                log.debug("Result lines count is %s", (len(data),))
                if len(data) > 0:
                    self._print_data( cur, data )
        except DB.Error, e:
            self.connection.rollback()
            log.error("(default cmdhandler) Command failed! %s", e)

    def completedefault(self, text, line, begidx, endidx):
        #log.debug('completedefault: %s | %s', text, line)
        if len(self.cache_table_names) == 0:
            self._update_cache_table_names()
        word_list = self.cache_table_names
        for table_name in line.split(' '):
            if table_name in self.cache_table_names:
                word_list += [ '%s.%s' % (table_name, col_name,) for col_name in self.cache_column_names[table_name] ]

        #word_list += SQL_KEYWORDS
        return self._complete(text, word_list)

    # =========================================================================
    # Helper Methods and Hook Implementations
    # =========================================================================
    def _print_data(self, cursor, rows):
        if rows is None:
            return

        if self.mode not in FORMATS.keys():
            log.error("Uups, output data format is not implemented.")
            log.error("It's %s.", self.mode)
            log.error("TODO: Implement other output formats!!")
            return

        if self.mode == TABLE:
            self._print_mode_table(cursor, rows)
        elif self.mode == LINE:
            self._print_mode_line(cursor, rows)

    @staticmethod
    def _print_mode_line(cursor, rows):
        column_names = [ cn[0] for cn in cursor.description ]

        width = []
        for cn in column_names:
            width.append( len(cn) )
        name_max = max(width)

        for row in rows:
            for column_name in column_names:
                print "%s: %s" % (COLUMN_NAME_COLOR("{0!s:<{width}}".format(column_name, width=name_max + 1 )),
                                 DATA_COLOR(row[column_name]),)
            print


    def _print_mode_table(self, cursor, rows):
        header_finished = False
        column_names    = [ cn[0] for cn in cursor.description ]
        #
        # Calculate for every column the max length.
        # Example:
        # data:
        #   [
        #       { 'a': 12,  'b': 'something' },
        #       { 'a': 120, 'b': 'more of something' },
        #   ]
        #
        # ---------------------------------------------------------------------
        # column_lengths:
        #   [
        #       { 'a': 2, 'b': 9 },
        #       { 'a': 3, 'b': 17 },
        #   ]
        column_lengths  = []
        for row in rows:
            line_data = {}
            for cn in column_names:
                line_data[cn] = len(str(row[cn]))
            column_lengths.append(line_data)
        # ---------------------------------------------------------------------

        #
        # column_max:
        #   { 'a': 3, 'b': 17 }
        #
        column_max = {}
        for cn in column_names:
            column_max[cn] = max( max( [col[cn] for col in column_lengths] ), len(cn))
        # ---------------------------------------------------------------------

        # Cell formating:
        #   { 'a': "{0!s:>{width}} |", 'b': "{0!s:<{width}} |" }
        # Numbers align right. Strings align left. All others are centered.
        #
        cells = {}
        for cn in column_names:
            if type(rows[0][cn]) in (int, float,):
                cells[cn] = "{0!s:>{width}}"
            elif type(rows[0][cn]) in (str, unicode,):
                cells[cn] = "{0!s:<{width}}"
            else:
                cells[cn] = "{0!s:^{width}}"
        # ---------------------------------------------------------------------
        # refine layout.
        #
        width     = sum([size for size in column_max.values()]) + (2 * len(column_max)) + 1
        # max_width = FORMATS[TABLE][TABLE_MAX_WIDTH]
        # if width > max_width:
        #     diff = width - max_width
        #     width= max_width

        # ---------------------------------------------------------------------
        # print data.
        #
        for row in rows:
            # header
            if not header_finished:
                print FRAME_COLOR("=") * width
                print FRAME_COLOR("|"),
                header_groundline = "+"
                for cn in column_names:
                    print "%s%s" % (COLUMN_NAME_COLOR(cells[cn].format(cn, width=column_max[cn])), FRAME_COLOR("|"),),
                    header_groundline += "%s%s" % ("-" * (column_max[cn] + 1) , "+",)
                print
                print FRAME_COLOR(header_groundline)
                header_finished = True
            # body
            print FRAME_COLOR("|"),
            for cn in column_names:
                print "%s%s" % (DATA_COLOR(cells[cn].format(row[cn], width=column_max[cn])), FRAME_COLOR("|"),),
            print
        print FRAME_COLOR("=") * width

    @staticmethod
    def _complete(text, word_list):
        if not text:
            completions = word_list[:]
        else:
            completions = [ word for word in word_list if word.startswith(text) ]
        return completions

    def _connected(self):
        if self.connection is None:
            log.error("No Database Connection found!")
            log.info("Use 'use FILENAME' to initialise/setup a connection.")
            return False
        return True

    def _update_cache_table_names(self):
        if self.connection is None:
            return
        cursor = self.connection.cursor()
        cursor.execute(SQL_GET_TABLE_NAMES)
        for name in cursor:
            self.cache_table_names.append( name['name'] )
            self._update_cache_column_names(name['name'])

    def _update_cache_column_names(self, table_name):
        if self.connection is None:
            return
        cursor = self.connection.cursor()
        cursor.execute('PRAGMA table_info(%s)' % (table_name,))
        if table_name not in self.cache_column_names:
            self.cache_column_names[table_name] = []
        for table_info_row in cursor:
            self.cache_column_names[table_name].append( table_info_row['name'] )

    def _set_loglevel(self):
        log.setLevel(LOG_LEVELS[self.loglevel])

    def postloop(self):
        print
        log.info("== exit sqlite_cli ==")

if __name__ == '__main__':
    cli = SQLiteCli()
    if len(sys.argv) > 1:
        cmd_string = ' '.join(sys.argv[1:])
        cmd_queue  = cmd_string.split(';')
        for cmd in cmd_queue:
            if len(cmd) == 0:
                continue
            cli.onecmd(cmd)
    else:
        cli.intro = INTRO_TEXT
        cli.cmdloop()

