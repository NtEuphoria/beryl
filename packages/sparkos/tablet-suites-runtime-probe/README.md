# Trusted tablet suite identity probe

This experiment adds a compiled literal identity response to a fresh copy of the
preserved tablet suite candidate. It is used only by
`scripts/verify-tablet-existing-suites.py` and the owned Workbench transport.

The source fingerprint identifies the preceding 86-file source manifest; the new
87-file manifest separately includes this rendered identity source. A fresh
per-job token prevents another compiled session from satisfying that identity.

The probe opens no world, enters no play mode, spawns no entity and invokes no
tablet lifecycle method. Passing the five existing suites establishes their
source-defined responses only. Native callbacks, physical input, queued work,
service lifetime, multiplayer and visual acceptance remain separate gates.

See `docs/advanced/P5_TABLET_EXISTING_SUITES.md` for evidence and boundaries.
