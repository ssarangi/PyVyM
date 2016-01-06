"""
The MIT License (MIT)

Copyright (c) 2015 <Satyajit Sarangi>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

class LineNo:
    """
    Described in http://svn.python.org/projects/python/trunk/Objects/lnotab_notes.txt
    """
    def __init__(self, start_lineno, co_lnotab, source, filename):
        self.__start_lineno = start_lineno
        self.__byte_increments = list(co_lnotab[0::2])
        self.__line_increments = list(co_lnotab[1::2])
        self.__source = source
        self.__filename = filename
        self.__currently_executed_line = None

    @property
    def currently_executing_line(self):
        return self.__currently_executed_line

    @currently_executing_line.setter
    def currently_executing_line(self, lineno):
        self.__currently_executed_line = lineno

    def line_number(self, ip):
        lineno = addr = 0

        for addr_incr, line_incr in zip(self.__byte_increments, self.__line_increments):
            addr += addr_incr
            if addr > ip:
                return lineno + self.__start_lineno

            lineno += line_incr

        return lineno + self.__start_lineno

    def get_source_line(self, lineno):
        if lineno - 1 > len(self.__source):
            raise Exception("Invalid line no calculated")

        return self.__source[lineno - 1]

    def get_all_source_lines(self):
        all_source = ""
        for lineno, line in enumerate(self.__source):
            all_source += "%s\t%s" % (lineno, line) + "\n"

        return all_source

    def get_source_sorrounding_line(self, lineno, max_lines_sorrounding=5):
        lineno = lineno - 1
        start = max(0, lineno - 2)

        # figure out how many lines to add
        num_lines_needed = max_lines_sorrounding - (lineno - start)
        end = min(len(self.__source), lineno + num_lines_needed)

        source_lines = ""
        for i in range(start, end + 1):
            if i == lineno:
                source_lines += " ---> "
            else:
                source_lines += "      "

            source_lines += "%s\t%s" % (i+1, self.__source[i]) + "\n"

        return source_lines