from __future__ import print_function

__author__      = "Remi Chateauneu"
__copyright__   = "Primhill Computers, 2018-2021"
__credits__ = ["", "", ""]
__license__ = "GPL"
__version__ = "0.0.1"
__maintainer__ = "Remi Chateauneu"
__email__ = "contact@primhillcomputers.com"
__status__ = "Development"

import re
import os
import sys
import six
import struct
import logging
import threading
import collections
import traceback

import win32file
import win32con
import win32process

# FIXME: For tests only !!
import psutil

if __package__:
    from . import cim_objects_definitions
else:
    import cim_objects_definitions

if cim_objects_definitions.is_py3:
    import queue
else:
    import Queue as queue

if __package__:
    from . import pydbg
    from .pydbg import defines
    from .pydbg import windows_h
    from .pydbg import utils
else:
    import pydbg
    from pydbg import defines
    from pydbg import windows_h
    from pydbg import utils

################################################################################

# This models what can be done with the detection of function calls
# in a running program. It is possible to report the function,
# and also report the creation or update of an object, modelled with CIM,
# or an extension of CIM.
class TracerBase(object):
    def report_function_call(self, function_name, process_id):
        assert isinstance(function_name, six.binary_type)
        raise NotImplementedError("Must not be implemented")

    def report_object_creation(self, cim_objects_context, cim_class_name, **cim_arguments):
        raise NotImplementedError("Must not be implemented")


class PseudoTraceLineCore:
    """
    This uses duck typing to behave like a BatchLetCore.
    """
    def __init__(self, process_id, function_name):
        self.m_pid = process_id
        # This is not applicable to Windows, yet.
        self.m_status = 999999
        assert isinstance(function_name, six.binary_type)
        self._function_name = function_name
        self._return_value = 0
        # This is intentionaly an invalid value which is easy to spot if it is not properly initialised.
        self._time_start = 99999999.99 # time.time()
        self._time_end = self._time_start

    # TODO: Finish this list.
    _functions_creating_processes = set(["CreateProcessW", "CreateProcessA"])

    def is_creating_process(self):
        return self._function_name in self._functions_creating_processes


class PseudoTraceLine:
    """
    This is functionally equivalent to a line displayed by strace or ltrace:
    It contains a process id, a function name and its arguments.
    """
    def __init__(self, process_id, function_name):
        assert isinstance(function_name, six.binary_type)
        self.m_core = PseudoTraceLineCore(process_id, function_name)
        # So, consecutive calls can be aggregated.
        # This compresses consecutive calls, in a loop, to the same function.
        self.m_occurrences = 1
        # The style tells if this is a native call or an aggregate of function calls.
        self.m_style = "Breakpoint"

    def write_to_file(self, file_descriptor):
        """This writes the content, so it can be deserialized, to replay a session."""
        assert isinstance(self.m_core._function_name, six.binary_type)
        file_descriptor.write("%d %s\n" % (self.m_core.m_pid, self.m_core._function_name.decode('utf-8)')))

    @staticmethod
    def read_from_file(file_descriptor):
        function_call_line = file_descriptor.readline().split()
        process_id = int(function_call_line[0])
        function_name = function_call_line[1].encode()
        return PseudoTraceLine(process_id, function_name)

    def is_same_call(self, another_object):
        """Process creations or setup are not aggregated."""
        assert isinstance(self.m_core._function_name, six.binary_type)
        assert isinstance(another_object.m_core._function_name, six.binary_type)
        return self.m_core._function_name == another_object.m_core._function_name \
               and not self.m_core.is_creating_process() \
               and not another_object.m_core.is_creating_process()

    def get_significant_args(self):
        return []


class Win32Tracer(TracerBase):

    # These function names are a convention to indicate the program start and end.
    _function_name_process_start = b"PYDBG_PROCESS_START"
    _function_name_process_exit = b"PYDBG_PROCESS_EXIT"

    def _callback_process_creation(self, created_process_id):
        logging.debug("_callback_process_creation created_process_id=%d" % created_process_id)
        # The first message of this queue is a conventional function call which contains the created process id.
        # After that, it contains only genuine function calls, plus the last one,
        # also conventional, which indicates the process end, and releases the main process.
        batch_core = PseudoTraceLine(created_process_id, self._function_name_process_start)
        self._queue.put(batch_core)

    def _start_debugging_pid(self):
        """This is executed in a Python thread which attaches to a running process."""
        logging.debug("_start_debugging_pid")
        assert self._input_process_id > 0
        assert not self._command_line
        logging.info("_start_debugging self._input_process_id=%d" % self._input_process_id)
        self._hooks_manager.attach_to_pid(self._input_process_id)

        # This signals the end of execution.
        self.report_function_call(self._function_name_process_exit, 0)
        # created_process.terminate()
        # created_process.join()

    def _start_debugging_cmd(self):
        """This is executed in a Python thread which starts a command in a subprocess."""
        assert self._input_process_id <= 0
        logging.info("_start_debugging self._command_line=%s" % self._command_line)
        command_as_string = " ".join(self._command_line)
        self._root_pid = self._hooks_manager.attach_to_command(command_as_string, self._callback_process_creation)

        # This signals the end of execution.
        self.report_function_call(self._function_name_process_exit, 0)
        # created_process.terminate()
        # created_process.join()

    def tee_calls_stream(self, log_stream, output_files_prefix):
        assert isinstance(log_stream, queue.Queue)

        class TeeQueue:
            def __init__(self):
                self._log_stream = log_stream
                assert output_files_prefix[-1] != '.'
                log_filename = output_files_prefix + ".log"
                self._out_file_descriptor = open(log_filename, "w")
                logging.info("Creating log file:%s" % log_filename)

            def get(self, block=True, timeout=None):
                logging.info("get timeout:%s" % str(timeout))
                next_function_call = self._log_stream.get(block, timeout)
                assert isinstance(next_function_call, PseudoTraceLine)
                # When replaying, each line is deserialized into a PseudoTraceLine.
                next_function_call.write_to_file(self._out_file_descriptor)
                return next_function_call

        return TeeQueue()

    def create_logfile_stream(self, command_line, process_id):
        """
        This starts a a new process running a command, or attaches to a running process,
        the returns the id of the process to debung, and a queue which receives all system function calls.
        This is a virtual function which exists for tracer class, i.e. the objects yielding a queue
        or a stream of the system calls of the debugged process.
        This is not a very fast mechanism but is intended to monitor only a small set of key functions.

        :param command_line: A command line to execute, or an empty list.
        :param process_id: A process if, or a zero or negative number.
        :return: Returns a tuple of the id of the running process, and a queue of the system function calls.
        """
        logging.info("create_logfile_stream command_line=%s process_id=%d" % (command_line, process_id))

        assert isinstance(command_line, list)
        assert isinstance(process_id, int)
        assert (command_line == []) ^ (process_id < 0)

        logging.info("Creating Win32Hook_Manager")
        self._hooks_manager = Win32Hook_Manager()
        logging.info("Created Win32Hook_Manager")
        self._command_line = command_line
        logging.info("Created Win32Hook_Manager self._command_line=%s" % str(self._command_line))
        self._queue = queue.Queue()

        self._input_process_id = process_id
        if self._input_process_id < 0:
            # It is possible to start the process in a Python thread and resume it in another,
            # because these are not real threads. It might be possible to do that
            # in different threads, but it is better not to take the risk.
            logging.info("create_logfile_stream process will be started in thread")

            self._debugging_thread = threading.Thread(target=self._start_debugging_cmd, args=())
            self._debugging_thread.start()
            logging.info("Waiting for process id to be set")
            process_start_timeout = 10.0
            first_function_call = self._queue.get(True, timeout=process_start_timeout)
            assert isinstance(first_function_call, PseudoTraceLine)
            logging.info("first_function_call.m_core._function_name=%s" % first_function_call.m_core._function_name)
            logging.info("self._function_name_process_start=%s" % self._function_name_process_start)
            assert first_function_call.m_core._function_name == self._function_name_process_start
            self._top_process_id = first_function_call.m_core.m_pid
        else:
            logging.info("Process already set process_id=%d" % process_id)
            self._top_process_id = process_id

            self._debugging_thread = threading.Thread(target=self._start_debugging_pid, args=())
            self._debugging_thread.start()

            # This does not specifically wait for the first function call because the process is already running.

        logging.info("create_logfile_stream self._top_process_id=%d" % self._top_process_id)
        return self._top_process_id, self._queue

    def logfile_pathname_to_stream(self, input_log_file):
        """Used when replaying a trace session. This returns an object, on which each read access
        return a conceptual function call, similar to what is returned when monitoring a process.
        """
        class ReplayStream:
            def __init__(self):
                self._in_file_descriptor = open(input_log_file)

            def get(self, block=True, timeout=None):
                next_function_call = PseudoTraceLine.read_from_file(self._in_file_descriptor)
                return next_function_call

        return ReplayStream()

    def create_flows_from_calls_stream(self, log_stream):
        """This yields objects which model a function call."""
        # TODO: So why not simply returning self instead of the queue ?
        logging.info("create_flows_from_calls_stream Starting")

        queue_timeout = 30.0  # Seconds.

        while True:
            try:
                logging.debug("Waiting entering queue_timeout=%d" % queue_timeout)
                # We could use the queue to signal the end of the loop.
                pseudo_trace_line = log_stream.get(True, timeout=queue_timeout)
            except queue.Empty:
                logging.warning("Waiting queue_timeout=%d" % queue_timeout)
                continue
            #print("create_flows_from_calls_stream Function=", pseudo_trace_line.m_core._function_name)
            assert isinstance(pseudo_trace_line, PseudoTraceLine)

            logging.warning("_function_name=%s" % pseudo_trace_line.m_core._function_name)
            if pseudo_trace_line.m_core._function_name == self._function_name_process_exit:
                logging.info("Exit detected")
                return

            yield pseudo_trace_line
        logging.info("Leaving")

    def report_function_call(self, function_name, task_id):
        """This is called in the debugger context."""
        assert isinstance(function_name, six.binary_type)
        batch_core = PseudoTraceLine(task_id, function_name)
        self._queue.put(batch_core)

    def report_object_creation(self, cim_objects_context, cim_class_name, **cim_arguments):
        cim_objects_context.attributes_to_cim_object(cim_class_name, **cim_arguments)


