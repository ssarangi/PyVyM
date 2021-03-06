import dis
import operator

# Very good explanation comes from this link. https://ep2013.europython.eu/conference/talks/all-singing-all-dancing-python-bytecode

import sys
from enum import Enum
from src.log import draw_header
from src.debugger_support import LineNo
from src.vmconfig import VMConfig

uninitialized = None

class_exec_frame_attr = "ZZ__EXEC_FRAME__ZZ"

COMPARE_OPERATORS = [
    operator.lt,
    operator.le,
    operator.eq,
    operator.ne,
    operator.gt,
    operator.ge,
    lambda x, y: x in y,
    lambda x, y: x not in y,
    lambda x, y: x is y,
    lambda x, y: x is not y,
    lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    ]

BINARY_OPERATORS = {
    '+':   lambda x, y: x + y,
    '-':   lambda x, y: x - y,
    '*':   lambda x, y: x * y,
    '**':  lambda x, y: x ** y,
    '/':   lambda x, y: x / y,
    '//':  lambda x, y: x // y,
    '<<':  lambda x, y: x << y,
    '>>':  lambda x, y: x >> y,
    '%':   lambda x, y: x % type(x)(y),
    '&':   lambda x, y: x & y,
    '|':   lambda x, y: x | y,
    '^':   lambda x, y: x ^ y,
}

UNARY_OPERATORS = {
    '+': lambda x: abs(x),
    "-": lambda x: -x,
    "~": lambda x: ~x,
    "!": lambda x: not x,
}

class TerminateStates(Enum):
    TERMINATE_PROGRAM = 1
    TERMINATE_FUNCTION = 2

class Base:
    def __init__(self):
        self.__code = None
        self.__ip = 0

    def add_attr(self, attr, value):
        setattr(self, attr, value)

    def get_attr(self, attr):
        if attr in self:
            return getattr(self, attr)

        return None

    def get_code(self):
        return self.__code

    def set_code(self, c):
        self.__code = c

    def __str__(self):
        s = ""
        for attr in self.__dict__:
            s += attr + ": " + str(self.__dict__[attr]) + "\n"

        return s

class Module(Base):
    def __init__(self, name):
        Base.__init__(self)
        self.__classes = {}
        self.__funcs = {}
        self.__name = name

    @property
    def classes(self):
        return self.__classes

    @property
    def functions(self):
        return self.__funcs

    @property
    def code(self):
        return Base.get_code(self)

    @code.setter
    def code(self, c):
        Base.set_code(self, c)

    def add_class(self, class_obj):
        self.__classes[class_obj.name] = class_obj

    def add_function(self, fn):
        self.__funcs[fn.name] = fn

    def add_attr(self, attr, value):
        Base.add_attr(self, attr, value)

    def get_attr(self, attr):
        Base.get_attr(attr)

    def __str__(self):
        return "Module: %s" % self.__name


class Function(Base):
    def __init__(self, name, defaults, code=None):
        Base.__init__(self)
        self.__name = name
        self.__defaults = defaults
        Base.set_code(self, code)

    @property
    def defaults(self):
        return self.__defaults

    @property
    def name(self):
        return self.__name

    @property
    def code(self):
        return Base.get_code(self)

    @code.setter
    def code(self, c):
        Base.set_code(self, c)

    def add_attr(self, attr, value):
        Base.add_attr(self, attr, value)

    def get_attr(self, attr):
        return Base.get_attr(attr)

    def set_code(self, code):
        Base.set_code(code)

    def __str__(self):
        return "Function: %s" % self.__name


class Class(Base):
    def __init__(self, name):
        Base.__init__(self)
        self.__name = name
        self.__special_funcs = {}
        self.__normal_funcs = {}

    @property
    def special_funcs(self):
        return self.__special_funcs

    @property
    def normal_funcs(self):
        return self.__normal_funcs

    def add_special_func(self, fn):
        self.__special_funcs[fn.name] = fn

    def add_normal_func(self, fn):
        self.__normal_funcs[fn.name] = fn

    @property
    def name(self):
        return self.__name

class ClassImpl:
    def __init__(self):
        pass

class Block(Base):
    def __init__(self, code):
        Base.__init__(self)
        Base.set_code(self, code)

    @property
    def code(self):
        return Base.get_code(self)

    def set_code(self, code):
        Base.set_code(code)

class Closure:
    pass


class VMState(Enum):
    BUILD_CLASS = 1
    BUILD_FUNC = 2
    EXEC = 3


def is_special_func(func_name):
    func_start = func_name[0:2]
    func_end = func_name[-2:]

    if func_start == "__" and func_end == "__" and len(func_name) > 2:
        return True

    return False

def create_class_impl(class_impl, class_def):
    for k, v in class_def.special_funcs.items():
        setattr(class_impl, k, v)

    for k, v in class_def.normal_funcs.items():
        setattr(class_impl, k, v)

    return class_impl

