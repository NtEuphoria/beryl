"""Inert regressions for primary outcomes surviving failed owned cleanup."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/beryl-mod'))
import mod
from process_job import ProcessJob

EXPECTED_IDS = (
    'attach.primary-survives-kill-and-wait-failure', 'stop.request-failure-confirmed-wait',
    'stop.request-and-wait-failure', 'close.double-failure-with-primary', 'close.double-failure-without-primary',
    'timeout.secondary-timeout', 'timeout.secondary-stop-failure', 'cancel.secondary-stop-failure',
    'timeout.confirmed-cleanup', 'cancel.confirmed-cleanup', 'return.cleanup-failure-is-unavailable',
    'return.success-no-cleanup-error', 'startup.no-process-or-exit-invented',
)


def main():
    work = Path(tempfile.mkdtemp(prefix='process-cleanup-faults-', dir=ROOT / 'build'))
    cases = []

    def check(name, action):
        try:
            action()
            cases.append({'id': name, 'status': 'success'})
        except BaseException as exc:
            cases.append({'id': name, 'status': 'failure', 'type': type(exc).__name__, 'message': str(exc)})

    def require(value, message):
        if not value:
            raise AssertionError(message)

    def attach_fault():
        primary = OSError('deliberate primary resume failure')
        owner = ProcessJob()
        owner.process = None; owner.handle = 1; owner.cleanup_errors = []
        owner.api = type('API', (), {'AssignProcessToJobObject': lambda *args: True})()
        owner._resume_primary = lambda process: (_ for _ in ()).throw(primary)
        class Child:
            pid = 321; _handle = 123
            def poll(self): return None
            def kill(self): raise OSError('deliberate stop request failure')
            def wait(self, timeout):
                require(timeout == 10, 'cleanup wait was not bounded')
                raise subprocess.TimeoutExpired('fixture', timeout)
        try:
            owner.attach(Child())
        except OSError as exc:
            require(exc is primary, 'cleanup replaced primary attach error')
        else:
            raise AssertionError('attach incorrectly passed')
        require([item['stage'] for item in owner.cleanup_errors] == ['attach.kill', 'attach.wait'], 'secondary errors missing')

    check('attach.primary-survives-kill-and-wait-failure', attach_fault)

    def owner_fault(wait_fails, closing=False, primary=False):
        owner = ProcessJob(); owner.handle = 1; owner.cleanup_errors = []
        # No native API is called; even WinError construction is mocked so this
        # regression is usable on POSIX as well as Windows.
        owner.api = type('API', (), {'TerminateJobObject': lambda *args: False,
                                    'CloseHandle': lambda *args: False})()
        class Child:
            def wait(self, timeout):
                require(timeout == 10, 'secondary wait was not bounded')
                if wait_fails: raise subprocess.TimeoutExpired('fixture', timeout)
                return 2
        with patch('ctypes.WinError', create=True, side_effect=lambda *args: OSError('deliberate native request failure')), \
             patch('ctypes.get_last_error', create=True, return_value=5):
            try:
                if closing:
                    owner.__exit__(OSError if primary else None, OSError('primary') if primary else None, None)
                else:
                    owner.stop(Child())
            except OSError as exc:
                require(not primary and 'native request' in str(exc), 'secondary error replaced an in-flight primary')
            else:
                require(primary, 'cleanup failure incorrectly passed')
        expected = ['close.request', 'close.handle'] if closing else ['stop.request'] + (['stop.wait'] if wait_fails else [])
        require([item['stage'] for item in owner.cleanup_errors] == expected, 'owner cleanup faults missing')
        if closing: require(owner.handle is None, 'closed handle not retired')

    check('stop.request-failure-confirmed-wait', lambda: owner_fault(False))
    check('stop.request-and-wait-failure', lambda: owner_fault(True))
    check('close.double-failure-with-primary', lambda: owner_fault(False, True, True))
    check('close.double-failure-without-primary', lambda: owner_fault(False, True, False))

    def run_case(primary, cleanup, expected, exit_code=None):
        job = object.__new__(mod.Job)
        job.path = work / ('job-' + str(len(cases))); job.path.mkdir()
        job.input_hashes = None; job.result = {'raw_logs': []}
        class Child:
            pid = 654; returncode = exit_code if primary is None else None
            def wait(self, timeout):
                require(timeout == 3, 'primary wait budget changed')
                if primary is not None: raise primary
                return exit_code
        class Owner:
            flags = 0
            def __init__(self): self.cleanup_errors = []
            def __enter__(self): return self
            def attach(self, child): pass
            def stop(self, child):
                if cleanup is not None:
                    self.cleanup_errors.append({'stage': 'stop.wait', 'type': type(cleanup).__name__, 'message': str(cleanup)})
                    raise cleanup
                child.returncode = exit_code
            def __exit__(self, *args):
                if primary is None and cleanup is not None:
                    self.cleanup_errors.append({'stage': 'close.request', 'type': type(cleanup).__name__, 'message': str(cleanup)})
                    raise cleanup
        with patch('process_job.ProcessJob', Owner), patch.object(mod.subprocess, 'Popen', return_value=Child()):
            try:
                job.run(['fixed-fixture'], 'inert', work, timeout=3)
            except mod.Failure as exc:
                require(exc.status == expected, 'primary status was replaced: ' + exc.status)
            else:
                require(expected == 'success', 'failed operation incorrectly passed')
        record = job.result['raw_logs'][0]
        require(record['status'] == ('exited' if primary is None else expected), 'raw primary outcome missing')
        require(record['process_id'] == 654 and record['exit_confirmed'] == (exit_code is not None), 'exit identity/confirmation incorrect')
        require(bool(record['cleanup_errors']) == (cleanup is not None), 'cleanup evidence missing or invented')
        require(type(record['seconds']) is float and record['seconds'] >= 0, 'elapsed evidence missing')

    check('timeout.secondary-timeout', lambda: run_case(subprocess.TimeoutExpired('fixture', 3), subprocess.TimeoutExpired('fixture', 10), 'timeout'))
    check('timeout.secondary-stop-failure', lambda: run_case(subprocess.TimeoutExpired('fixture', 3), OSError('stop failed'), 'timeout'))
    check('cancel.secondary-stop-failure', lambda: run_case(KeyboardInterrupt(), OSError('stop failed'), 'cancelled'))
    check('timeout.confirmed-cleanup', lambda: run_case(subprocess.TimeoutExpired('fixture', 3), None, 'timeout', 2))
    check('cancel.confirmed-cleanup', lambda: run_case(KeyboardInterrupt(), None, 'cancelled', 2))
    check('return.cleanup-failure-is-unavailable', lambda: run_case(None, OSError('close failed'), 'unavailable', 0))
    check('return.success-no-cleanup-error', lambda: run_case(None, None, 'success', 0))

    def startup_fault():
        job = object.__new__(mod.Job); job.path = work / 'startup'; job.path.mkdir()
        job.input_hashes = None; job.result = {'raw_logs': []}
        class Owner:
            flags = 0
            def __enter__(self): self.cleanup_errors = []; return self
            def __exit__(self, *args): pass
        with patch('process_job.ProcessJob', Owner), patch.object(mod.subprocess, 'Popen', side_effect=OSError('startup denied')):
            try: job.run(['fixed-fixture'], 'inert', work, timeout=3)
            except mod.Failure as exc: require(exc.status == 'unavailable', 'startup status changed')
            else: raise AssertionError('startup incorrectly passed')
        record = job.result['raw_logs'][0]
        require(record['status'] == 'startup_failure' and not record['exit_confirmed'], 'startup fabricated exit')
        require('process_id' not in record and record['cleanup_errors'] == [], 'startup fabricated process')

    check('startup.no-process-or-exit-invented', startup_fault)
    sources = {}
    for path in (Path(__file__), ROOT / 'tools/beryl-mod/process_job.py', ROOT / 'tools/beryl-mod/mod.py'):
        data = path.read_bytes(); sources[str(path.resolve())] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    complete = [item['id'] for item in cases] == list(EXPECTED_IDS)
    result = {'schema_version': 1, 'operation': 'verify.process_cleanup', 'status': 'success' if complete and all(item['status'] == 'success' for item in cases) else 'failure',
              'scope': 'mocked process/API failures; no shell, compiler, editor, process start or stop', 'sources': sources,
              'expected_case_ids': list(EXPECTED_IDS), 'cases_complete': complete, 'cases': cases, 'case_count': len(cases)}
    output = work / 'result.json'; output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(output), **result}))
    return 0 if result['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
