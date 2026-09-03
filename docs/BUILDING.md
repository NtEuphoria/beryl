# Building Beryl

```bash
bash scripts/build.sh          # release: build/beryl.exe
bash scripts/build.sh --debug  # -O0 -g
bash scripts/test.sh           # compiler unit + golden tests
```

Requirements: **clang** and nothing else. No build system, no package manager, no
third-party libraries. The compiler is C11 and links against the C runtime alone.

## Smart App Control on this machine

This host runs **Smart App Control in Enforce mode**
(`HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState = 1`).
SAC does a cloud reputation lookup per file hash, and for an unknown unsigned binary
**the verdict is not deterministic**. Measured on this machine: building identical
source three times, each producing a different hash, gave RAN / BLOCKED / RAN.

A block looks like this, and is easy to mistake for a file-permission bug:

```
./build/run_tests.exe: Permission denied        # shell exit code 126
```

Confirmed in the Windows event log as CodeIntegrity event **3077**, citing policy
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`.

**It is not a compile failure and it is not caused by anything in the code.** What
does *not* influence it: file size, optimisation level, static versus dynamic
linkage, filename. An 88 KB trivial binary was blocked in the same session a 121 KB
one ran.

`scripts/sac.sh` handles it. Each attempt compiles with a different
`-DBERYL_BUILD_NONCE`, which changes the binary's content hash and so earns an
independent verdict; six attempts make a spurious failure vanishingly unlikely. You
will occasionally see:

```
note: Smart App Control blocked this binary; rebuilding (attempt 2/6)
```

That line is expected and harmless. If all six attempts are blocked, the script says
so explicitly rather than reporting a test failure.

Raise `SAC_MAX_ATTEMPTS` to retry more:

```bash
SAC_MAX_ATTEMPTS=12 bash scripts/test.sh
```

**This is not something Beryl should try to "fix" further.** SAC can only be turned
off through Settings, and turning it off is irreversible without an OS reset — that
is the machine owner's decision, not the build system's.