class BuildClass:
    def __init__(self, name, code, config, module):
        self.__class_name = name
        self.__code = code.co_code
        self.__ip = 0
        self.__stack = []
        self.__names = code.co_names
        self.__constants = code.co_consts
        self.__module = module
        self.__klass = Class(self.__class_name)
        self.__klass.code = code
        self.__vm_state = VMState.EXEC
        self.__config = config

    @property
    def klass(self):
        return self.__klass

    @property
    def name(self):
        return self.__name

    @property
    def code(self):
        return self.__code

    def popn(self, n):
        if n:
            ret = self.__stack[-n:]
            self.__stack[-n:] = []
            return ret
        else:
            return []

    def get_opcode(self):
        # Based on the settings decide to show the line-by-line trace
        # Get the current line being executed

        ip = self.__ip

        op = self.__code[self.__ip]
        ip += 1
        opmethod = "execute_%s" % dis.opname[op]

        oparg = None
        if op >= dis.HAVE_ARGUMENT:
            low = self.__code[ip]
            high = self.__code[ip + 1]
            oparg = (high << 8) | low

        return opmethod, oparg

    def execute_opcode(self, opmethod, oparg):
        # Update the IP for the opcode
        self.__ip += 1
        if oparg is not None:
            self.__ip += 2

        if (hasattr(self, opmethod)):
            if oparg is not None:
                terminate = getattr(self, opmethod)(oparg)
            else:
                terminate = getattr(self, opmethod)()
        else:
            raise NotImplementedError("Method %s not found." % (opmethod))

        return terminate

    def build(self):
        terminate = False
        while not terminate:
            opmethod, oparg = self.get_opcode()
            terminate = self.execute_opcode(opmethod, oparg)

    def execute_LOAD_CONST(self, consti):
        """
        Pushes co_consts[consti] onto the stack.
        """
        const = self.__constants[consti]
        self.__stack.append(const)


    def execute_LOAD_NAME(self, namei):
        """
        Pushes the value associated with co_names[namei] onto the stack.
        """
        name = self.__names[namei]
        self.__stack.append(name)

    def execute_STORE_NAME(self, namei):
        """
        Implements name = TOS. namei is the index of name in the attribute co_names of the code object. The compiler tries
        to use STORE_FAST or STORE_GLOBAL if possible.
        """
        # Add the name to the current scope
        if self.__vm_state == VMState.EXEC:
            name = self.__names[namei]
            val = self.__stack.pop()
            self.__klass.add_attr(name, val)

    def execute_MAKE_FUNCTION(self, argc):
        """
        Pushes a new function object on the stack. From bottom to top, the consumed stack must consist of argc & 0xFF default argument
        objects in positional order (argc >> 8) & 0xFF pairs of name and default argument, with the name just below the object on the
        stack, for keyword-only parameters (argc >> 16) & 0x7FFF parameter annotation objects a tuple listing the parameter names for the
        annotations (only if there are ony annotation objects) the code associated with the function (at TOS1) the qualified name of the
        function (at TOS)
        """
        num_default_args = argc & 0xFF
        num_kw_args = (argc >> 8) & 0xFF

        name = self.__stack.pop()

        name = name.replace(self.__class_name + ".", "")
        special_func = False
        if is_special_func(name):
            special_func = True

        code = self.__stack.pop()
        defaults = self.popn(num_default_args)

        fn = Function(name, defaults)
        fn.code = code
        if special_func == True:
            self.__klass.add_special_func(fn)
        else:
            self.__klass.add_normal_func(fn)
        self.__vm_state = VMState.BUILD_FUNC

        if self.__config.show_disassembly:
            draw_header("FUNCTION CODE: %s" % name)
            dis.dis(code)

    def execute_RETURN_VALUE(self):
        """
        Returns with TOS to the caller of the function.
        """
        self.__module.add_class(self.__klass)
        return True

class Builtins:
    def __init__(self):
        self.__funcs = {}
        self.__funcs["build_class"] = self.build_class

    def build_class(self, *args):
        build_class_obj = args[0]
        build_class_obj.build()

    @property
    def funcs(self):
        return self.__funcs

