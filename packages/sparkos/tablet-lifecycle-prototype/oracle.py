"""Independent source-order decision oracle; reviewed services are scripted fixtures.

This transcribes retained SPK_TabletComponent/Gadget decisions, without calling the
continuation evaluator. It does not execute Enfusion or establish engine contracts.
"""
from dataclasses import dataclass
import math
import struct


def f32(value):
    result = struct.unpack("<f", struct.pack("<f", value))[0]
    if not math.isfinite(result):
        raise ValueError("only finite binary32 fixture inputs/results are admitted")
    return result


def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


@dataclass
class State:
    mode: int = 0
    telemetry_accumulator: float = 0.0


class Original:
    def __init__(self, world):
        self.world = world

    def sync_screen(self):
        w = self.world
        if w.state.mode == 1:
            if not w.ui_state["screen_present"]:
                w.service("screen.create")
            w.service("screen.enable")  # The returned boolean is intentionally ignored.
            return
        if w.ui_state["screen_present"]:
            w.service("screen.disable")

    def focus(self, argument=False, dt=0.0):
        w = self.world
        if w.state.mode != 1:
            return False
        if not w.ui_state["ui_present"]:
            w.service("ui.create")
        if not w.service("ui.open"):
            return False
        if w.service("input.find"):
            w.service("ui.set_input")
            w.service("input.get_keybinds")
            w.service("ui.set_keybinds")
        else:
            w.service("log.missing_input")
        w.state.mode = 2
        self.sync_screen()
        return True

    def unfocus(self, argument=False, dt=0.0):
        w = self.world
        if w.state.mode != 2:
            return False
        if w.ui_state["ui_present"]:
            w.service("ui.close")
        w.state.mode = 1
        self.sync_screen()
        return True

    def held(self, argument=False, dt=0.0):
        w = self.world
        if argument:
            if w.state.mode == 0:
                w.state.mode = 1
            self.sync_screen()
            return False  # Void operations use false only as a fixture return marker.
        self.unfocus()
        w.state.mode = 0
        self.sync_screen()
        return False

    def init(self, argument=False, dt=0.0):
        w = self.world
        w.service("super.init")
        w.state.mode = 0
        w.service("frame.mask")
        return False

    def frame(self, argument=False, dt=0.0):
        w = self.world
        if w.state.mode != 2 or not w.ui_state["ui_present"]:
            return False
        w.service("ui.markers")
        w.state.telemetry_accumulator = f32(w.state.telemetry_accumulator + f32(dt))
        if w.state.telemetry_accumulator < f32(0.25):
            return False
        w.state.telemetry_accumulator = f32(0.0)
        w.service("ui.telemetry")
        return False

    def delete(self, argument=False, dt=0.0):
        w = self.world
        if w.ui_state["ui_present"]:
            w.service("ui.close")
        if w.ui_state["screen_present"]:
            w.service("screen.destroy")
        w.service("super.delete")
        return False


