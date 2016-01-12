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

from enum import Enum

from src.vmconfig import VMConfig
from src.log import draw_header
from src.vm import BytecodeVM

import sys

class DebuggerCmds(Enum):
    VM_NEXT_INST = 0
    VM_STOP_EXEC = 1
    VM_RUN = 2
    VM_SET_BP = 3
    VM_DISABLE_BP = 4
    VM_CLEAR_BP = 5
    VM_CLEAR_ALL_BP = 6
    VM_VIEW_SOURCE = 7
    VM_VIEW_LOCALS = 8
    VM_VIEW_GLOBALS = 9
    VM_VIEW_LOCAL = 10
    VM_VIEW_GLOBAL = 11
    VM_SET_LOCAL = 12
    VM_VIEW_BACKTRACE = 14
    VM_VIEW_BREAKPOINTS = 15
    HELP = 90
    QUIT = 100

class Debugger:
    def __init__(self, code, source, filename):
        self.__breakpoints = {}
        self.__prompt = ">>> "
        self.__debugger_broken = False

        self.__code = code
        self.__source = source
        self.__filename = filename

        self.initialize_vm(code, source, filename)
        draw_header("Initializing Debugger...")

        self.__breakpoint_hit = None
        self.__vm_running = False

    def initialize_vm(self, code, source, filename):
        self.__vm = BytecodeVM(code, source, filename)
        config = VMConfig()
        self.__vm.config = config
        config.show_disassembly = True
        self.__vm.execute = self.execute

    def set_breakpoint(self, line_no):
        self.__breakpoints[line_no] = True

    def disable_breakpoint(self, line_no):
        if line_no not in self.__breakpoints.keys():
            return

        self.__breakpoints[line_no] = False

    def clear_breakpoint(self, line_no):
        if line_no not in self.__breakpoints.keys():
            return

        del self.__breakpoints[line_no]

    def clear_all_breakpoints(self):
        self.__breakpoints = {}

    def view_locals(self, local_var=None):
        draw_header("Locals")
        current_exec_frame = self.__vm.exec_frame

        while current_exec_frame is not None:
            locals = current_exec_frame.locals
            for k, v in locals.items():
                if local_var is None or local_var == k:
                    print("%s: %s" % (k, v))

            current_exec_frame = current_exec_frame.parent_exec_frame

    def view_globals(self, global_var=None):
        globals = self.__vm.exec_frame.globals

        draw_header("Globals")
        for k, v in globals.items():
            if global_var is None or global_var == k:
                print("%s: %s" % (k, v))

    def set_local(self, local_var, val):
        locals = self.__vm.exec_frame.locals

        draw_header("Locals Changed")
        for k, v in locals.items():
            if k == local_var:
                t = type(v)
                try:
                    new_val = t(val)
                    self.__vm.exec_frame.locals[k] = new_val
                except:
                    self.__vm.exec_frame.locals[k] = val
                print("%s: %s" % (k, self.__vm.exec_frame.locals[k]))

    def view_backtrace(self):
        stack_trace = [frame for frame in self.__vm.exec_frame_stack]
        stack_trace.append(self.__vm.exec_frame)

        stack_trace.reverse()

        draw_header("Stacktrace")
        backtrace = ""
        for i, frame in enumerate(stack_trace):
            backtrace += "\t<Frame %s - %s>" % (i, frame) + "\n"

        print(backtrace)

    def view_breakpoints(self):
        draw_header("Breakpoints Set")
        for bp, status in self.__breakpoints.items():
            breakpoint_hit = self.__vm.exec_frame.line_no_obj.get_source_line(bp)
            breakpoint_hit = breakpoint_hit.strip()
            if status == True:
                status = "Enabled"
            else:
                status = "Disabled"
            print("Breakpoint Line %s: %s ---> %s" % (bp, status, breakpoint_hit))

    def view_source(self, lineno):
        if lineno > 0:
            lines = self.__vm.exec_frame.line_no_obj.get_source_sorrounding_line(lineno)
        else:
            lines = self.__vm.exec_frame.line_no_obj.get_all_source_lines()

        print(lines)

    def display_help(self):
        print("\tnext - Execute Next Instruction")
        print("\trun - Run VM")
        print("\tset bp <loc> - Set Breakpoint at loc")
        print("\tdisable bp <loc> - Disable Breakpoint at loc")
        print("\tclear bp <loc> - Disable Breakpoint at loc")
        print("\tclear all bps - Clear all Breakpoints")
        print("\tview source <loc> - View Source. If no loc is specified entire source is shown")
        print("\tview locals - View the Local variables")
        print("\tview globals - View the Global variables")
        print("\tview local <var> - View local var")
        print("\tview global <var> - View global var")
        print("\tview backtrace - View the BackTrace")
        print("\tview bp - View Breakpoints")
        print("\thelp - Display this help")
        print("\tquit - Quit")

    def parse_command(self, cmd):
        if cmd == "next":
            return DebuggerCmds.VM_NEXT_INST
        elif cmd == "run":
            return DebuggerCmds.VM_RUN
        elif "set bp" in cmd:
            parts = cmd.split(" ")
            bp_location = int(parts[2])
            cmd = DebuggerCmds.VM_SET_BP
            return (cmd, bp_location)
        elif "disable bp" in cmd:
            parts = cmd.split(" ")
            bp_location = int(parts[2])
            cmd = DebuggerCmds.VM_DISABLE_BP
            return (cmd, bp_location)
        elif "clear bp" in cmd:
            parts = cmd.split(" ")
            bp_location = int(parts[2])
            cmd = DebuggerCmds.VM_CLEAR_BP
            return (cmd, bp_location)
        elif cmd == "clear all bps":
            cmd = DebuggerCmds.VM_CLEAR_ALL_BP
            return cmd
        elif "view source" in cmd:
            parts = cmd.split()
            cmd = DebuggerCmds.VM_VIEW_SOURCE
            if len(parts) == 3:
                lineno = int(parts[2])
            else:
                lineno = 0
            return (cmd, lineno)
        elif cmd == "view locals":
            cmd = DebuggerCmds.VM_VIEW_LOCALS
            return cmd
        elif cmd == "view globals":
            cmd = DebuggerCmds.VM_VIEW_GLOBALS
            return cmd
        elif "view local" in cmd:
            parts = cmd.split(" ")
            var = parts[2]
            cmd = DebuggerCmds.VM_VIEW_LOCAL
            return (cmd, var)
        elif "view global" in cmd:
            parts = cmd.split(" ")
            var = parts[2]
            cmd = DebuggerCmds.VM_VIEW_GLOBAL
            return (cmd, var)
        elif "set local" in cmd:
            parts = cmd.split(" ")
            var = parts[2]
            val = parts[3]
            cmd = DebuggerCmds.VM_SET_LOCAL
            return (cmd, var, val)
        elif cmd == "view backtrace":
            cmd = DebuggerCmds.VM_VIEW_BACKTRACE
            return cmd
        elif cmd == "view bp":
            cmd = DebuggerCmds.VM_VIEW_BREAKPOINTS
            return cmd
        elif cmd == "help":
            cmd = DebuggerCmds.HELP
            return cmd
        elif cmd == "quit":
            cmd = DebuggerCmds.QUIT
            return cmd

    def display_prompt(self):
        cmd_str = input(self.__prompt)
        cmd_res = self.parse_command(cmd_str)
        return cmd_res

    def run_vm(self):
        # Run until any breakpoint is hit
        self.__vm_running = True
        while True:
            opmethod, oparg, current_lineno = self.__vm.get_opcode()

            # Check if any breakpoint got hit
            if current_lineno in self.__breakpoints.keys():
                if self.__breakpoints[current_lineno] is True:
                    breakpoint_hit = self.__vm.exec_frame.line_no_obj.get_source_line(current_lineno)
                    draw_header("Breakpoint Hit: %s" % breakpoint_hit)
                    lines = self.__vm.exec_frame.line_no_obj.get_source_sorrounding_line(current_lineno)
                    print(lines)
                    self.__breakpoint_hit = current_lineno
                    return

            terminate = self.__vm.execute_opcode(opmethod, oparg)
            if terminate:
                break

        # Reinitialize for next execution
        self.initialize_vm(self.__code, self.__source, self.__filename)
        print("App exited...")
        self.__vm_running = False
        return

    def next_inst(self):
        if self.__vm_running is False:
            print("App is not running. Run it with 'run'")
            return

        current_lineno = self.__vm.exec_frame.line_no_obj.line_number(self.__vm.exec_frame.ip)
        lineno = current_lineno

        while lineno == current_lineno:
            opmethod, oparg, lineno = self.__vm.get_opcode()
            terminate = self.__vm.execute_opcode(opmethod, oparg)

            if terminate:
                # Reinitialize for next execution
                self.initialize_vm(self.__code, self.__source, self.__filename)
                print("App exited...")
                self.__vm_running = False
                return

        lines = self.__vm.exec_frame.line_no_obj.get_source_sorrounding_line(lineno)
        print(lines)


    def view_asm(self):
        if self.__breakpoint_hit is None:
            # Display the entire source frame for this
            self.__vm.exec_frame.line_no_obj.get_all_source_lines()
        else:
            self.__vm.exec_frame.line_no_obj.get_source_sorrounding_line(self.__breakpoint_hit)

    def execute(self, call_from_vm = True):
        while True:
            arg1 = None

            if not call_from_vm:
                cmd_res = self.display_prompt()
                if isinstance(cmd_res, tuple):
                    cmd = cmd_res[0]
                    arg1 = cmd_res[1]
                else:
                    cmd = cmd_res
            else:
                cmd = DebuggerCmds.VM_RUN

            if cmd is DebuggerCmds.VM_RUN:
                self.run_vm()
            elif cmd is DebuggerCmds.VM_NEXT_INST:
                self.next_inst()
            elif cmd is DebuggerCmds.VM_SET_BP:
                self.set_breakpoint(arg1)
            elif cmd is DebuggerCmds.VM_DISABLE_BP:
                self.disable_breakpoint(arg1)
            elif cmd is DebuggerCmds.VM_CLEAR_BP:
                self.clear_breakpoint(arg1)
            elif cmd is DebuggerCmds.VM_CLEAR_ALL_BP:
                self.clear_all_breakpoints()
            elif cmd is DebuggerCmds.VM_VIEW_LOCALS:
                self.view_locals()
            elif cmd is DebuggerCmds.VM_VIEW_LOCAL:
                self.view_locals(arg1)
            elif cmd is DebuggerCmds.VM_SET_LOCAL:
                val = cmd_res[2]
                self.set_local(arg1, val)
            elif cmd is DebuggerCmds.VM_VIEW_GLOBALS:
                self.view_globals()
            elif cmd is DebuggerCmds.VM_VIEW_GLOBAL:
                self.view_globals(arg1)
            elif cmd is DebuggerCmds.VM_VIEW_BACKTRACE:
                self.view_backtrace()
            elif cmd is DebuggerCmds.VM_VIEW_BREAKPOINTS:
                self.view_breakpoints()
            elif cmd is DebuggerCmds.VM_VIEW_SOURCE:
                self.view_source(arg1)
            elif cmd is DebuggerCmds.HELP:
                self.display_help()
            elif cmd is DebuggerCmds.QUIT:
                sys.exit(0)

            call_from_vm = False