class ExecutionFrame:
    def __init__(self, callable, globals, args, kwargs, parent_exec_frame = None, source="", filename="", ip=0):
        assert callable != None, "Code object has to be provided when creating a new code context"

        # Print the line numbers
        self.__ip = ip
        self.__callable = callable
        self.__code = callable.code
        self.__stack = []
        self.__globals_dict = globals
        self.__vm_current_state = VMState.EXEC

        self.__constants = self.__code.co_consts
        self.__names = self.__code.co_names
        self.__program = self.__code.co_code
        self.__nlocals = self.__code.co_nlocals
        self.__local_vars = self.__code.co_varnames

        self.__line_no_obj = LineNo(self.__code.co_firstlineno, self.__code.co_lnotab, source, filename)

        self.__locals = {}

        self.__parent_exec_frame = parent_exec_frame

        self.__source = source
        self.__filename = filename

        # Set the default arguments. This could be optimized so we set it once in the function
        # itself. But then we don't pull from Function locals right now
        if hasattr(callable, "defaults"):
            pos_count = callable.code.co_argcount
            pos_default_count = len(callable.defaults)
            non_default_count = pos_count - pos_default_count

            for i in range(0, len(callable.defaults)):
                var_name = self.__code.co_varnames[non_default_count + i]
                self.__locals[var_name] = callable.defaults[i]

        for i in range(0, len(args)):
            var_name = self.__code.co_varnames[i]
            self.__locals[var_name] = args[i]

        # Set the keyword arguments
        for k, v in kwargs.items():
            self.__locals[k] = v

    def set_args(self, args):
        for i in range(0, len(args)):
            var_name = self.__code.co_varnames[i]
            self.__locals[var_name] = args[i]

    def set_kwargs(self, kwargs):
        # Set the keyword arguments
        for k, v in kwargs.items():
            self.__locals[k] = v

    @property
    def parent_exec_frame(self):
        return self.__parent_exec_frame

    @property
    def callable(self):
        return self.__callable

    @callable.setter
    def callable(self, callable_obj):
        self.__callable = callable_obj
        self.__code = callable_obj.code

        self.__constants = self.__code.co_consts
        self.__names = self.__code.co_names
        self.__program = self.__code.co_code
        self.__nlocals = self.__code.co_nlocals
        self.__local_vars = self.__code.co_varnames

        self.__line_no_obj = LineNo(self.__code.co_firstlineno, self.__code.co_lnotab, self.__source, self.__filename)

    @property
    def line_no_obj(self):
        return self.__line_no_obj

    @property
    def locals(self):
        return self.__locals

    @property
    def program(self):
        return self.__program

    @property
    def names(self):
        return self.__names

    @property
    def constants(self):
        return self.__constants

    @property
    def globals(self):
        return self.__globals_dict

    def get_local_var_name(self, varnum):
        return self.__local_vars[varnum]

    def get_local_var_value(self, varname):
        current_exec_frame = self

        found = False
        while not found or current_exec_frame is not None:
            locals = current_exec_frame.locals
            if varname in locals:
                return locals[varname], current_exec_frame
            else:
                current_exec_frame = current_exec_frame.parent_exec_frame

        raise Exception("Local variable: %s not found in scope" % varname)

    def set_local_var_value(self, varname, value):
        try:
            local_value, exec_frame = self.get_local_var_value(varname)
            exec_frame.locals[varname] = value
        except:
            self.__locals[varname] = value

    def increment_ip(self, val=1):
        self.__ip += val

    def add_global(self, name, val):
        self.__globals_dict[name] = val

    def get_global(self, name):
        if name in self.__globals_dict:
            return self.__globals_dict[name]

        return None

    @property
    def ip(self):
        return self.__ip

    @ip.setter
    def ip(self, v):
        self.__ip = v

    @property
    def code(self):
        return self.__code

    @code.setter
    def code(self, c):
        self.__code = c

    @property
    def vm_state(self):
        return self.__vm_current_state

    @vm_state.setter
    def vm_state(self, state):
        self.__vm_current_state = state

    def top(self):
        return self.__stack[-1]

    def pop(self):
        return self.__stack.pop()

    def popn(self, n):
        if n:
            ret = self.__stack[-n:]
            self.__stack[-n:] = []
            return ret
        else:
            return []

    def append(self, v):
        self.__stack.append(v)

    def __str__(self):
        return str(self.__callable)

