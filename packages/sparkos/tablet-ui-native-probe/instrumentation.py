"""Reversible N1b/N3 call-through overlays; no service/compiler/engine execution."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import hashlib
from pathlib import Path

ADAPTER_SHA256 = "21479adf12a76a48ad7be9419e6e5047d663cce0ebee1341e5d8bfaf8d20d3c7"
UI_SHA256 = "4efeab8cce793939d748506f34691aae9b0b47aa8b32ed568ece05accf28a05d"
MAX_BYTES = 128 * 1024


class InstrumentationFailure(ValueError):
    pass


def require(condition, detail):
    if not condition:
        raise InstrumentationFailure(detail)


def checked(data, digest):
    require(type(data) is bytes and 0 < len(data) <= MAX_BYTES, "Bounded literal source bytes required")
    require(hashlib.sha256(data).hexdigest() == digest, "Stale original source revision")
    require(b"\0" not in data, "NUL source rejected")
    try:
        return data.decode("utf8")
    except UnicodeError as exc:
        raise InstrumentationFailure("Invalid UTF-8 source") from exc


def replace_once(text, old, new):
    require(text.count(old) == 1, "Overlay selection must identify one exact original block")
    return text.replace(old, new, 1)


def method_span(text, declaration):
    start = text.find(declaration)
    require(start >= 0 and text.count(declaration) == 1, "UI declaration must be exact and unique")
    opening = text.find("{", start)
    depth = 1
    cursor = opening + 1
    # The two pinned reviewed bodies contain no brace-bearing string literals.
    while cursor < len(text) and depth:
        depth += (text[cursor] == "{") - (text[cursor] == "}")
        cursor += 1
    require(depth == 0, "Unbalanced pinned UI method")
    return opening, cursor - 1


def pair(code, statement, has_return=False, reply=False, input_result=False):
    name = "berylUiInvocation" + str(code)
    value = "berylUiReturned" + str(code)
    body = "\t\t\t{\n\t\t\t\tint " + name + " = BerylObserveUiServiceEnter(" + str(code) + ");\n"
    if has_return:
        body += "\t\t\t\tbool " + value + " = " + statement + ";\n"
    else:
        body += "\t\t\t\t" + statement + ";\n"
    returned = value if has_return else "false"
    if input_result:
        returned = "input != null"
    body += "\t\t\t\tBerylObserveUiServiceExit(" + str(code) + ", " + name + ", " + ("true" if has_return or input_result else "false") + ", " + returned + ");\n"
    if reply:
        body += "\t\t\t\tif (" + value + ") reply = 1;\n"
    if input_result:
        body += "\t\t\t\tif (input) reply = 1;\n"
    return body + "\t\t\t}"


def adapter_overlay(original):
    text = checked(original, ADAPTER_SHA256)
    # Preserve source newline convention: the pinned seam is LF.
    require("\r" not in text, "Pinned adapter must be LF")
    specs = [
        (2, "m_UI = new SPK_TabletUI()", False, False),
        (10, "m_ScreenRT = new SPK_ScreenRT()", False, False),
        (11, "m_ScreenRT.Enable(GetOwner())", True, False),
        (12, "m_ScreenRT.Disable()", False, False),
        (13, "m_UI.Close()", False, False),
        (16, "m_UI.UpdateMarkers()", False, False),
        (17, "m_UI.RefreshTelemetry()", False, False),
        (18, "m_ScreenRT.Destroy()", False, False),
    ]
    for code, statement, actual_return, reply in specs:
        old = "else if (code == " + str(code) + ")\n\t\t\t\t" + statement + ";"
        count = 2 if code == 13 else 1
        require(text.count(old) == count, "Exact service source cardinality changed: " + str(code))
        new = "else if (code == " + str(code) + ")\n" + pair(code, statement, actual_return, reply)
        text = text.replace(old, new)
    old_open = "else if (code == 3)\n\t\t\t{\n\t\t\t\tif (m_UI.Open()) reply = 1;\n\t\t\t}"
    text = replace_once(text, old_open, "else if (code == 3)\n" + pair(3, "m_UI.Open()", True, True))
    old_input = "else if (code == 4)\n\t\t\t{\n\t\t\t\tinput = SPK_DroneInputComponent.Cast(GetOwner().FindComponent(SPK_DroneInputComponent));\n\t\t\t\tif (input) reply = 1;\n\t\t\t}"
    text = replace_once(text, old_input, "else if (code == 4)\n" + pair(4, "input = SPK_DroneInputComponent.Cast(GetOwner().FindComponent(SPK_DroneInputComponent))", input_result=True))
    old_missing = "else if (code == 8)\n\t\t\t\tPrint(\"[MESH] tablet has no SPK_DroneInputComponent - manual control unavailable\", LogLevel.ERROR);"
    text = replace_once(text, old_missing, "else if (code == 8)\n" + pair(8, 'Print("[MESH] tablet has no SPK_DroneInputComponent - manual control unavailable", LogLevel.ERROR)'))
    text = replace_once(text, "\t\t\t\tsuper.OnDelete(owner);\n\t\t\t\treturn;", "\t\t\t\tBerylObserveUiDeletePreSuper();\n\t\t\t\tsuper.OnDelete(owner);\n\t\t\t\treturn;")
    hooks = "\n\tprotected int BerylObserveUiServiceEnter(int code) { return 0; }\n\tprotected void BerylObserveUiServiceExit(int code, int invocationId, bool hasReturned, bool returned) {}\n\tprotected void BerylObserveUiDeletePreSuper() {}\n"
    text = replace_once(text, "\n\toverride void OnPostInit(IEntity owner)", hooks + "\n\toverride void OnPostInit(IEntity owner)")
    encoded = text.encode("utf8")
    require(len(encoded) <= MAX_BYTES, "Instrumented adapter source bound")
    return encoded


def strip_adapter(instrumented, original):
    require(type(instrumented) is bytes and instrumented == adapter_overlay(original), "Instrumented adapter is not the exact reversible overlay")
    return original


def ui_overlay(original):
    text = checked(original, UI_SHA256)
    newline = "\r\n" if "\r\n" in text else "\n"
    work = text.replace("\r\n", "\n")
    # Observe before the original unchanged enqueue, without added queue args.
    for target, delay, count in (("RefreshTerrain", 400, 2), ("ReportRootSize", 500, 1)):
        call = "GetGame().GetCallqueue().CallLater(" + target + ", " + str(delay) + ", false);"
        require(work.count(call) == count, "Exact deferred-source enqueue cardinality changed")
        work = work.replace(call, 'SPK_BerylTabletUINativeRegistry.Queue("enqueue.' + target + '", this);\n\t\t' + call)
    # Actual method entry/exit is not attributed to a particular enqueue.
    for declaration, target in (("protected void ReportRootSize()", "ReportRootSize"), ("void RefreshTerrain()", "RefreshTerrain")):
        opening, closing = method_span(work, declaration)
        original_body = work[opening + 1:closing]
        require(original_body.count("return;") == 2, "Exact deferred method early-return cardinality changed")
        exit_call = 'SPK_BerylTabletUINativeRegistry.Queue("exit.' + target + '", this);'
        # Blockify each reviewed bare if/return before inserting its exit hook.
        # Original predicate and return remain in the same branch.
        guarded = reblock_returns(original_body, exit_call)
        replacement = '\n\t\tSPK_BerylTabletUINativeRegistry.Queue("entry.' + target + '", this);' + guarded
        replacement = replacement.rstrip() + "\n\t\t" + exit_call + "\n\t"
        work = work[:opening + 1] + replacement + work[closing:]
    result = work.replace("\n", newline).encode("utf8")
    require(len(result) <= MAX_BYTES, "Instrumented UI source bound")
    return result


def reblock_returns(body, exit_call):
    import re
    # ReportRootSize has two bare guarded returns; RefreshTerrain one bare guard
    # and one return inside its retry block. Preserve each original guard.
    body = re.sub(r'(\t\tif \([^\n]+\)\n)\t\t\treturn;',
                  lambda m: m[1] + "\t\t{\n\t\t\t" + exit_call + "\n\t\t\treturn;\n\t\t}", body)
    # The remaining return is already inside the existing retry block.
    lines = body.splitlines(keepends=True)
    result = []
    for index, line in enumerate(lines):
        if line.strip() == "return;" and (not result or exit_call not in result[-1]):
            indent = line[:len(line) - len(line.lstrip())]
            result.append(indent + exit_call + "\n")
        result.append(line)
    return "".join(result)


def strip_ui(instrumented, original):
    require(type(instrumented) is bytes and instrumented == ui_overlay(original), "Instrumented UI is not the exact reversible overlay")
    return original
