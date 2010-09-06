"""
Module with command-line tool commands that interact with the dashboard
server. All commands listed here should have counterparts in
the ..xml_rpc.commands package.
"""

import errno
import os
import socket
import urlparse
import xmlrpclib

from launch_control.commands.interface import Command


class DataSetRenderer(object):
    """
    Support class for rendering a table out of list of dictionaries.

    It supports several features that make printing tabular data easier.
    * Automatic layout
    * Custom column headers
    * Custom cell formatting
    * Custom table captions
    * Custom column ordering
    * Custom Column separators
    * Custom dataset notification

    The primary method is render() which does all of the above. You
    need to pass a dataset argument which is a list of dictionaries.
    Each dictionary must have the same keys. In particular the first row
    is used to determine columns.
    """
    def __init__(self, column_map=None, row_formatter={}, empty=None,
            order=None, caption=None, separator = " "):
        if column_map is None:
            column_map = {}
        if row_formatter is None:
            row_formatter = {}
        if empty is None:
            empty = "There is no data to display"
        self.column_map = column_map
        self.row_formatter = row_formatter
        self.empty = empty
        self.order = order
        self.separator = separator
        self.caption = caption

    def _analyze_dataset(self, dataset):
        """
        Determine the columns that will be displayed and the maximum
        length of each of those columns.

        Returns a tuple (dataset, columms, maxlen) where columns is a
        list of column names and maxlen is a dictionary mapping from
        column name to maximum length of any value in the row or the
        column header and the dataset is a copy of the dataset altered
        as necessary.

        Some examples:

        First the dataset, an array of dictionaries
        >>> dataset = [
        ...     {'a': 'shorter', 'bee': ''},
        ...     {'a': 'little longer', 'bee': 'b'}]

        Note that column 'bee' is actually three characters long as the
        column name made it wider.
        >>> dataset_out, columns, maxlen = DataSetRenderer(
        ...     )._analyze_dataset(dataset)

        Unless you format rows with a custom function the data is not altered.
        >>> dataset_out is dataset
        True

        Columns come out in sorted alphabetic order
        >>> columns
        ['a', 'bee']

        Maximum length determines the width of each column. Note that
        the header affects the column width.
        >>> maxlen
        {'a': 13, 'bee': 3}

        You can constrain or reorder columns. In that case columns you
        decided to ignore are simply left out of the output.
        >>> dataset_out, columns, maxlen = DataSetRenderer(
        ...     order=['bee'])._analyze_dataset(dataset)
        >>> columns
        ['bee']
        >>> maxlen
        {'bee': 3}

        You can format values anyway you like:
        >>> dataset_out, columns, maxlen = DataSetRenderer(row_formatter={
        ...     'bee': lambda value: "%10s" % value}
        ...     )._analyze_dataset(dataset)

        Dataset is altered to take account of the row formatting
        function. The original dataset argument is copied.
        >>> dataset_out
        [{'a': 'shorter', 'bee': '          '}, {'a': 'little longer', 'bee': '         b'}]
        >>> dataset_out is not dataset
        True

        Columns stay the same though:
        >>> columns
        ['a', 'bee']

        Note how formatting altered the width of the column 'bee'
        >>> maxlen
        {'a': 13, 'bee': 10}

        You can also format columns (with nice aliases).Note how
        column 'bee' maximum width is now dominated by the long column
        name:
        >>> dataset_out, columns, maxlen = DataSetRenderer(column_map={
        ...     'bee': "Column B"})._analyze_dataset(dataset)
        >>> maxlen
        {'a': 13, 'bee': 8}
        """
        if self.order:
            columns = self.order
        else:
            columns = sorted(dataset[0].keys())
        if self.row_formatter:
            dataset_out = [dict(row) for row in dataset]
        else:
            dataset_out = dataset
        for row in dataset_out:
            for column in row:
                if column in self.row_formatter:
                    row[column] = self.row_formatter[column](row[column])
        maxlen = dict(
                [(column, max(
                    len(self.column_map.get(column, column)),
                    max([
                        len(str(row[column])) for row in dataset_out])))
                    for column in columns])
        return dataset_out, columns, maxlen

    def _render_header(self, dataset, columns, maxlen):
        """
        Render a header, possibly with a caption string

        Caption is controlled by the constructor.
        >>> dataset = [
        ...     {'a': 'shorter', 'bee': ''},
        ...     {'a': 'little longer', 'bee': 'b'}]
        >>> columns = ['a', 'bee']
        >>> maxlen = {'a': 13, 'bee': 3}

        By default there is no caption, just column names:
        >>> DataSetRenderer()._render_header(
        ...     dataset, columns, maxlen)
              a       bee

        If you provide a caption it gets rendered as a centered
        underlined text before the data:
        >>> DataSetRenderer(caption="Dataset")._render_header(
        ...     dataset, columns, maxlen)
             Dataset     
        =================
              a       bee

        Observe how the total length of the output horizontal line
        depends on the separator! Also note the columns labels are
        aligned to the center of the column
        >>> DataSetRenderer(caption="Dataset", separator=" | ")._render_header(
        ...     dataset, columns, maxlen)
              Dataset      
        ===================
              a       | bee
        """
        if self.caption:
            total_len = sum(maxlen.itervalues())
            if len(columns):
                total_len += len(self.separator) * (len(columns) - 1)
            print "{0:^{1}}".format(self.caption, total_len)
            print "=" * total_len
        print self.separator.join([
            "{0:^{1}}".format(self.column_map.get(column, column),
                maxlen[column]) for column in columns])

    def _render_rows(self, dataset, columns, maxlen):
        """
        Render rows of the dataset.

        Each row is printed on one line using the maxlen argument to
        determine correct column size. Text is aligned left.

        First the dataset, columns and maxlen as produced by
        _analyze_dataset()
        >>> dataset = [
        ...     {'a': 'shorter', 'bee': ''},
        ...     {'a': 'little longer', 'bee': 'b'}]
        >>> columns = ['a', 'bee']
        >>> maxlen = {'a': 13, 'bee': 3}

        Now a plain table. Note! To really understand this test
        you should check out the length of the strings below. There
        are two more spaces after 'b' in the second row
        >>> DataSetRenderer()._render_rows(dataset, columns, maxlen)
        shorter          
        little longer b  
        """
        for row in dataset:
            print self.separator.join([
                "{0!s:{1}}".format(row[column], maxlen[column])
                for column in columns])

    def _render_dataset(self, dataset):
        """
        Render the header followed by the rows of data.
        """
        dataset, columns, maxlen = self._analyze_dataset(dataset)
        self._render_header(dataset, columns, maxlen)
        self._render_rows(dataset, columns, maxlen)

    def _render_empty_dataset(self):
        """
        Render empty dataset.

        By default it just prints out a fixed sentence:
        >>> DataSetRenderer()._render_empty_dataset()
        There is no data to display

        This can be changed by passing an argument to the constructor
        >>> DataSetRenderer(empty="there is no data")._render_empty_dataset()
        there is no data
        """
        print self.empty

    def render(self, dataset):
        if len(dataset) > 0:
            self._render_dataset(dataset)
        else:
            self._render_empty_dataset()


