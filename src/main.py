"""
The MIT License (MIT)

Copyright (c) <2015> <sarangis>

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

import dis
import sys

from src.vm import BytecodeVM
from src.vmconfig import VMConfig
from src.log import draw_header
from src.debugger import Debugger

def configure_vm():
    config = VMConfig()
    return config

def format_source_lines(source_lines):
    new_source_lines = []
    for line in source_lines:
        line = line.replace("\n", "")
        new_source_lines.append(line)

    return new_source_lines

def display_source(source_lines):
    for i, line in enumerate(source_lines):
        print("%s\t\t%s" % (i+1, line))

def main():
    filename = sys.argv[1]
    fptr = open(filename, "r")
    source = fptr.read()
    fptr.seek(0)
    source_lines = format_source_lines(fptr.readlines())
    fptr.close()

    draw_header("Source")
    display_source(source_lines)
    code = compile(source, filename, "exec")

    vm = BytecodeVM(code, source_lines, filename)

    WITH_DEBUGGER = True

    if not WITH_DEBUGGER:
        draw_header("Disassembly")
        dis.dis(code)
        #  Configure the VM and set the settings based on command line. For now use defaults
        config = configure_vm()
        config.show_disassembly = True
        vm.config = config
        vm.execute()
    else:
        debugger = Debugger(code, source_lines, filename)
        debugger.execute(False)

if __name__ == "__main__":
    main()