# This must be replaced by an object of a derived class.
tracer_object = None # Win32Tracer()


################################################################################
class Win32Hook_Manager(pydbg.pydbg):
    def __init__(self):
        super(Win32Hook_Manager, self).__init__()
        self.m_core = None
        logging.debug("Win32Hook_Manager ctor")
        assert self.pid == 0

        # This contains the list of dlls which were loaded.
        # It is a helper to indiacte which funcitons calls are worth to investigate.
        self.dlls_set = set()

        self.create_process_handle = None

        class process_hooks_definition(object):
            def __init__(self):
                self.hooked_functions = utils.hook_container()
                self.unhooked_functions_by_dll = collections.defaultdict(list)

        # Indexed by the pid of subprocesses of the root pid, as a flattened tree.
        self.hooks_by_processes = collections.defaultdict(process_hooks_definition)

        # TODO: Ideally this cache should be refreshed each time a new module is loaded,
        # TODO: otherwise the entire list of modules must be reexplored when  a module does not exist.
        # TODO: Still, this is a better solution.
        self.dict_dll_to_base_address =  self.get_base_address_dict()

    def __del__(self):
        self.stop_cleanup()

    def debug_print_hooks_counter(self):
        """
        This is exclusively for debugging purpose.
        """
        print("DLLs")
        for one_dll_name in sorted(self.dlls_set):
            print("    ", one_dll_name)

        # This displays how many times functions where hooked, cumulated by processes.
        print("Functions calls")
        for process_id in self.hooks_by_processes:
            print("pid=", process_id)
            hooks_container = self.hooks_by_processes[process_id].hooked_functions
            hooks_by_function_name = {
                the_hook.function_name: the_hook
                for one_address, the_hook in hooks_container.hooks.items()}

            for one_function_name in sorted(list(hooks_by_function_name.keys())):
                the_hook = hooks_by_function_name[one_function_name]
                print("    %-30s %3d %3d" % (
                      one_function_name,
                      the_hook.counter_proxy_on_entry,
                      the_hook.counter_proxy_on_exit))

    def stop_cleanup(self):
        """
        This tests on win32process, otherwise, exiting the program might display the error message:
        Exception AttributeError: "'NoneType' object has no attribute 'GetProcessId'"
        in <bound method Win32Hook_Manager.__del__ of <survol.scripts.win32_api_definitions.Win32Hook_Manager
        object at 0x0000000003FF1C50>> ignored
        """
        if self.create_process_handle and win32process:
            # We cannot rely anymore on self.pid because it might point to a subprocess.
            created_process_id = win32process.GetProcessId(self.create_process_handle)
            logging.debug("Current_Pid=%d" % os.getpid())

            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            logging.debug("Killing subprocesses of created_process_id=%d" % created_process_id)
            for child_process in children:
                if child_process.pid != created_process_id:
                    logging.debug('==== Killing child pid {}'.format(child_process.pid))
                    pydbg.wait_for_process_exit(child_process.pid)

            pydbg.wait_for_process_exit(created_process_id)
            # The destructor might be called at any moment by the garbage collector,
            # and this would delete all subprocesses of the current process.
            # Setting the handle to None prevents this.
            self.create_process_handle = None

    def add_one_function_from_dll_address(self, hooked_pid, dll_address, the_subclass):
        """
        This must use the process id self.pid, which is not the current process,
        and may be a subprocess of the target pid.
        """
        the_subclass.function_address = self.func_resolve_from_dll(dll_address, the_subclass.function_name)
        assert the_subclass.function_address

        def hook_function_adapter_entry(object_pydbg, function_arguments):
            """
            There is one such function per class associated to an API function.
            The arguments are stored per thread, and implictly form a stack.
            """

            logging.debug("hook_function_adapter_entry class=%s args=%s" % (the_subclass.__name__, function_arguments))
            subclass_instance = the_subclass()
            subclass_instance.set_hook_manager(object_pydbg)

            # This instance object has the same visibility and scope than the arguments.
            # Therefore, they are stored together with a hack of appending the instance at the arguments'end.
            # This instance is a context for the results of anything done before the function call.
            subclass_instance.callback_before(function_arguments)
            function_arguments.append(subclass_instance)
            assert isinstance(the_subclass.function_name, six.binary_type)
            tracer_object.report_function_call(the_subclass.function_name, object_pydbg.dbg.dwProcessId)
            subclass_instance.__class__._debug_counter_before += 1
            return defines.DBG_CONTINUE

        def hook_function_adapter_exit(object_pydbg, function_arguments, function_result):
            """There is one such function per class associated to an API function."""
            logging.debug("hook_function_adapter_exit class=%s args=%s result=%s"
                          % (the_subclass.__name__, function_arguments, function_result))
            subclass_instance = function_arguments[-1]
            function_arguments.pop()
            # So we can use arguments stored before the actual function call.
            subclass_instance.callback_after(function_arguments, function_result)
            subclass_instance.__class__._debug_counter_after += 1
            return defines.DBG_CONTINUE

        self.hooks_by_processes[hooked_pid].hooked_functions.add(self,
                         the_subclass.function_address,
                         len(the_subclass.args_list),
                         hook_function_adapter_entry,
                         hook_function_adapter_exit,
                         the_subclass.function_name)

    @staticmethod
    def callback_event_handler_load_dll(self):
        # self.dbg.u.LoadDll is _LOAD_DLL_DEBUG_INFO
        dll_filename = win32file.GetFinalPathNameByHandle(
            self.dbg.u.LoadDll.hFile, win32con.FILE_NAME_NORMALIZED)
        if dll_filename.startswith("\\\\?\\"):
            dll_filename = dll_filename[4:]

        assert isinstance(dll_filename, six.text_type)
        dll_canonic_name = self.canonic_dll_name(dll_filename.encode('utf-8'))

        self.dlls_set.add(dll_canonic_name)
        logging.debug("LOAD:%s" % dll_canonic_name)

        unhooked_functions = self.hooks_by_processes[self.dbg.dwProcessId].unhooked_functions_by_dll[dll_canonic_name]

        # At this stage, the library cannot be found with CreateToolhelp32Snapshot,
        #  and Module32First/Module32Next. But the dll object is passed to the callback.
        dll_address = self.dbg.u.LoadDll.lpBaseOfDll
        for one_subclass in unhooked_functions:
            if dll_canonic_name in [b'msvcrt.dll', b'ws2_32.dll']:
                logging.debug("    function_name=%s" % one_subclass.function_name)
            self.add_one_function_from_dll_address(self.dbg.dwProcessId, dll_address, one_subclass)

        return defines.DBG_CONTINUE

    @staticmethod
    def callback_event_handler_create_process(self):
        """
        This handler should not be necessary because creation of processes are detected
        by hooking CreatingProcessA and CreatingProcessW
        """
        created_process_id = win32process.GetProcessId(self.dbg.u.CreateProcessInfo.hProcess)
        logging.debug("event_handler_create_process dwProcessId=%d created_process_id=%d self.pid=%d"
                      % (self.dbg.dwProcessId, created_process_id, self.pid))
        return defines.DBG_CONTINUE

    @staticmethod
    def callback_event_handler_access_violation(self):
        """
        When catching an access violation, and to terminate the process,
        it is necessary to return DBG_CONTINUE to avoid a deadlock.
        """
        print("callback_event_handler_access_violation ACCESS VIOLATION")
        return defines.DBG_CONTINUE

    @staticmethod
    def callback_event_handler_exit_process_debug(self):
        logging.info("Exit process debug handler EXIT_PROCESS_DEBUG_EVENT")
        return defines.DBG_EXCEPTION_NOT_HANDLED

    def set_handlers(self):
        # TODO: It would be neater and faster to override pydbg methods.
        self.set_callback(defines.CREATE_PROCESS_DEBUG_EVENT, self.callback_event_handler_create_process)
        self.set_callback(defines.LOAD_DLL_DEBUG_EVENT,       self.callback_event_handler_load_dll)
        self.set_callback(defines.EXCEPTION_ACCESS_VIOLATION, self.callback_event_handler_access_violation)
        #self.set_callback(defines.EXIT_PROCESS_DEBUG_EVENT,   self.callback_event_handler_exit_process_debug)

    def _hook_api_function(self, the_subclass, process_id):
        """This is called when looping on the list of semantically interesting functions."""
        logging.debug("subclass=%s process_id=%d" % (the_subclass.__name__, process_id))
        assert sorted(self.callbacks.keys()) == sorted([
            defines.CREATE_PROCESS_DEBUG_EVENT,
            defines.LOAD_DLL_DEBUG_EVENT,
            defines.EXCEPTION_ACCESS_VIOLATION,
            #defines.EXIT_PROCESS_DEBUG_EVENT,
		])

        the_subclass._parse_text_definition()

        dll_canonic_name = self.canonic_dll_name(the_subclass.dll_name)
        logging.debug("dll_canonic_name=%s" % dll_canonic_name)

        dll_address = self.find_dll_base_address(dll_canonic_name)

        # If the DLL is already loaded.
        if dll_address:
            logging.debug("DLL %s already loaded" % dll_canonic_name)
            self.add_one_function_from_dll_address(process_id, dll_address, the_subclass)
        else:
            logging.debug("self.pid=%d" % self.pid)
            self.hooks_by_processes[self.pid].unhooked_functions_by_dll[dll_canonic_name].append(the_subclass)

    def _hook_api_functions_list(self, process_id):
        for the_subclass in _functions_list:
            self._hook_api_function(the_subclass, process_id)

    def attach_to_pid(self, process_id):
        logging.debug("attach_to_pid process_id=%d" % process_id)
        self.set_handlers()
        logging.debug("before attach to process_id=%d" % process_id)
        self.attach(process_id)
        logging.debug("before hook api to process_id=%d" % process_id)
        self._hook_api_functions_list(process_id)
        self.run()

    def attach_to_command(self, command_line, callback_process_creation=None):
        """This receives a command line, starts the process in suspended mode,
        stores the desired breakpoints, in a map indexed by the DLL name, then resumes the process.
        When the DLLs are loaded, a callback sets their breakpoints. The callback is optional because of tests.
        """
        logging.info("attach_to_command command_line=%s" % command_line)

        start_info = win32process.STARTUPINFO()
        start_info.dwFlags = win32con.STARTF_USESHOWWINDOW

        hProcess, hThread, dwProcessId, dwThreadId = win32process.CreateProcess(
            None, command_line, None, None, False,
            win32con.CREATE_SUSPENDED, None,
            os.getcwd(), start_info)

        # This is used for clean process termination.
        self.create_process_handle = hProcess

        logging.info("Created dwProcessId=%d" % dwProcessId)
        if callback_process_creation:
            # This is needed to possibly inform a caller of the process id which is wrapped in the first element
            # stored in a queue, so we know the root process id.
            callback_process_creation(dwProcessId)

        if "DEBUG DEBUG":
            suspend_count = win32process.SuspendThread(hThread)
            if suspend_count != 1:
                raise Exception("Process %d: Invalid suspend count:%d" % (dwProcessId, suspend_count))
            resume_count = win32process.ResumeThread(hThread)
            if resume_count != 2:
                raise Exception("Process %d: Invalid resume count (a):%d" % (dwProcessId, resume_count))

        cim_objects_definitions.G_topProcessId = dwProcessId

        self.set_handlers()
        self.attach(dwProcessId)
        self._hook_api_functions_list(dwProcessId)

        resume_count = win32process.ResumeThread(hThread)
        # Value is two, if root process started from command line.
        if resume_count != 1 and resume_count != 2:
            raise Exception("Process %d: Invalid resume count:%d" % (dwProcessId, resume_count))
        self.run()
        return dwProcessId