class XMLRPCCommand(Command):
    """
    Abstract base class for commands that interact with dashboard server
    over XML-RPC.

    The only difference is that you should implement invoke_remote()
    instead of invoke(). The provided implementation catches several
    socket and XML-RPC errors and prints a pretty error message.
    """

    __abstract__ = True

    def __init__(self, parser, args):
        super(XMLRPCCommand, self).__init__(parser, args)
        parts = urlparse.urlsplit(args.dashboard_url)
        if args.username and args.password:
            netloc = "%s:%s@%s" % (
                    args.username, args.password,
                    parts.netloc)
        else:
            netloc = parts.netloc
        urltext = urlparse.urlunsplit((parts.scheme, netloc, "/xml-rpc/",
                "", ""))
        self.server = xmlrpclib.ServerProxy(urltext, use_datetime=True,
                allow_none=True, verbose=args.verbose_xml_rpc)

    @classmethod
    def register_arguments(cls, parser):
        group = parser.add_argument_group("Dashboard Server options")
        group.add_argument('-u', '--username', default=None,
                help="Dashboard user name")
        group.add_argument('-p', '--password', default=None,
                help="Dashboard password")
        group.add_argument("--dashboard-url",
                default = "http://localhost:8000/",
                help="URL of your validation dashboard")
        group.add_argument("--verbose-xml-rpc",
                action="store_true", default=False,
                help="Show XML-RPC data")

    def invoke(self):
        try:
            self.invoke_remote()
        except socket.error as ex:
            print "Unable to connect to server at %s" % (
                    self.args.dashboard_url,)
            # It seems that some errors are reported as -errno
            # while others as +errno.
            if ex.errno < 0:
                ex.errno = -ex.errno
            if ex.errno == errno.ECONNREFUSED:
                print "Connection was refused."
                parts = urlparse.urlsplit(self.args.dashboard_url)
                if parts.netloc == "localhost:8000":
                    print "Perhaps the server is not running?"
            elif ex.errno == errno.ENOENT:
                print "Unable to resolve address"
            else:
                print "Socket %d: %s" % (ex.errno, ex.strerror)
        except xmlrpclib.ProtocolError as ex:
            print "Unable to exchange XML-RPC message with dashboard server"
            print "HTTP error code: %d/%s" % (ex.errcode, ex.errmsg)
        except xmlrpclib.Fault as ex:
            self.handle_xmlrpc_fault(ex.faultCode, ex.faultString)

    def handle_xmlrpc_fault(self, faultCode, faultString):
        if faultCode == 500:
            print "Dashboard server has experienced internal error"
            print faultString
        else:
            print "XML-RPC error %d: %s" % (faultCode, faultString)

    def invoke_remote(self):
        raise NotImplementedError()


class server_version(XMLRPCCommand):
    """
    Display dashboard server version
    """

    __abstract__ = False

    def invoke_remote(self):
        print "Dashboard server version: %s" % (self.server.version(),)