class BytecodeVM:
    def __init__(self, code, source, filename):
        self.__code_object = code

        self.__module = Module("main_module")
        self.__module.code = code

        self.__module_frame = ExecutionFrame(self.__module, globals = {}, args = [], kwargs={}, source=source, filename=filename)
        self.__exec_frame = self.__module_frame
        self.__exec_frame_stack = []
        self.__builtins = sys.modules['builtins'].__dict__
        self.__custom_builtins = Builtins()
        self.__source = source
        self.__filename = filename
        self.__config = None
        self.__BUILD_CLASS_STATE = False

    @property
    def exec_frame(self):
        return self.__exec_frame

    @property
    def exec_frame_stack(self):
        return self.__exec_frame_stack

    @property
    def config(self):
        return self.__config

    @config.setter
    def config(self, conf):
        self.__config = conf

    def print_members(self):
        co_methods = [method for method in dir(self.__code_object) if method.startswith("co_")]

        for method in co_methods:
            m = getattr(self.__code_object, method)
            print("Calling method: %s" % method)
            print(m)

    def get_opcode(self):
        # Based on the settings decide to show the line-by-line trace
        # Get the current line being executed
        current_lineno = self.__exec_frame.line_no_obj.line_number(self.__exec_frame.ip)

        ip = self.__exec_frame.ip
            # Update the line number only if the currently executing line has changed.
        if self.__exec_frame.line_no_obj.currently_executing_line is None or \
            self.__exec_frame.line_no_obj.currently_executing_line != current_lineno:
            self.__exec_frame.line_no_obj.currently_executing_line = current_lineno
            self.__exec_frame.line_no_obj.currently_executing_line = current_lineno

        if self.__config.show_line_execution:
            current_line = self.__exec_frame.line_no_obj.get_source_line(current_lineno)
            print("Execution Line: %s" % current_line)

        op = self.__exec_frame.program[self.__exec_frame.ip]
        ip += 1
        opmethod = "execute_%s" % dis.opname[op]

        oparg = None
        if op >= dis.HAVE_ARGUMENT:
            low = self.__exec_frame.program[ip]
            high = self.__exec_frame.program[ip + 1]
            oparg = (high << 8) | low

        return opmethod, oparg, current_lineno

    def execute_opcode(self, opmethod, oparg):
        # Update the IP for the opcode
        self.__exec_frame.ip += 1
        if oparg is not None:
            self.__exec_frame.ip += 2

        if (hasattr(self, opmethod)):
            if oparg is not None:
                terminate = getattr(self, opmethod)(oparg)
            else:
                terminate = getattr(self, opmethod)()
        else:
            raise NotImplementedError("Method %s not found." % (opmethod))

        return terminate

    def execute_next_instruction(self, config=None):
        if config is not None:
            self.__config = config

        opmethod, oparg, current_lineno = self.get_opcode()
        terminate = self.execute_opcode(opmethod, oparg)
        return terminate, current_lineno

    def execute(self, config=None):
        if config is not None:
            self.__config = config

        while True:
            terminate, current_lineno = self.execute_next_instruction()
            if terminate == TerminateStates.TERMINATE_PROGRAM:
                print("Program Terminated:")
                return_val = self.__exec_frame.pop()
                print("Program Return Value: %s" % return_val)
                sys.exit(return_val)
            elif terminate == TerminateStates.TERMINATE_FUNCTION:
                return
            else:
                pass

    def __jump(self, target):
        self.__exec_frame.ip = target

    def execute_NOP(self):
        """
        Do nothing code. Used as a placeholder by the bytecode optimizer.
        """
        pass

    def execute_POP_TOP(self):
        """
        Removes the top-of-stack (TOS) item.
        """
        self.__exec_frame.pop()

    def execute_ROT_TWO(self):
        """
        Swaps the two top-most stack items.
        """
        tos = self.__exec_frame.pop()
        tos1 = self.__exec_frame.pop()
        self.__exec_frame.append(tos)
        self.__exec_frame.append(tos1)

    def execute_ROT_THREE(self):
        """
        Lifts second and third stack item one position up, moves top down to position three.
        """
        tos = self.__exec_frame.pop()
        tos1 = self.__exec_frame.pop()
        tos2 = self.__exec_frame.pop()
        self.__exec_frame.append(tos1)
        self.__exec_frame.append(tos2)
        self.__exec_frame.append(tos)

    def execute_DUP_TOP(self):
        """
        Duplicates the reference on top of the stack.
        """
        top = self.__exec_frame.top()
        self.__exec_frame.append(top)

    def execute_DUP_TOP_TWO(self):
        """
        Duplicates the two references on top of the stack, leaving them in the same order.
        """
        tos = self.__exec_frame.pop()
        tos1 = self.__exec_frame.top()
        self.__exec_frame.append(tos)
        self.__exec_frame.append(tos1)
        self.__exec_frame.append(tos)

    # Unary operations
    # Unary operations take the top of the stack, apply the operation, and push the result back on the stack.

    def __execute_unary(self, op):
        lambda_op = UNARY_OPERATORS[op]
        x = self.__exec_frame.pop()
        self.__exec_frame.append(lambda_op(x))

    def execute_UNARY_POSITIVE(self, oparg):
        """
        Implements TOS = +TOS.
        """
        self.__execute_unary('+')

    def execute_UNARY_NEGATIVE(self, oparg):
        """
        Implements TOS = -TOS.
        """
        self.__execute_unary('-')

    def execute_UNARY_NOT(self, oparg):
        """
        Implements TOS = not TOS.
        """
        self.__execute_unary('!')

    def execute_UNARY_INVERT(self, oparg):
        """
        Implements TOS = ~TOS.
        """
        self.__execute_unary('~')

    def execute_GET_ITER(self):
        """
        Implements TOS = iter(TOS).
        """
        self.__exec_frame.append(iter(self.__exec_frame.pop()))

    # Binary operations
    # Binary operations remove the top of the stack (TOS) and the second top-most stack item (TOS1) from the stack.
    # They perform the operation, and put the result back on the stack.

    def execute_binary_op(self, op):
        lambda_op = BINARY_OPERATORS[op]
        w = self.__exec_frame.pop()
        v = self.__exec_frame.pop()
        self.__exec_frame.append(lambda_op(v, w))

    def execute_BINARY_POWER(self, oparg):
        """
        Implements TOS = TOS1 ** TOS.
        """
        self.execute_binary_op('**')

    def execute_BINARY_MULTIPLY(self):
        """
        Implements TOS = TOS1 * TOS.
        """
        self.execute_binary_op('*')


    def execute_BINARY_FLOOR_DIVIDE(self, oparg):
        """
        Implements TOS = TOS1 // TOS.
        """
        self.execute_binary_op('//')


    def execute_BINARY_TRUE_DIVIDE(self, oparg):
        """
        Implements TOS = TOS1 / TOS.
        """
        self.execute_binary_op('/')


    def execute_BINARY_MODULO(self):
        """
        Implements TOS = TOS1 % TOS.
        """
        self.execute_binary_op('%')

    def execute_BINARY_ADD(self):
        """
        Implements TOS = TOS1 + TOS.
        """
        self.execute_binary_op('+')

    def execute_BINARY_SUBTRACT(self):
        """
        Implements TOS = TOS1 - TOS.
        """
        self.execute_binary_op('-')


    def execute_BINARY_SUBSCR(self):
        """
        Implements TOS = TOS1[TOS].
        """
        tos = self.__exec_frame.pop()
        obj = self.__exec_frame.pop()
        tos = obj[tos]
        self.__exec_frame.append(tos)


    def execute_BINARY_LSHIFT(self):
        """
        Implements TOS = TOS1 << TOS.
        """
        self.execute_binary_op('<<')


    def execute_BINARY_RSHIFT(self):
        """
        Implements TOS = TOS1 >> TOS.
        """
        self.execute_binary_op('>>')


    def execute_BINARY_AND(self):
        """
        Implements TOS = TOS1 & TOS.
        """
        self.execute_binary_op('&')


    def execute_BINARY_XOR(self):
        """
        Implements TOS = TOS1 ^ TOS.
        """
        self.execute_binary_op('^')


    def execute_BINARY_OR(self):
        """
        Implements TOS = TOS1 | TOS.
        """
        self.execute_binary_op('|')


    # In-place operations
    # In-place operations are like binary operations, in that they remove TOS and TOS1, and push
    # the result back on the stack, but the operation is done in-place when TOS1 supports it, and
    # the resulting TOS may be (but does not have to be) the original TOS1.

    def execute_INPLACE_POWER(self):
        """
        Implements in-place TOS = TOS1 ** TOS.
        """
        self.execute_binary_op("**")


    def execute_INPLACE_MULTIPLY(self):
        """
        Implements in-place TOS = TOS1 * TOS.
        """
        self.execute_binary_op("*")


    def execute_INPLACE_FLOOR_DIVIDE(self):
        """
        Implements in-place TOS = TOS1 // TOS.
        """
        self.execute_binary_op("//")


    def execute_INPLACE_TRUE_DIVIDE(self):
        """
        Implements in-place TOS = TOS1 / TOS.
        """
        self.execute_binary_op("/")


    def execute_INPLACE_MODULO(self):
        """
        Implements in-place TOS = TOS1 % TOS.
        """
        self.execute_binary_op("%")


    def execute_INPLACE_ADD(self):
        """
        Implements in-place TOS = TOS1 + TOS.
        """
        self.execute_binary_op("+")


    def execute_INPLACE_SUBTRACT(self):
        """
        Implements in-place TOS = TOS1 - TOS.
        """
        self.execute_binary_op("-")


    def execute_INPLACE_LSHIFT(self):
        """
        Implements in-place TOS = TOS1 << TOS.
        """
        self.execute_binary_op("<<")


    def execute_INPLACE_RSHIFT(self):
        """
        Implements in-place TOS = TOS1 >> TOS.
        """
        self.execute_binary_op(">>")


    def execute_INPLACE_AND(self):
        """
        Implements in-place TOS = TOS1 & TOS.
        """
        self.execute_binary_op("&")


    def execute_INPLACE_XOR(self):
        """
        Implements in-place TOS = TOS1 ^ TOS.
        """
        self.execute_binary_op("^")


    def execute_INPLACE_OR(self):
        """
        Implements in-place TOS = TOS1 | TOS.
        """
        self.execute_binary_op("|")


    def execute_STORE_SUBSCR(self):
        """
        Implements TOS1[TOS] = TOS2.
        """
        key = self.__exec_frame.pop()
        obj = self.__exec_frame.pop()
        val = self.__exec_frame.pop()
        obj[key] = val
        self.__exec_frame.append(obj)


    def execute_DELETE_SUBSCR(self, oparg):
        """
        Implements del TOS1[TOS].
        """
        key = self.__exec_frame.pop()
        obj = self.__exec_frame.pop()
        del obj[key]


    # Miscellaneous opcodes

    def execute_PRINT_EXPR(self, oparg):
        """
        Implements the expression statement for the interactive mode. TOS is removed from the
        stack and printed. In non-interactive mode, an expression statement is terminated with POP_TOP.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_BREAK_LOOP(self, oparg):
        """
        Terminates a loop due to a break statement.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_CONTINUE_LOOP(self, target):
        """
        Continues a loop due to a continue statement. target is the address to jump to (which should be
        a FOR_ITER instruction).
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)

    def execute_SET_ADD(self, i):
        """
        Calls set.add(TOS1[-i], TOS). Used to implement set comprehensions.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LIST_APPEND(self, i):
        """
        Calls list.append(TOS[-i], TOS). Used to implement list comprehensions.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_MAP_ADD(self, i):
        """
        Calls dict.setitem(TOS1[-i], TOS, TOS1). Used to implement dict comprehensions.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    # For all of the SET_ADD, LIST_APPEND and MAP_ADD instructions, while the added value or key/value pair
    # is popped off, the container object remains on the stack so that it is available for further iterations of the loop.

    def execute_RETURN_VALUE(self):
        """
        Returns with TOS to the caller of the function.
        """
        terminate = False
        return_val = self.__exec_frame.top()

        prev_exec_ctx = None
        if len(self.__exec_frame_stack) > 0:
            prev_exec_ctx = self.__exec_frame_stack.pop()

        if prev_exec_ctx is not None:
            self.__exec_frame = prev_exec_ctx

        self.__exec_frame.append(return_val)

        if prev_exec_ctx == None:
            terminate = TerminateStates.TERMINATE_PROGRAM
        else:
            terminate = TerminateStates.TERMINATE_FUNCTION

        return terminate

    def execute_YIELD_VALUE(self):
        """
        Pops TOS and yields it from a generator.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_YIELD_FROM(self):
        """
        Pops TOS and delegates to it as a subiterator from a generator.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    # New in version 3.3.

    def execute_IMPORT_STAR(self):
        """
        Loads all symbols not starting with '_' directly from the module TOS to the local namespace.
        The module is popped after loading all names. This opcode implements from module import *.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_POP_BLOCK(self):
        """
        Removes one block from the block stack. Per frame, there is a stack of blocks, denoting nested loops,
        try statements, and such.
        """
        current_ip = self.__exec_frame.ip
        prev_exec_frame = self.__exec_frame_stack.pop()
        self.__exec_frame = prev_exec_frame
        self.__jump(current_ip)

    def execute_POP_EXCEPT(self):
        """
        Removes one block from the block stack. The popped block must be an exception handler block, as implicitly
        created when entering an except handler. In addition to popping extraneous values from the frame stack,
        the last three popped values are used to restore the exception state.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_END_FINALLY(self):
        """
        Terminates a finally clause. The interpreter recalls whether the exception has to be re-raised, or whether
        the function returns, and continues with the outer-next block.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LOAD_BUILD_CLASS(self):
        """
        Pushes builtins.__build_class__() onto the stack. It is later called by CALL_FUNCTION to construct a class.
        """
        self.__exec_frame.append(self.__custom_builtins.build_class)
        self.__BUILD_CLASS_STATE = True

    def execute_SETUP_WITH(self, delta):
        """
        This opcode performs several operations before a with block starts. First, it loads __exit__() from the
        context manager and pushes it onto the stack for later use by WITH_CLEANUP. Then, __enter__() is called, and
        a finally block pointing to delta is pushed. Finally, the result of calling the enter method is pushed onto the
        stack. The next opcode will either ignore it (POP_TOP), or store it in (a) variable(s) (STORE_FAST, STORE_NAME,
        or UNPACK_SEQUENCE).
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)

    def execute_WITH_CLEANUP(self):
        """
        Cleans up the stack when a with statement block exits. TOS is the context manager’s __exit__() bound method.
        Below TOS are 1–3 values indicating how/why the finally clause was entered:
        SECOND = None
        (SECOND, THIRD) = (WHY_{RETURN,CONTINUE}), retval
        SECOND = WHY_*; no retval below it
        (SECOND, THIRD, FOURTH) = exc_info()
        In the last case, TOS(SECOND, THIRD, FOURTH) is called, otherwise TOS(None, None, None). In addition, TOS is
        removed from the stack.

        If the stack represents an exception, and the function call returns a ‘true’ value, this information is “zapped”
        and replaced with a single WHY_SILENCED to prevent END_FINALLY from re-raising the exception. (But non-local gotos
        will still be resumed.)

        All of the following opcodes expect arguments. An argument is two bytes, with the more significant byte last.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)

    def execute_STORE_NAME(self, namei):
        """
        Implements name = TOS. namei is the index of name in the attribute co_names of the code object. The compiler tries
        to use STORE_FAST or STORE_GLOBAL if possible.
        """
        # Add the name to the current scope
        if self.__exec_frame.vm_state == VMState.EXEC:
            value = self.__exec_frame.pop()
            name = self.__exec_frame.names[namei]

            if isinstance(self.__exec_frame.callable, Module):
                self.__exec_frame.add_global(name, value)
            else:
                self.__exec_frame.set_local_var_value(name, value)

    def execute_DELETE_NAME(self, namei):
        """
        Implements del name, where namei is the index into co_names attribute of the code object.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_UNPACK_SEQUENCE(self, count):
        """
        Unpacks TOS into count individual values, which are put onto the stack right-to-left.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_UNPACK_EX(self, counts):
        """
        Implements assignment with a starred target: Unpacks an iterable in TOS into individual values, where the total number
        of values can be smaller than the number of items in the iterable: one the new values will be a list of all leftover items.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    # The low byte of counts is the number of values before the list value, the high byte of counts the number of values after it. The resulting values are put onto the stack right-to-left.

    def execute_STORE_ATTR(self, namei):
        """
        Implements TOS.name = TOS1, where namei is the index of name in co_names.
        """
        obj = self.__exec_frame.pop()
        val = self.__exec_frame.pop()
        name = self.__exec_frame.names[namei]
        setattr(obj, name, val)



    def execute_DELETE_ATTR(self, namei):
        """
        Implements del TOS.name, using namei as index into co_names.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_STORE_GLOBAL(self, namei):
        """
        Works as STORE_NAME, but stores the name as a global.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_DELETE_GLOBAL(self, namei):
        """
        Works as DELETE_NAME, but deletes a global name.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LOAD_CONST(self, consti):
        """
        Pushes co_consts[consti] onto the stack.
        """
        const = self.__exec_frame.constants[consti]
        self.__exec_frame.append(const)


    def execute_LOAD_NAME(self, namei):
        """
        Pushes the value associated with co_names[namei] onto the stack.
        """
        self.execute_LOAD_GLOBAL(namei)


    def execute_BUILD_TUPLE(self, count):
        """
        Creates a tuple consuming count items from the stack, and pushes the resulting tuple onto the stack.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_BUILD_LIST(self, count):
        """
        Works as BUILD_TUPLE, but creates a list.
        """
        if count == 0:
            var = []
            self.__exec_frame.append(var)


    def execute_BUILD_SET(self, count):
        """
        Works as BUILD_TUPLE, but creates a set.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_BUILD_MAP(self, count):
        """
        Pushes a new dictionary object onto the stack. The dictionary is pre-sized to hold count entries.
        """
        self.__exec_frame.append({})


    def execute_LOAD_ATTR(self, namei):
        """
        Replaces TOS with getattr(TOS, co_names[namei]).
        """
        obj = self.__exec_frame.pop()
        name = self.__exec_frame.names[namei]
        attr = getattr(obj, name)
        self.__exec_frame.append(attr)

        # Function calls for Classes would need a reference to the class obj
        if isinstance(attr, Function):
            self.__exec_frame.append(obj)


    def execute_COMPARE_OP(self, compare_op):
        """
        Performs a Boolean operation. The operation name can be found in cmp_op[opname].
        """
        w = self.__exec_frame.pop()
        v = self.__exec_frame.pop()
        if len(COMPARE_OPERATORS) < compare_op:
            raise NotImplementedError("Compare Op %s not implemented" % compare_op)

        value = COMPARE_OPERATORS[compare_op](v, w)
        self.__exec_frame.append(value)

    def execute_IMPORT_NAME(self, namei):
        """
        Imports the module co_names[namei]. TOS and TOS1 are popped and provide the fromlist and level arguments of __import__().
        The module object is pushed onto the stack. The current namespace is not affected: for a proper import statement, a subsequent
        STORE_FAST instruction modifies the namespace.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)

    def execute_IMPORT_FROM(self, namei):
        """
        Loads the attribute co_names[namei] from the module found in TOS. The resulting object is pushed onto the stack,
        to be subsequently stored by a STORE_FAST instruction.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_JUMP_FORWARD(self, delta):
        """
        Increments bytecode counter by delta.
        """
        self.__exec_frame.ip += delta


    def execute_POP_JUMP_IF_TRUE(self, target):
        """
        If TOS is true, sets the bytecode counter to target. TOS is popped.
        """
        if self.__exec_frame.top():
            self.__exec_frame.ip = target
            self.__exec_frame.pop()

    def execute_POP_JUMP_IF_FALSE(self, target):
        """
        If TOS is false, sets the bytecode counter to target. TOS is popped.
        """
        if not self.__exec_frame.top():
            self.__exec_frame.ip = target
            self.__exec_frame.pop()

    def execute_JUMP_IF_TRUE_OR_POP(self, target):
        """
        If TOS is true, sets the bytecode counter to target and leaves TOS on the stack. Otherwise (TOS is false), TOS is popped.
        """
        if self.__exec_frame.top():
            self.__exec_frame.ip = target
        else:
            self.__exec_frame.pop()

    def execute_JUMP_IF_FALSE_OR_POP(self, target):
        """
        If TOS is false, sets the bytecode counter to target and leaves TOS on the stack. Otherwise (TOS is true), TOS is popped.
        """
        if not self.__exec_frame.top():
            self.__exec_frame.ip = target
        else:
            self.__exec_frame.pop()


    def execute_JUMP_ABSOLUTE(self, target):
        """
        Set bytecode counter to target.
        """
        self.__exec_frame.ip = target

    def execute_FOR_ITER(self, delta):
        """
        TOS is an iterator. Call its __next__() method. If this yields a new value, push it on the stack (leaving the iterator below it).
        If the iterator indicates it is exhausted TOS is popped, and the byte code counter is incremented by delta.
        """
        iter_obj = self.__exec_frame.top()
        try:
            iter_obj = next(iter_obj)
            self.__exec_frame.append(iter_obj)
        except StopIteration:
            self.__exec_frame.pop()
            self.__jump(self.__exec_frame.ip + delta)

    def execute_LOAD_GLOBAL(self, namei):
        """
        Loads the global named co_names[namei] onto the stack.
        """
        name = self.__exec_frame.names[namei]
        global_v = self.__exec_frame.get_global(name)
        if global_v is None:
            # Check if the global is a builtin
            if name in self.__builtins:
                global_v = self.__builtins[name]

        if global_v is None:
            global_v = self.__exec_frame.get_global(name)

        if global_v is None:
            # Look in the class modules to see if it is a class
            if name in self.__module.classes:
                class_def = self.__module.classes[name]
                class_impl = ClassImpl()
                class_impl = create_class_impl(class_impl, class_def)
                setattr(class_impl, "code", class_def.code)
                global_v = class_impl.__init__
                # Create a new exection context and associate it with this class
                exec_ctx = ExecutionFrame(class_impl, self.__exec_frame.globals, [], {}, source=self.__source, filename=self.__filename)
                exec_ctx.set_local_var_value("self", class_impl)
                setattr(class_impl, class_exec_frame_attr, exec_ctx)
                self.__exec_frame.append(global_v)
                self.__exec_frame.append(class_impl)
                return

        if global_v is None:
            raise Exception("Global Value %s is not defined" % name)

        if global_v is not None:
            self.__exec_frame.append(global_v)


    def execute_SETUP_LOOP(self, delta):
        """
        Pushes a block for a loop onto the block stack. The block spans from the current instruction with a size of delta bytes.
        """
        block = Block(self.__exec_frame.code)
        exec_frame = ExecutionFrame(block, self.__exec_frame.globals, [], {}, parent_exec_frame=self.__exec_frame, ip=self.__exec_frame.ip, source=self.__source, filename=self.__filename)
        self.__exec_frame_stack.append(self.__exec_frame)
        self.__exec_frame = exec_frame


    def execute_SETUP_EXCEPT(self, delta):
        """
        Pushes a try block from a try-except clause onto the block stack. delta points to the first except block.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_SETUP_FINALLY(self, delta):
        """
        Pushes a try block from a try-except clause onto the block stack. delta points to the finally block.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_STORE_MAP(self):
        """
        Store a key and value pair in a dictionary. Pops the key and value while leaving the dictionary on the stack.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LOAD_FAST(self, var_num):
        """
        Pushes a reference to the local co_varnames[var_num] onto the stack.
        """
        varname = self.__exec_frame.get_local_var_name(var_num)
        local_var, exec_frame = self.__exec_frame.get_local_var_value(varname)
        self.__exec_frame.append(local_var)


    def execute_STORE_FAST(self, var_num):
        """
        Stores TOS into the local co_varnames[var_num].
        """
        varname = self.__exec_frame.get_local_var_name(var_num)
        value = self.__exec_frame.pop()
        self.__exec_frame.set_local_var_value(varname, value)

    def execute_DELETE_FAST(self, var_num):
        """
        Deletes local co_varnames[var_num].
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LOAD_CLOSURE(self, i):
        """
        Pushes a reference to the cell contained in slot i of the cell and free variable storage. The name of the variable is
        co_cellvars[i] if i is less than the length of co_cellvars. Otherwise it is co_freevars[i - len(co_cellvars)].
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LOAD_DEREF(self, i):
        """
        Loads the cell contained in slot i of the cell and free variable storage. Pushes a reference to the object the cell
        contains on the stack.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_LOAD_CLASSDEREF(self, i):
        """
        Much like LOAD_DEREF but first checks the locals dictionary before consulting the cell. This is used for loading free
        variables in class bodies.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_STORE_DEREF(self, i):
        """
        Stores TOS into the cell contained in slot i of the cell and free variable storage.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_DELETE_DEREF(self, i):
        """
        Empties the cell contained in slot i of the cell and free variable storage. Used by the del statement.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_RAISE_VARARGS(self, argc):
        """
        Raises an exception. argc indicates the number of parameters to the raise statement, ranging from 0 to 3. The handler will
        find the traceback as TOS2, the parameter as TOS1, and the exception as TOS.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_CALL_FUNCTION(self, argc):
        """
        Calls a function. The low byte of argc indicates the number of positional parameters, the high byte the number of keyword
        parameters. On the stack, the opcode finds the keyword parameters first. For each keyword argument, the value is on top of
        the key. Below the keyword parameters, the positional parameters are on the stack, with the right-most parameter on top.
        Below the parameters, the function object to call is on the stack. Pops all function arguments, and the function itself off
        the stack, and pushes the return value.
        """
        num_positional_args = argc & 0xF
        num_keyword_args = (argc >> 8) & 0xF

        kwargs = {}
        for i in range(0, num_keyword_args):
            val = self.__exec_frame.pop()
            arg_name = self.__exec_frame.pop()
            kwargs[arg_name] = val

        args = [self.__exec_frame.pop() for i in range(num_positional_args)]
        args.reverse()

        callable = self.__exec_frame.pop()

        if not isinstance(callable, Function) and not isinstance(callable, ClassImpl):
            # This is a builtin function. Then directly run it
            self.__exec_frame.append(callable)
            result = callable(*args)
            self.__exec_frame.pop()
            self.__exec_frame.append(result)
            return

        BUILD_CLASS = False
        if isinstance(callable, ClassImpl):
            # if the callable is the constructor of the class, then add the constructor to the top
            class_obj = callable
            callable = self.__exec_frame.pop()

            func_name = callable.name
            if func_name == "__init__":
                BUILD_CLASS = True

            exec_frame = getattr(class_obj, class_exec_frame_attr)
            exec_frame.set_args(args)
            exec_frame.set_kwargs(kwargs)
            exec_frame.callable = callable

            # Reset the IP
            exec_frame.ip = 0
        else:
            exec_frame = ExecutionFrame(callable, self.__exec_frame.globals, args, kwargs, source=self.__source, filename=self.__filename)
        self.__exec_frame_stack.append(self.__exec_frame)
        self.__exec_frame = exec_frame

        self.execute()

        if BUILD_CLASS == True:
            # Init Function must have been called.
            # Init functions cannot return anything. They will return just NONE. However, the class object needs to be
            # assigned to the caller. So we will pop the stack for the NONE value and push the class object into the stack.
            self.__exec_frame.pop()
            self.__exec_frame.append(class_obj)

    def execute_MAKE_FUNCTION(self, argc):
        """
        Pushes a new function object on the stack. From bottom to top, the consumed stack must consist of argc & 0xFF default argument
        objects in positional order (argc >> 8) & 0xFF pairs of name and default argument, with the name just below the object on the
        stack, for keyword-only parameters (argc >> 16) & 0x7FFF parameter annotation objects a tuple listing the parameter names for the
        annotations (only if there are ony annotation objects) the code associated with the function (at TOS1) the qualified name of the
        function (at TOS)
        """
        num_default_args = argc & 0xFF
        num_kw_args = (argc >> 8) & 0xFF

        name = self.__exec_frame.pop()
        code = self.__exec_frame.pop()
        defaults = self.__exec_frame.popn(num_default_args)

        if self.__BUILD_CLASS_STATE == True:
            build_class = BuildClass(name, code, self.__config, self.__module)
            self.__exec_frame.append(build_class)
            self.__BUILD_CLASS_STATE = False
        else:
            fn = Function(name, defaults)
            fn.code = code
            self.__exec_frame.add_global(name, fn)
            self.__exec_frame.vm_state = VMState.BUILD_FUNC

        if self.__config.show_disassembly:
            draw_header("FUNCTION CODE: %s" % name)
            dis.dis(code)

    def execute_MAKE_CLOSURE(self, argc):
        """
        Creates a new function object, sets its __closure__ slot, and pushes it on the stack. TOS is the qualified name of the function,
        TOS1 is the code associated with the function, and TOS2 is the tuple containing cells for the closure’s free variables. argc is
        interpreted as in MAKE_FUNCTION; the annotations and defaults are also in the same order below TOS2.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)

    def execute_BUILD_SLICE(self, argc):
        """
        Pushes a slice object on the stack. argc must be 2 or 3. If it is 2, slice(TOS1, TOS) is pushed; if it is 3, slice(TOS2, TOS1, TOS)
        is pushed. See the slice() built-in function for more information.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_EXTENDED_ARG(self, ext):
        """
        Prefixes any opcode which has an argument too big to fit into the default two bytes. ext holds two additional bytes which, taken
        together with the subsequent opcode’s argument, comprise a four-byte argument, ext being the two most-significant bytes.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_CALL_FUNCTION_VAR(self, argc):
        """
        Calls a function. argc is interpreted as in CALL_FUNCTION. The top element on the stack contains the variable argument list,
        followed by keyword and positional arguments.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_CALL_FUNCTION_KW(self, argc):
        """
        Calls a function. argc is interpreted as in CALL_FUNCTION. The top element on the stack contains the keyword arguments dictionary,
        followed by explicit keyword and positional arguments.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)


    def execute_CALL_FUNCTION_VAR_KW(self, argc):
        """
        Calls a function. argc is interpreted as in CALL_FUNCTION. The top element on the stack contains the keyword arguments dictionary,
        followed by the variable-arguments tuple, followed by explicit keyword and positional arguments.
        """
        raise NotImplementedError("Method %s not implemented" % sys._getframe().f_code.co_name)