################################################################################


class CallsCounterMeta(type):
    def __init__(cls, name, bases, dct):
        super(CallsCounterMeta, cls).__init__(name, bases, dct)
        #cls._cnt = cls.__name__ + "_SPECIFIC"
        cls._debug_counter_before = 0
        cls._debug_counter_after = 0


def hook_metaclass(meta, *bases):
    return meta("CallsCounterMetaGenerator", bases, {})


class Win32Hook_BaseClass(hook_metaclass(CallsCounterMeta)):
    """
    Each derived class must have:
    - The string api_definition="" which contains the signature of the Windows API
      function in Windows web site format.
    """

    # The style tells if this is a native call or an aggregate of function
    # calls, made with some style: Factorization etc...
    def __init__(self):
        self.m_core = None
        self.win32_hook_manager = None

    # Possible optimisation: If this function is not implemented,
    # no need to create a subclass instance.
    def callback_before(self, function_arguments):
        pass

    def callback_after(self, function_arguments, function_result):
        pass

    def cim_context(self):
        return cim_objects_definitions.ObjectsContext(self.win32_hook_manager.dbg.dwProcessId)

    def set_hook_manager(self, hook_manager):
        self.win32_hook_manager = hook_manager

    @classmethod
    def _split_into_return_arguments(cls):
        # This iterates over several possible syntax.
        match_one = None
        if not match_one:
            match_one = re.match(br"\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*\((.*)\)\s*;", cls.api_definition, re.DOTALL)
        if not match_one:
            # The return type could also be: "FILE *fopen("
            match_one = re.match(br"\s*([A-Za-z0-9_]+)\s*\*\s*([A-Za-z0-9_]+)\s*\((.*)\)\s*;", cls.api_definition, re.DOTALL)
        if not match_one:
            raise Exception("Cannot parse api definition:%s" % cls.api_definition)

        cls.return_type = match_one.group(1)
        cls.function_name = match_one.group(2)
        logging.debug("function_name=%s" % cls.function_name)

        return match_one.group(3).split(b",")

    @classmethod
    def _parse_text_definition(cls):
        """
        The API signature is taken "as is" from Microsoft web site.
        There are many functions and copying their signature is error-prone.
        Therefore, one just needs to copy-paste the web site text.
        """
        arguments_list = cls._split_into_return_arguments()

        cls.args_list = []
        for one_arg_pair in arguments_list:
            # It uses specific regular expressions for different arguments grammar.
            # This simplifies regular expressions testing and will help if specific processing is needed.
            # It is simplistic because there are not many cases.
            match_pair = None
            if not match_pair:
                match_pair = re.match(br"\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*", one_arg_pair)
            if not match_pair:
                # Maybe this is a pointer: "sockaddr *name" or "FILE** pFile"
                match_pair = re.match(br"\s*([A-Za-z0-9_]+\s*\*+)\s*([A-Za-z0-9_]+)\s*", one_arg_pair)
            if not match_pair:
                # Maybe this is a const pointer: "const sockaddr *name"
                match_pair = re.match(br"\s*(const\s+[A-Za-z0-9_]+\s*\*)\s+([A-Za-z0-9_]+)\s*", one_arg_pair)
            if not match_pair:
                # Maybe this is an array: "FILE_SEGMENT_ELEMENT [] aSegmentArray"
                match_pair = re.match(br"\s*([A-Za-z0-9_]+ +\[\])\s+([A-Za-z0-9_]+)\s*", one_arg_pair)
            if not match_pair:
                raise Exception("_parse_text_definition: %s Cannot match:%s" % (cls.function_name, one_arg_pair))

            cls.args_list.append((match_pair.group(1), match_pair.group(2)))

        logging.debug("args_list=%s" % cls.args_list)
        assert isinstance(cls.function_name, six.binary_type)

    def callback_create_object(self, cim_class_name, **cim_arguments):
        cim_objects_definitions.standardize_object_attributes(cim_class_name, cim_arguments)
        tracer_object.report_object_creation(self.cim_context(), cim_class_name, **cim_arguments)

    def callback_create_object_with_status(self, success_flag, cim_class_name, **cim_arguments):
        cim_objects_definitions.standardize_object_attributes(cim_class_name, cim_arguments)
        if False and not success_flag:
            # TODO: Maybe report the attempt to create a directory.
            calling_function_name = sys._getframe(1).f_code.co_name
            print("FAILED", calling_function_name, "cannot create", cim_class_name, str(**cim_arguments))
        tracer_object.report_object_creation(self.cim_context(), cim_class_name, **cim_arguments)