class World:
    """Synchronous scripted service host, shared by the independent decision paths.

    Service identities are fixture tokens. Queue records are declarations only;
    queued methods are NOT run here. No engine object or retention claim is made.
    """
    def __init__(self, config, hooks=(), *, mode=0, accumulator=0.0):
        self.config = {"ui_present": False, "screen_present": False, "open": True,
                       "map": True, "input": True, "core": True, "owner": True,
                       "screen_build": True, "local_owner": True, "controller": True,
                       "controlled_owner": True, "tablet": True, **config}
        self.state = State(mode, f32(accumulator))
        self.ui_state = {"ui_present": self.config["ui_present"], "ui_root": self.config.get("ui_root", False),
                         "screen_present": self.config["screen_present"], "screen_widget": False,
                         "screen_enabled": False, "screen_owner": None, "input_bound": False,
                         "keybinds": False, "hint": None, "queue": [], "map_attached": False}
        self.events = []
        self.steps = []
        self.hooks = [{"service": name, "operation": operation, "argument": argument,
                       "dt": f32(dt), "used": False} for name, operation, argument, dt in hooks]
        self.backend = None
        self.depth = 0
        self.service_count = 0
        self.operation_count = 0

    def snapshot(self):
        return {"mode": self.state.mode, "accumulator_bits": bits(self.state.telemetry_accumulator),
                **{name: (list(value) if isinstance(value, list) else value)
                   for name, value in self.ui_state.items()}}

    def record(self, phase, name, **payload):
        if len(self.events) >= 4096:
            raise ValueError("fixture event budget exhausted")
        self.events.append({"seq": len(self.events), "phase": phase, "name": name,
                            "snapshot": self.snapshot(), **payload})

    def trace_step(self, **payload):
        if len(self.steps) >= 4096:
            raise ValueError("fixture continuation transcript budget exhausted")
        self.steps.append({"seq": len(self.steps), **payload})

    def invoke(self, operation, argument=False, dt=0.0):
        if operation not in {"focus", "unfocus", "held", "init", "frame", "delete", "gadget"}:
            raise ValueError("unknown fixture operation")
        if self.depth >= 8 or self.operation_count >= 128:
            raise ValueError("fixture operation/depth budget exhausted")
        self.operation_count += 1
        identity = self.operation_count
        self.depth += 1
        self.record("operation_begin", operation, operation_id=identity, argument=bool(argument), dt_bits=bits(f32(dt)))
        try:
            answer = self.gadget(argument) if operation == "gadget" else self.backend.invoke(operation, argument, f32(dt))
            self.record("operation_end", operation, operation_id=identity, answer=bool(answer))
            return bool(answer)
        finally:
            self.depth -= 1

    def gadget(self, active):
        self.service("gadget.super")
        if not self.service("gadget.character_owner"):
            return False
        if not self.service("game.player_controller"):
            return False
        if not self.service("controller.controlled_owner"):
            return False
        if not self.service("tablet.find"):
            self.service("log.missing_tablet")
            return False
        if not active:
            self.invoke("held", False)
            return False
        self.invoke("held", True)
        if not self.invoke("focus"):
            return False
        if not self.ui_state["ui_present"]:
            return False
        if self.service("core.find"):
            self.service("ui.set_assets")
        else:
            self.service("log.missing_core")
        self.service("ui.contact_rows")
        self.service("ui.order_availability")
        return True

    def service(self, name):
        if self.service_count >= 1024:
            raise ValueError("fixture service budget exhausted")
        self.service_count += 1
        self.record("service_begin", name)
        for hook in self.hooks:
            if not hook["used"] and hook["service"] == name:
                hook["used"] = True  # Before reentry, so this hook cannot recursively fire itself.
                self.invoke(hook["operation"], hook["argument"], hook["dt"])
                break
        u, c = self.ui_state, self.config
        answer = False
        if name == "ui.create":
            u["ui_present"] = True
        elif name == "ui.open":
            if c["open"]:
                if not u["ui_root"]:
                    u["ui_root"] = True
                    u["hint"] = "fixture-bound-key" if u["keybinds"] else "?"
                    u["queue"].append("root-size:500")
                u["queue"].append("terrain:400")
                u["map_attached"] = c["map"]
                answer = True  # A missing map is deliberately not an Open failure.
        elif name == "ui.set_input":
            u["input_bound"] = True
        elif name == "ui.set_keybinds":
            u["keybinds"] = True  # No hint rebuild: preserve existing source order.
        elif name == "ui.close":
            u["map_attached"] = False
            u["ui_root"] = False  # Preserve UI object, keybinds, chrome/terrain and queued work.
        elif name == "screen.create":
            u["screen_present"] = True
        elif name == "screen.enable":
            if c["owner"] and c["screen_build"]:
                u["screen_widget"] = True
                u["screen_owner"] = "fixture:owner:1"
                u["screen_enabled"] = True
                answer = True
        elif name == "screen.disable":
            u["screen_owner"] = None
            u["screen_enabled"] = False
        elif name == "screen.destroy":
            self.service("screen.disable")
            u["screen_widget"] = False
        elif name == "input.find":
            answer = c["input"]
        elif name == "core.find":
            answer = c["core"]
        elif name == "gadget.character_owner":
            answer = c["local_owner"]
        elif name == "game.player_controller":
            answer = c["controller"]
        elif name == "controller.controlled_owner":
            answer = c["controlled_owner"]
        elif name == "tablet.find":
            answer = c["tablet"]
        elif name not in {"input.get_keybinds", "log.missing_input", "super.init", "frame.mask", "ui.markers",
                          "ui.telemetry", "super.delete", "gadget.super", "log.missing_tablet", "ui.set_assets",
                          "log.missing_core", "ui.contact_rows", "ui.order_availability"}:
            raise ValueError("unknown fixture service: " + name)
        self.record("service_end", name, answer=bool(answer))
        return bool(answer)


class OriginalBackend:
    def __init__(self, world):
        self.original = Original(world)

    def invoke(self, operation, argument, dt):
        return getattr(self.original, operation)(argument, dt)
