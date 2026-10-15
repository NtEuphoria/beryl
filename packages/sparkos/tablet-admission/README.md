# Tablet signature-admission fixture

This contains a public plain state record and three empty callback functions for
the bounded companion v2 admission profile. It is not a tablet implementation,
a MESH candidate or engine validation evidence. The experimental P4-B renderer
can now generate scalar ScriptComponent wrappers for this fixture; it does not
implement the real tablet's services or lifecycle.

The fixture lets the shared CLI/MCP workflow check exact declarations, parameter
modes, component base names and source-reviewed superclass order. Passing those
checks does not verify handler behavior, lifecycle, authority or retention.

Eligible v2 `mod build` now produces an immutable source candidate. Engine
verification and promotion remain unavailable until their separate gates pass.
The real tablet
baseline and required service traces are recorded in
`docs/advanced/P4_TABLET_RECOVERY_2026_10_08.md`.