################################################################################

class Win32Hook_GenericProcessCreation(Win32Hook_BaseClass):
    """This is a base class for all functions which create a process."""

    # API functions which create process have a specific behaviour:
    # - They set the process as suspended.
    # - Wait until it is created.
    # - Once the subprocess is created, the necessary environment for hooking a process is re-created
    #   inside this function call which is then uniquely associated to a process.
    #   This data structure associated to a process also contains the hook logic to interrupt API functions calls.

    def callback_before(self, function_arguments):
        raise NotImplementedError("Win32Hook_GenericProcessCreation.callback_before")

    def callback_after(self, function_arguments, function_result):
        raise NotImplementedError("Win32Hook_GenericProcessCreation.callback_after")

    def callback_before_common(self, function_arguments):
        #print("callback_before_common self.win32_hook_manager.pid=", self.win32_hook_manager.pid)

        offset_flags=5
        dwCreationFlags = function_arguments[offset_flags]

        # This should be the case most of times,
        # because it is very rare that a user process starts in suspended state.
        self.process_is_already_suspended = dwCreationFlags & win32con.CREATE_SUSPENDED
        if self.process_is_already_suspended:
            raise Exception("Process already suspended. Not implemented.")

        # The primary thread of the new process is created in a suspended state,
        # and does not run until the ResumeThread function is called.
        # If the process is started with os.system, dwCreationFlags=win32con.EXTENDED_STARTUPINFO_PRESENT
        # If multiprocessing.Process, it is win32con.CREATE_UNICODE_ENVIRONMENT for Python 3, otherwise 0.
        try:
            # This value might not be defined.
            win32con.EXTENDED_STARTUPINFO_PRESENT
        except AttributeError:
            win32con.EXTENDED_STARTUPINFO_PRESENT = 0x80000

        # On Windows 10 in 64 bits, dwCreationFlags=x19e00080400 or x400 or x80000.
        # The lowest int is CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT
        # With Python 2.7, Windows 7, 64 bits, process started by Perl,
        # dwCreationFlags=000007fe00000000
        # Otherwise it can be 0 or EXTENDED_STARTUPINFO_PRESENT
        dwCreationFlagsSuspended = dwCreationFlags | win32con.CREATE_SUSPENDED

        self.win32_hook_manager.set_arg(offset_flags+1, dwCreationFlagsSuspended)
        #dwCreationFlagsAgain = self.win32_hook_manager.get_arg(offset_flags+1)
        #print("callback_before_common : CHECK dwCreationFlags=%0x" % dwCreationFlagsAgain)

    def callback_after_common(self, function_arguments, function_result):
        # typedef struct _PROCESS_INFORMATION {
        #   HANDLE hProcess;
        #   HANDLE hThread;
        #   DWORD  dwProcessId;
        #   DWORD  dwThreadId;
        # } PROCESS_INFORMATION, *PPROCESS_INFORMATION, *LPPROCESS_INFORMATION;

        #print("callback_after_common self.win32_hook_manager.pid=", self.win32_hook_manager.pid)

        offset_flags=5
        #dwCreationFlags = function_arguments[offset_flags]
        dwCreationFlags = self.win32_hook_manager.get_arg(offset_flags + 1)
        assert dwCreationFlags == self.win32_hook_manager.get_arg(offset_flags + 1)

        lpProcessInformation = function_arguments[9]

        hProcess = self.win32_hook_manager.get_pointer(lpProcessInformation)

        offset_hThread = windows_h.sizeof(windows_h.HANDLE)
        hThread = self.win32_hook_manager.get_pointer(lpProcessInformation + offset_hThread)

        offset_dwProcessId = windows_h.sizeof(windows_h.HANDLE) + windows_h.sizeof(windows_h.HANDLE)
        dwProcessId = self.win32_hook_manager.get_long(lpProcessInformation + offset_dwProcessId)

        offset_dwThreadId = windows_h.sizeof(windows_h.HANDLE) + windows_h.sizeof(windows_h.HANDLE) + windows_h.sizeof(windows_h.DWORD)
        dwThreadId = self.win32_hook_manager.get_long(lpProcessInformation + offset_dwThreadId)

        print("callback_after_common dwProcessId=%d dwThreadId=%d self.win32_hook_manager.pid=%d" % (
            dwProcessId, dwThreadId, self.win32_hook_manager.pid))

        if function_result == 0:
            print("callback_after_common FAILED")
            return

        self.callback_create_object("CIM_Process", Handle=dwProcessId)

        if self.process_is_already_suspended:
            raise Exception("Process was already suspended. NOT IMPLEMENTED YET.")

        if False:
            process_object = psutil.Process(dwProcessId)
            print("callback_after_common ppid=", process_object.ppid(),
                "dwProcessId=", dwProcessId,
                "self.win32_hook_manager.pid=", self.win32_hook_manager.pid,
                "self.win32_hook_manager.dbg.dwProcessId=", self.win32_hook_manager.dbg.dwProcessId)
            assert process_object.ppid() == self.win32_hook_manager.dbg.dwProcessId
            print("callback_after_common cmdline=", process_object.cmdline())


        self.win32_hook_manager.set_handlers()
        self.win32_hook_manager.debug_active_process(dwProcessId)

        current_process_id = self.win32_hook_manager.pid
        self.win32_hook_manager.switch_to_process(dwProcessId, "before hooking")
        self.win32_hook_manager._hook_api_functions_list(dwProcessId)
        self.win32_hook_manager.switch_to_process(current_process_id, "after hooking")

        resume_count = self.win32_hook_manager.resume_thread(dwThreadId)
        if resume_count != 2:
            raise Exception("Process %d: Invalid resume count:%d" % (dwProcessId, resume_count))
        resume_count = self.win32_hook_manager.resume_thread(dwThreadId)
        if resume_count != 1:
            raise Exception("Process %d: Invalid resume count:%d" % (dwProcessId, resume_count))
        print("callback_after_common AFTER Resuming thread OK:", dwThreadId)



