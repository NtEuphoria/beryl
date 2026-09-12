"""Ownership of child process trees; no shell execution or global process matching."""
import os
import signal
import subprocess


class ProcessJob:
    # Popen closes CreateProcessW's primary-thread handle. attach() obtains a
    # handle to the only thread of this still-suspended process through the
    # documented Toolhelp/OpenThread APIs, assigns the job, then resumes it.
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | 0x00000004) if os.name == "nt" else 0

    def __enter__(self):
        self.handle = None
        self.process = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes as w
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            self.api.CreateJobObjectW.argtypes = (ctypes.c_void_p, w.LPCWSTR)
            self.api.CreateJobObjectW.restype = w.HANDLE
            self.api.AssignProcessToJobObject.argtypes = (w.HANDLE, w.HANDLE)
            self.api.AssignProcessToJobObject.restype = w.BOOL
            self.api.TerminateJobObject.argtypes = (w.HANDLE, w.UINT)
            self.api.TerminateJobObject.restype = w.BOOL
            self.api.CloseHandle.argtypes = (w.HANDLE,)
            self.api.CloseHandle.restype = w.BOOL
            self.api.SetInformationJobObject.argtypes = (w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD)
            self.api.SetInformationJobObject.restype = w.BOOL
            self.api.CreateToolhelp32Snapshot.argtypes = (w.DWORD, w.DWORD)
            self.api.CreateToolhelp32Snapshot.restype = w.HANDLE
            self.api.OpenThread.argtypes = (w.DWORD, w.BOOL, w.DWORD)
            self.api.OpenThread.restype = w.HANDLE
            self.api.GetProcessIdOfThread.argtypes = (w.HANDLE,)
            self.api.GetProcessIdOfThread.restype = w.DWORD
            self.api.ResumeThread.argtypes = (w.HANDLE,)
            self.api.ResumeThread.restype = w.DWORD

            class BasicLimits(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD),
                            ("SchedulingClass", w.DWORD)]

            class IoCounters(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in
                            ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                             "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

            class ExtendedLimits(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            self.handle = self.api.CreateJobObjectW(None, None)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                error = ctypes.WinError(ctypes.get_last_error())
                self.api.CloseHandle(self.handle)
                self.handle = None
                raise error
        return self

    def _resume_primary(self, process):
        import ctypes
        from ctypes import wintypes as w

        class ThreadEntry(ctypes.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ThreadID", w.DWORD),
                        ("th32OwnerProcessID", w.DWORD), ("tpBasePri", w.LONG),
                        ("tpDeltaPri", w.LONG), ("dwFlags", w.DWORD)]

        self.api.Thread32First.argtypes = (w.HANDLE, ctypes.POINTER(ThreadEntry))
        self.api.Thread32First.restype = w.BOOL
        self.api.Thread32Next.argtypes = (w.HANDLE, ctypes.POINTER(ThreadEntry))
        self.api.Thread32Next.restype = w.BOOL
        snapshot = self.api.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        found = []
        try:
            entry = ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            present = self.api.Thread32First(snapshot, ctypes.byref(entry))
            count = 0
            while present:
                count += 1
                if count > 262144:
                    raise OSError("owned-process thread snapshot exceeds admitted limit")
                if entry.th32OwnerProcessID == process.pid:
                    found.append(entry.th32ThreadID)
                    if len(found) > 1:
                        raise OSError("suspended owned process has more than one thread; refusing ambiguous resume")
                entry.dwSize = ctypes.sizeof(entry)
                present = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            error = ctypes.get_last_error()
            if error != 18:  # ERROR_NO_MORE_FILES
                raise ctypes.WinError(error)
        finally:
            self.api.CloseHandle(snapshot)
        if len(found) != 1:
            raise OSError("cannot identify the primary thread of the suspended owned process")
        # Exact-owner check closes thread-ID reuse between enumeration and open.
        thread = self.api.OpenThread(0x0002 | 0x0800, False, found[0])
        if not thread:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            owner = self.api.GetProcessIdOfThread(thread)
            if not owner:
                raise ctypes.WinError(ctypes.get_last_error())
            if owner != process.pid:
                raise OSError("primary-thread identity changed before resume")
            prior = self.api.ResumeThread(thread)
            if prior == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            if prior != 1:
                raise OSError("unexpected primary-thread suspend count; refusing further resumes")
        finally:
            self.api.CloseHandle(thread)

    def attach(self, process):
        if self.process is not None:
            raise OSError("a ProcessJob owns one direct child")
        self.process = process
        if self.handle:
            try:
                if process.poll() is not None:
                    raise OSError("owned child exited before job assignment")
                if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
                    import ctypes
                    raise ctypes.WinError(ctypes.get_last_error())
                self._resume_primary(process)
            except BaseException:
                # Assignment can fail before this process belongs to the job.
                # Always terminate our exact child; closing the configured job
                # also terminates any descendants created after a failed resume.
                process.kill()
                process.wait(timeout=10)
                raise

    def stop(self, process):
        if self.handle:
            if not self.api.TerminateJobObject(self.handle, 2):
                import ctypes
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=10)

    def __exit__(self, *args):
        if self.handle:
            # Also terminate descendants surviving the process we directly waited for.
            # Kill-on-close additionally covers abrupt death of this Python host.
            import ctypes
            error = None
            if not self.api.TerminateJobObject(self.handle, 2):
                error = ctypes.WinError(ctypes.get_last_error())
            if not self.api.CloseHandle(self.handle) and error is None:
                error = ctypes.WinError(ctypes.get_last_error())
            self.handle = None
            if error is not None and not any(args):
                raise error
