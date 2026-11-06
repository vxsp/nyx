"""Owned check processes; Windows jobs contain children before user code starts.

This controls process lifetime, not filesystem/network privileges or hostile code.
Only trusted, explicitly requested check commands belong here.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import time


if os.name == "nt":
    import ctypes as c
    from ctypes import wintypes as w
    import msvcrt

    SIZE_T = c.c_size_t
    ULONG_PTR = c.c_size_t

    class SECURITY_ATTRIBUTES(c.Structure):
        _fields_ = [("nLength", w.DWORD), ("lpSecurityDescriptor", w.LPVOID), ("bInheritHandle", w.BOOL)]

    class STARTUPINFOW(c.Structure):
        _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
                    ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
                    ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                    ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                    ("lpReserved2", c.POINTER(w.BYTE)), ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]

    class STARTUPINFOEXW(c.Structure):
        _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", w.LPVOID)]

    class PROCESS_INFORMATION(c.Structure):
        _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]

    class BASIC_LIMITS(c.Structure):
        _fields_ = [("PerProcessUserTimeLimit", c.c_longlong), ("PerJobUserTimeLimit", c.c_longlong),
                    ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", SIZE_T), ("MaximumWorkingSetSize", SIZE_T),
                    ("ActiveProcessLimit", w.DWORD), ("Affinity", ULONG_PTR), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

    class IO_COUNTERS(c.Structure):
        _fields_ = [(name, c.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class EXTENDED_LIMITS(c.Structure):
        _fields_ = [("BasicLimitInformation", BASIC_LIMITS), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", SIZE_T), ("JobMemoryLimit", SIZE_T), ("PeakProcessMemoryUsed", SIZE_T), ("PeakJobMemoryUsed", SIZE_T)]

    class ACCOUNTING(c.Structure):
        _fields_ = [("TotalUserTime", c.c_longlong), ("TotalKernelTime", c.c_longlong),
                    ("ThisPeriodTotalUserTime", c.c_longlong), ("ThisPeriodTotalKernelTime", c.c_longlong),
                    ("TotalPageFaultCount", w.DWORD), ("TotalProcesses", w.DWORD),
                    ("ActiveProcesses", w.DWORD), ("TotalTerminatedProcesses", w.DWORD)]

    kernel = c.WinDLL("kernel32", use_last_error=True)

    def _api(name, result, arguments):
        function = getattr(kernel, name)
        function.restype, function.argtypes = result, arguments
        return function

    CreateJobObject = _api("CreateJobObjectW", w.HANDLE, [w.LPVOID, w.LPCWSTR])
    SetJobInformation = _api("SetInformationJobObject", w.BOOL, [w.HANDLE, c.c_int, w.LPVOID, w.DWORD])
    QueryJobInformation = _api("QueryInformationJobObject", w.BOOL, [w.HANDLE, c.c_int, w.LPVOID, w.DWORD, w.LPVOID])
    TerminateJob = _api("TerminateJobObject", w.BOOL, [w.HANDLE, w.UINT])
    CloseHandle = _api("CloseHandle", w.BOOL, [w.HANDLE])
    GetCurrentProcess = _api("GetCurrentProcess", w.HANDLE, [])
    DuplicateHandle = _api("DuplicateHandle", w.BOOL, [w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD])
    CreateFile = _api("CreateFileW", w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(SECURITY_ATTRIBUTES), w.DWORD, w.DWORD, w.HANDLE])
    InitializeAttributes = _api("InitializeProcThreadAttributeList", w.BOOL, [w.LPVOID, w.DWORD, w.DWORD, c.POINTER(SIZE_T)])
    UpdateAttribute = _api("UpdateProcThreadAttribute", w.BOOL, [w.LPVOID, w.DWORD, SIZE_T, w.LPVOID, SIZE_T, w.LPVOID, w.LPVOID])
    DeleteAttributes = _api("DeleteProcThreadAttributeList", None, [w.LPVOID])
    CreateProcess = _api("CreateProcessW", w.BOOL, [w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL, w.DWORD,
                                                 w.LPVOID, w.LPCWSTR, c.POINTER(STARTUPINFOEXW), c.POINTER(PROCESS_INFORMATION)])
    WaitForSingleObject = _api("WaitForSingleObject", w.DWORD, [w.HANDLE, w.DWORD])
    GetExitCode = _api("GetExitCodeProcess", w.BOOL, [w.HANDLE, c.POINTER(w.DWORD)])

    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x20002
    PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x2000D
    EXTENDED_STARTUPINFO_PRESENT = 0x80000
    CREATE_UNICODE_ENVIRONMENT = 0x400
    STARTF_USESTDHANDLES = 0x100

    def _checked(result):
        if not result:
            raise c.WinError(c.get_last_error())
        return result

    class WindowsJobProcess:
        def __init__(self, command: list[str], cwd: Path, output, environment: dict[str, str]):
            self.command = command
            self._process = self._job = None
            self._returncode = None
            executable = shutil.which(command[0], path=environment.get("PATH"))
            if not executable or Path(executable).suffix.lower() in (".bat", ".cmd"):
                raise OSError("Check runner must resolve to a native executable")
            self._job = _checked(CreateJobObject(None, None))
            attributes = None
            attributes_initialized = False
            inherited_output, null_input = w.HANDLE(), None
            try:
                limits = EXTENDED_LIMITS()
                limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                _checked(SetJobInformation(self._job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, c.byref(limits), c.sizeof(limits)))
                owner = GetCurrentProcess()
                _checked(DuplicateHandle(owner, msvcrt.get_osfhandle(output.fileno()), owner,
                                         c.byref(inherited_output), 0, True, 2))  # DUPLICATE_SAME_ACCESS
                security = SECURITY_ATTRIBUTES(c.sizeof(SECURITY_ATTRIBUTES), None, True)
                null_input = CreateFile("NUL", 0x80000000, 3, c.byref(security), 3, 0x80, None)
                if null_input == c.c_void_p(-1).value:
                    null_input = None
                    raise c.WinError(c.get_last_error())
                _checked(null_input)
                size = SIZE_T()
                InitializeAttributes(None, 2, 0, c.byref(size))  # First call determines required storage.
                if not size.value:
                    raise c.WinError(c.get_last_error())
                attributes = c.create_string_buffer(size.value)
                _checked(InitializeAttributes(attributes, 2, 0, c.byref(size)))
                attributes_initialized = True
                handles = (w.HANDLE * 2)(null_input, inherited_output.value)
                jobs = (w.HANDLE * 1)(self._job)
                _checked(UpdateAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, handles, c.sizeof(handles), None, None))
                _checked(UpdateAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs, c.sizeof(jobs), None, None))
                startup = STARTUPINFOEXW()
                startup.StartupInfo.cb = c.sizeof(startup)
                startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
                startup.StartupInfo.hStdInput = null_input
                startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = inherited_output.value
                startup.lpAttributeList = c.cast(attributes, w.LPVOID)
                info = PROCESS_INFORMATION()
                arguments = c.create_unicode_buffer(subprocess.list2cmdline([executable, *command[1:]]))
                block = c.create_unicode_buffer("\0".join(f"{key}={environment[key]}" for key in sorted(environment, key=str.upper)) + "\0\0")
                flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | subprocess.CREATE_NO_WINDOW
                _checked(CreateProcess(executable, arguments, None, None, True, flags, block, str(cwd), c.byref(startup), c.byref(info)))
                self._process, self.pid = info.hProcess, info.dwProcessId
                CloseHandle(info.hThread)
            except BaseException:
                self.close()
                raise
            finally:
                if attributes_initialized:
                    DeleteAttributes(attributes)
                if inherited_output.value:
                    CloseHandle(inherited_output)
                if null_input:
                    CloseHandle(null_input)

        def poll(self):
            if self._returncode is not None:
                return self._returncode
            status = WaitForSingleObject(self._process, 0)
            if status == 0xFFFFFFFF:
                raise c.WinError(c.get_last_error())
            if status == 0:
                code = w.DWORD()
                _checked(GetExitCode(self._process, c.byref(code)))
                self._returncode = code.value
            return self._returncode

        def wait(self, timeout=None):
            milliseconds = 0xFFFFFFFF if timeout is None else min(0xFFFFFFFE, max(0, int(timeout * 1000)))
            status = WaitForSingleObject(self._process, milliseconds)
            if status == 258:
                raise subprocess.TimeoutExpired(self.command, timeout)
            if status == 0xFFFFFFFF:
                raise c.WinError(c.get_last_error())
            return self.poll()

        def kill(self):
            _checked(TerminateJob(self._job, 1))

        def close(self):
            if not self._job:
                return
            try:
                self.kill()
                if self._process:
                    self.wait(timeout=5)
                deadline = time.monotonic() + 5
                accounting = ACCOUNTING()
                while True:
                    _checked(QueryJobInformation(self._job, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
                                                 c.byref(accounting), c.sizeof(accounting), None))
                    if not accounting.ActiveProcesses:
                        break
                    if time.monotonic() >= deadline:
                        raise OSError("Contained check processes did not finish")
                    time.sleep(0.01)
            finally:
                if self._process:
                    CloseHandle(self._process)
                    self._process = None
                CloseHandle(self._job)
                self._job = None


@contextmanager
def launch_check(command: list[str], cwd: Path, output, environment: dict[str, str]):
    """Fail closed if Windows containment cannot be established; never run a fallback."""
    if os.name == "nt":
        process = WindowsJobProcess(command, cwd, output, environment)
        try:
            yield process
        finally:
            process.close()
    else:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, env=environment, start_new_session=True)
        try:
            yield process
        finally:
            if process.poll() is None:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