################################################################################


class Win32Hook_CreateProcessA(Win32Hook_GenericProcessCreation):
    api_definition = b"""
        BOOL CreateProcessA(
            LPCSTR                lpApplicationName,
            LPSTR                 lpCommandLine,
            LPSECURITY_ATTRIBUTES lpProcessAttributes,
            LPSECURITY_ATTRIBUTES lpThreadAttributes,
            BOOL                  bInheritHandles,
            DWORD                 dwCreationFlags,
            LPVOID                lpEnvironment,
            LPCSTR                lpCurrentDirectory,
            LPSTARTUPINFOA        lpStartupInfo,
            LPPROCESS_INFORMATION lpProcessInformation
        );"""
    dll_name = b"KERNEL32.dll"

    def callback_before(self, function_arguments):
        lpApplicationName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
        print("Win32Hook_CreateProcessA lpApplicationName=", lpApplicationName)
        lpCurrentDirectory = self.win32_hook_manager.get_bytes_string(function_arguments[7])
        print("Win32Hook_CreateProcessA lpCurrentDirectory=", lpCurrentDirectory)
        self.callback_before_common(function_arguments)

    def callback_after(self, function_arguments, function_result):
        lpApplicationName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
        lpCommandLine = self.win32_hook_manager.get_bytes_string(function_arguments[1])
        self.callback_after_common(function_arguments, function_result)


class Win32Hook_CreateProcessW(Win32Hook_GenericProcessCreation):
    api_definition = b"""
        BOOL CreateProcessW(
            LPCWSTR               lpApplicationName,
            LPWSTR                lpCommandLine,
            LPSECURITY_ATTRIBUTES lpProcessAttributes,
            LPSECURITY_ATTRIBUTES lpThreadAttributes,
            BOOL                  bInheritHandles,
            DWORD                 dwCreationFlags,
            LPVOID                lpEnvironment,
            LPCWSTR               lpCurrentDirectory,
            LPSTARTUPINFOW        lpStartupInfo,
            LPPROCESS_INFORMATION lpProcessInformation
        );"""
    dll_name = b"KERNEL32.dll"

    def callback_before(self, function_arguments):
        lpApplicationName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
        lpCurrentDirectory = self.win32_hook_manager.get_unicode_string(function_arguments[7])
        self.callback_before_common(function_arguments)

    def callback_after(self, function_arguments, function_result):
        lpApplicationName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
        lp_command_line = self.win32_hook_manager.get_unicode_string(function_arguments[1])
        logging.info("lp_command_line=%s function_result=%s" % (lp_command_line, function_result))
        self.callback_after_common(function_arguments, function_result)


class Win32Hook_CreateDirectoryA(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL CreateDirectoryA(
            LPCWSTR               lpPathName,
            LPSECURITY_ATTRIBUTES lpSecurityAttributes
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpPathName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
        self.callback_create_object_with_status(function_result, "CIM_Directory", Name=lpPathName)


class Win32Hook_CreateDirectoryW(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL CreateDirectoryW(
            LPCWSTR               lpPathName,
            LPSECURITY_ATTRIBUTES lpSecurityAttributes
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpPathName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
        self.callback_create_object_with_status(function_result, "CIM_Directory", Name=lpPathName)


class Win32Hook_RemoveDirectoryA(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL RemoveDirectoryA(
            LPCSTR lpPathName
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpPathName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
        self.callback_create_object_with_status(function_result, "CIM_Directory", Name=lpPathName)


class Win32Hook_RemoveDirectoryW(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL RemoveDirectoryW(
            LPCWSTR lpPathName
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpPathName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
        self.callback_create_object_with_status(function_result, "CIM_Directory", Name=lpPathName)


class Win32Hook_CreateFileA(Win32Hook_BaseClass):
    api_definition = b"""
        HANDLE CreateFileA(
            LPCSTR                lpFileName,
            DWORD                 dwDesiredAccess,
            DWORD                 dwShareMode,
            LPSECURITY_ATTRIBUTES lpSecurityAttributes,
            DWORD                 dwCreationDisposition,
            DWORD                 dwFlagsAndAttributes,
            HANDLE                hTemplateFile
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpFileName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
        self.callback_create_object_with_status(function_result != defines.INVALID_HANDLE_VALUE, "CIM_DataFile", Name=lpFileName)


class Win32Hook_CreateFileW(Win32Hook_BaseClass):
    api_definition = b"""
        HANDLE CreateFileW(
            LPCWSTR               lpFileName,
            DWORD                 dwDesiredAccess,
            DWORD                 dwShareMode,
            LPSECURITY_ATTRIBUTES lpSecurityAttributes,
            DWORD                 dwCreationDisposition,
            DWORD                 dwFlagsAndAttributes,
            HANDLE                hTemplateFile
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
        self.callback_create_object_with_status(function_result != defines.INVALID_HANDLE_VALUE, "CIM_DataFile", Name=lpFileName)


class Win32Hook_DeleteFileA(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL DeleteFileA(
            LPCSTR lpFileName
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpFileName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
        self.callback_create_object_with_status(function_result, "CIM_DataFile", Name=lpFileName)


class Win32Hook_DeleteFileW(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL DeleteFileW(
            LPCWSTR lpFileName
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        lpFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
        self.callback_create_object_with_status(function_result, "CIM_DataFile", Name=lpFileName)


class Win32Hook_CreateThread(Win32Hook_BaseClass):
    api_definition = b"""
        HANDLE CreateThread(
            LPSECURITY_ATTRIBUTES   lpThreadAttributes,
            SIZE_T                  dwStackSize,
            LPTHREAD_START_ROUTINE  lpStartAddress,
            __drv_aliasesMem LPVOID lpParameter,
            DWORD                   dwCreationFlags,
            LPDWORD                 lpThreadId
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_CreateRemoteThread(Win32Hook_BaseClass):
    api_definition = b"""
        HANDLE CreateRemoteThread(
            HANDLE                 hProcess,
            LPSECURITY_ATTRIBUTES  lpThreadAttributes,
            SIZE_T                 dwStackSize,
            LPTHREAD_START_ROUTINE lpStartAddress,
            LPVOID                 lpParameter,
            DWORD                  dwCreationFlags,
            LPDWORD                lpThreadId
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_CreateRemoteThreadEx(Win32Hook_BaseClass):
    api_definition = b"""
        HANDLE CreateRemoteThreadEx(
            HANDLE                       hProcess,
            LPSECURITY_ATTRIBUTES        lpThreadAttributes,
            SIZE_T                       dwStackSize,
            LPTHREAD_START_ROUTINE       lpStartAddress,
            LPVOID                       lpParameter,
            DWORD                        dwCreationFlags,
            LPPROC_THREAD_ATTRIBUTE_LIST lpAttributeList,
            LPDWORD                      lpThreadId
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_TerminateProcess(Win32Hook_BaseClass):
    api_definition = b"""
            BOOL TerminateProcess(
                HANDLE hProcess,
                UINT   uExitCode
            );"""
    dll_name = b"KERNEL32.dll"
    def callback_before(self, function_arguments):
        terminated_process_handle = function_arguments[0]
        terminated_process_id = win32process.GetProcessId(terminated_process_handle)
        exit_code = function_arguments[1]
        print("Win32Hook_TerminateProcess terminated_process_id=", terminated_process_id, "exit_code=", exit_code)


class Win32Hook_TerminateThread(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL TerminateThread(
            HANDLE hThread,
            DWORD  dwExitCode
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_WriteFile(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL WriteFile(
            HANDLE       hFile,
            LPCVOID      lpBuffer,
            DWORD        nNumberOfBytesToWrite,
            LPDWORD      lpNumberOfBytesWritten,
            LPOVERLAPPED lpOverlapped
        );"""
    dll_name = b"KERNEL32.dll"
    def callback_after(self, function_arguments, function_result):
        logging.debug("Win32Hook_WriteFile args=%s" % function_arguments)

        lpBuffer = function_arguments[1]
        nNumberOfBytesToWrite = function_arguments[2]
        # logging.debug("lpBuffer=", lpBuffer, "nNumberOfBytesToWrite=", nNumberOfBytesToWrite)
        buffer = self.win32_hook_manager.get_bytes_size(lpBuffer, nNumberOfBytesToWrite)
        logging.debug("Buffer=%s" % buffer)


class Win32Hook_WriteFileEx(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL WriteFileEx(
            HANDLE                          hFile,
            LPCVOID                         lpBuffer,
            DWORD                           nNumberOfBytesToWrite,
            LPOVERLAPPED                    lpOverlapped,
            LPOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_WriteFileGather(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL WriteFileGather(
            HANDLE                  hFile,
            FILE_SEGMENT_ELEMENT [] aSegmentArray,
            DWORD                   nNumberOfBytesToWrite,
            LPDWORD                 lpReserved,
            LPOVERLAPPED            lpOverlapped
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_ReadFile(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL ReadFile(
            HANDLE       hFile,
            LPVOID       lpBuffer,
            DWORD        nNumberOfBytesToRead,
            LPDWORD      lpNumberOfBytesRead,
            LPOVERLAPPED lpOverlapped
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_ReadFileEx(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL ReadFileEx(
            HANDLE                          hFile,
            LPVOID                          lpBuffer,
            DWORD                           nNumberOfBytesToRead,
            LPOVERLAPPED                    lpOverlapped,
            LPOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
        );"""
    dll_name = b"KERNEL32.dll"


class Win32Hook_ReadFileScatter(Win32Hook_BaseClass):
    api_definition = b"""
        BOOL ReadFileScatter(
            HANDLE                  hFile,
            FILE_SEGMENT_ELEMENT [] aSegmentArray,
            DWORD                   nNumberOfBytesToRead,
            LPDWORD                 lpReserved,
            LPOVERLAPPED            lpOverlapped
        );"""
    dll_name = b"KERNEL32.dll"


def _sockaddr_to_addr_id(hook_base_class, sockaddr_address, sockaddr_size):
    sin_family_memory = hook_base_class.win32_hook_manager.read_process_memory(sockaddr_address, 2)
    print("sin_family_memory=", sin_family_memory, len(sin_family_memory))

    sin_family = struct.unpack("<H", sin_family_memory)[0]

    print("sin_family=", sin_family)
    print("size=", sockaddr_size)

    if sin_family == defines.AF_INET:
        # AF_INET = 2, if this is an IPV4 DNS server.
        # struct sockaddr_in {
        #         short   sin_family;
        #         u_short sin_port;
        #         struct  in_addr sin_addr;
        #         char    sin_zero[8];
        # };
        # struct in_addr {
        #   union {
        #     struct {
        #       u_char s_b1;
        #       u_char s_b2;
        #       u_char s_b3;
        #       u_char s_b4;
        #     } S_un_b;
        #     struct {
        #       u_short s_w1;
        #       u_short s_w2;
        #     } S_un_w;
        #     u_long S_addr;
        #   } S_un;
        # };
        ip_port_memory = hook_base_class.win32_hook_manager.read_process_memory(sockaddr_address + 2, 2)
        port_number = struct.unpack(">H", ip_port_memory)[0]

        assert sockaddr_size == 16

        s_addr_ipv4 = hook_base_class.win32_hook_manager.read_process_memory(sockaddr_address + 4, 4)
        if cim_objects_definitions.is_py3:
            addr_ipv4 = ".".join(["%d" % int(one_byte) for one_byte in s_addr_ipv4])
        else:
            addr_ipv4 = ".".join(["%d" % ord(one_byte) for one_byte in s_addr_ipv4])
        return "%s:%d" % (addr_ipv4, port_number)
    elif sin_family == defines.AF_INET6:
        # AF_INET6 = 23, if this is an IPV6 DNS server.
        # struct sockaddr_in6 {
        #      sa_family_t     sin6_family;   /* AF_INET6 */
        #      in_port_t       sin6_port;     /* port number */
        #      uint32_t        sin6_flowinfo; /* IPv6 flow information */
        #      struct in6_addr sin6_addr;     /* IPv6 address */
        #      uint32_t        sin6_scope_id; /* Scope ID (new in 2.4) */
        #  };
        #
        # struct in6_addr {
        #      unsigned char   s6_addr[16];   /* IPv6 address */
        # };
        ip_port_memory = hook_base_class.win32_hook_manager.read_process_memory(sockaddr_address + 2, 2)
        port_number = struct.unpack(">H", ip_port_memory)[0]

        assert sockaddr_size == 28

        s_addr_ipv6 = hook_base_class.win32_hook_manager.read_process_memory(sockaddr_address + 8, 16)
        if cim_objects_definitions.is_py3:
            addr_ipv6 = str(s_addr_ipv6)
        else:
            addr_ipv6 = "".join(["%02x" % ord(one_byte) for one_byte in s_addr_ipv6])

        return "%s:%d" % (addr_ipv6, port_number)
    else:
        raise Exception("Invalid sa_family:%d" % sin_family)


class Win32Hook_connect(Win32Hook_BaseClass):
    api_definition = b"""
        int connect(
            SOCKET         s,
            sockaddr_cptr  name,
            int            namelen
        );"""
    dll_name = b"ws2_32.dll"
    def callback_after(self, function_arguments, function_result):
        logging.debug("Win32Hook_connect function_arguments=", function_arguments)
        sockaddr_address = function_arguments[1]
        sockaddr_size = function_arguments[2]

        addr_id = _sockaddr_to_addr_id(self, sockaddr_address, sockaddr_size)
        self.callback_create_object("addr", Id=addr_id)


class Win32Hook_bind(Win32Hook_BaseClass):
    api_definition = b"""
        int bind(
            SOCKET         s,
            const sockaddr *name,
            int            namelen
        );"""
    dll_name = b"ws2_32.dll"
    def callback_after(self, function_arguments, function_result):
        logging.debug("Win32Hook_bind function_arguments=", function_arguments)
        sockaddr_address = function_arguments[1]
        sockaddr_size = function_arguments[2]

        addr_id = _sockaddr_to_addr_id(self, sockaddr_address, sockaddr_size)
        self.callback_create_object("addr", Id=addr_id)


class Win32Hook_SQLDataSources(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        SQLRETURN SQLDataSources(
            SQLHENV          EnvironmentHandle,  
            SQLUSMALLINT     Direction,  
            SQLCHAR *        ServerName,  
            SQLSMALLINT      BufferLength1,  
            SQLSMALLINT *    NameLength1Ptr,  
            SQLCHAR *        Description,  
            SQLSMALLINT      BufferLength2,  
            SQLSMALLINT *    NameLength2Ptr
        );"""
    dll_name = b"odbc32.dll"


class Win32Hook_fopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *fopen(
            const char *filename,
            const char *mode
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__wfopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *_wfopen(
            const wchar_t *filename,
            const wchar_t *mode
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook_fopen_s(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        errno_t fopen_s(
            FILE** pFile,
            const char *filename,
            const char *mode
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__wfopen_s(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        errno_t _wfopen_s(
            FILE** pFile,
            const wchar_t *filename,
            const wchar_t *mode
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__fsopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *_fsopen(
            const char *filename,
            const char *mode,
            int shflag);"""
    dll_name = b"msvcrt.dll"


class Win32Hook__wfsopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *_wfsopen(
            const wchar_t *filename,
            const wchar_t *mode,
            int shflag
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook_freopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *freopen(
            const char *path,
            const char *mode,
            FILE *stream
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__wfreopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *_wfreopen(
            const wchar_t *path,
            const wchar_t *mode,
            FILE *stream
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook_freopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        errno_t freopen(
            FILE** pFile,
            const char *path,
            const char *mode,
            FILE *stream
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__wfreopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        errno_t _wfreopen(
            FILE** pFile,
            const wchar_t *path,
            const wchar_t *mode,
            FILE *stream
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__fdopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *_fdopen(
            int fd,
            const char *mode
        );"""
    dll_name = b"msvcrt.dll"


class Win32Hook__wfdopen(Win32Hook_BaseClass):
    # TODO: Not implemented yet. Only detected.
    api_definition = b"""
        FILE *_wfdopen(
            int fd,
            const wchar_t *mode
        );"""
    dll_name = b"msvcrt.dll"


if False:
    class Win32Hook_ExitProcess(Win32Hook_BaseClass):
        # FIXME: Unexplained crash with the message:
        # python.exe - Entry Point Not Found
        # The procedure entry point <utf8>DLL.RtlExitUserProcess could not be located
        # in the dynamic link library API-MS-Win-Core-ProcessThreads-L1-1-0.dll.
        api_definition = b"""
            void ExitProcess(
                UINT uExitCode
            );"""
        dll_name = b"KERNEL32.dll"
        # TODO: Must find the data structure associated to its process at creation time.

# os.sys.getwindowsversion()
# LAPTOP-R89KG6V1 and other.
# sys.getwindowsversion(major=10, minor=0, build=18362, platform=2, service_pack='')
# BLT (Windows 7)
# sys.getwindowsversion() != (6, 1, 7601, 2, 'Service Pack 1')
# Travis
# Windows 10.0.17134 N/A Build 17134
is_windows10 = os.sys.getwindowsversion()[0] == 10


# Not validated yet.
if is_windows10:
    class Win32Hook_CopyFileA(Win32Hook_BaseClass):
        api_definition = b"""
            BOOL CopyFileA(
                LPCSTR  lpExistingFileName,
                LPCSTR  lpNewFileName,
                BOOL    bFailIfExists
              );"""
        dll_name = b"KERNEL32.dll"
        def callback_after(self, function_arguments, function_result):
            lpExistingFileName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
            lpNewFileName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
            self.callback_create_object("CIM_DataFile", Name=lpExistingFileName)
            self.callback_create_object("CIM_DataFile", Name=lpNewFileName)


    class Win32Hook_CopyFileExA(Win32Hook_BaseClass):
        api_definition = b"""
            BOOL CopyFileExA(
                LPCSTR             lpExistingFileName,
                LPCSTR             lpNewFileName,
                LPPROGRESS_ROUTINE lpProgressRoutine,
                LPVOID             lpData,
                LPBOOL             pbCancel,
                DWORD              dwCopyFlags
            );"""
        dll_name = b"KERNEL32.dll"
        def callback_after(self, function_arguments, function_result):
            lpExistingFileName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
            lpNewFileName = self.win32_hook_manager.get_bytes_string(function_arguments[0])
            self.callback_create_object("CIM_DataFile", Name=lpExistingFileName)
            self.callback_create_object("CIM_DataFile", Name=lpNewFileName)


    class Win32Hook_CopyFileExW(Win32Hook_BaseClass):
        api_definition = b"""
            BOOL CopyFileExW(
                LPCWSTR            lpExistingFileName,
                LPCWSTR            lpNewFileName,
                LPPROGRESS_ROUTINE lpProgressRoutine,
                LPVOID             lpData,
                LPBOOL             pbCancel,
                DWORD              dwCopyFlags
            );"""
        dll_name = b"KERNEL32.dll"
        def callback_after(self, function_arguments, function_result):
            lpExistingFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
            lpNewFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
            self.callback_create_object("CIM_DataFile", Name=lpExistingFileName)
            self.callback_create_object("CIM_DataFile", Name=lpNewFileName)


    class Win32Hook_CopyFileW(Win32Hook_BaseClass):
        api_definition = b"""
            BOOL CopyFileW(
                LPCWSTR  lpExistingFileName,
                LPCWSTR  lpNewFileName,
                BOOL    bFailIfExists
              );"""
        dll_name = b"KERNEL32.dll"
        def callback_after(self, function_arguments, function_result):
            lpExistingFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
            lpNewFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
            self.callback_create_object("CIM_DataFile", Name=lpExistingFileName)
            self.callback_create_object("CIM_DataFile", Name=lpNewFileName)


    # This blocks the process.
    #
    # class Win32Hook_CopyFile2(Win32Hook_BaseClass):
    #     api_definition = b"""
    #         BOOL CopyFile2(
    #             PCWSTR                        pwszExistingFileName,
    #             PCWSTR                        pwszNewFileName,
    #             COPYFILE2_EXTENDED_PARAMETERS *pExtendedParameters
    #             );"""
    #     dll_name = b"KERNEL32.dll"
    #     def callback_after(self, function_arguments, function_result):
    #         exit(0)
    #         pwszExistingFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
    #         pwszNewFileName = self.win32_hook_manager.get_unicode_string(function_arguments[0])
    #         self.callback_create_object("CIM_DataFile", Name=pwszExistingFileName)
    #         self.callback_create_object("CIM_DataFile", Name=pwszNewFileName)
    #
    # CopyFileTransactedA
    # CopyFileTransactedW
    # CopyLZFile


    class Win32Hook_CreateProcessAsUserA(Win32Hook_GenericProcessCreation):
        api_definition = b"""
            BOOL CreateProcessAsUserA(
                HANDLE                hToken,
                LPCSTR                lpApplicationName,
                LPSTR                 lpCommandLine,
                LPSECURITY_ATTRIBUTES lpProcessAttributes,
                LPSECURITY_ATTRIBUTES lpThreadAttributes,
                BOOL                  bInheritHandles,
                DWORD                 dwCreationFlags,
                LPVOID                lpEnvironment,
                LPCSTR                lpCurrentDirectory,
                LPSTARTUPINFOA        lpStartupInfo,
                LPPROCESS_INFORMATION lpProcessInformation
            );"""
        dll_name = b"KERNEL32.dll"


    class Win32Hook_CreateProcessAsUserW(Win32Hook_GenericProcessCreation):
        api_definition = b"""
            BOOL CreateProcessAsUserW(
                HANDLE                hToken,
                LPCWSTR               lpApplicationName,
                LPWSTR                lpCommandLine,
                LPSECURITY_ATTRIBUTES lpProcessAttributes,
                LPSECURITY_ATTRIBUTES lpThreadAttributes,
                BOOL                  bInheritHandles,
                DWORD                 dwCreationFlags,
                LPVOID                lpEnvironment,
                LPCWSTR               lpCurrentDirectory,
                LPSTARTUPINFOW        lpStartupInfo,
                LPPROCESS_INFORMATION lpProcessInformation
            );"""
        dll_name = b"KERNEL32.dll"


    class Win32Hook_CreateFile2(Win32Hook_BaseClass):
        api_definition = b"""
            HANDLE CreateFile2(
                LPCWSTR                           lpFileName,
                DWORD                             dwDesiredAccess,
                DWORD                             dwShareMode,
                DWORD                             dwCreationDisposition,
                LPCREATEFILE2_EXTENDED_PARAMETERS pCreateExParams
            );"""
        dll_name = b"KERNEL32.dll"


################################################################################

# This returns only leaf classes.
_functions_list = cim_objects_definitions.leaf_derived_classes(Win32Hook_BaseClass)

##### Kernel32.dll
# Many functions are very specific to old-style Windows applications.
# Still, this is the only way to track specific behaviour.
# Which function for opening files, is called by the Python interpreter on Travis ?
#
# CreateHardLink A/W/TransactedA/TransactedW
# CreateNamedPipe A/W

# LoadLibrary

# MapViewOfIle ?

# MoveFile ...

# OpenFile, OpenFileById
# ReOpenFile

# ReplaceFile, A, W

# OpenJobObjects

##### KernelBase.dll
# Looks like a subset of Kernel32.dll

##### ntdll.dll
# NtOpenFile
# NtOpenDirectoryObject ?


