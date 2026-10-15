"""Fixture scheduling model of lifecycle.be, not an independent language oracle.

Every recorded next call is replayed through the actual Beryl reference executor.
The independent source-order oracle lives separately in oracle.py.
"""
from dataclasses import asdict, dataclass
from oracle import bits, f32

KINDS = {"init": 0, "focus": 1, "unfocus": 2, "held": 3, "frame": 4, "delete": 5}
SERVICES = {2: "ui.create", 3: "ui.open", 4: "input.find", 5: "ui.set_input", 6: "input.get_keybinds",
            7: "ui.set_keybinds", 8: "log.missing_input", 10: "screen.create", 11: "screen.enable",
            12: "screen.disable", 13: "ui.close", 14: "super.init", 15: "frame.mask", 16: "ui.markers",
            17: "ui.telemetry", 18: "screen.destroy", 19: "super.delete"}
BOOL_OPCODES = {1, 3, 4, 9, 11}


@dataclass
class Operation:
    kind: int = 0
    pc: int = 0
    screen_pc: int = 0
    held: bool = False
    time_slice: float = 0.0
    answer: bool = False


def finish(op, answer=False):
    op.answer, op.pc = answer, 999
    return 0


def screen_next(state, op, reply):
    if op.screen_pc == 0:
        op.screen_pc = 1 if state.mode == 1 else 4
        return 9
    if op.screen_pc == 1:
        op.screen_pc = 2
        if reply == 0:
            return 10
    if op.screen_pc == 2:
        op.screen_pc = 3
        return 11
    if op.screen_pc == 4:
        op.screen_pc = 5
        if reply != 0:
            return 12
    op.screen_pc = 99
    return 0


def next_step(state, op, reply):
    if op.pc == 999:
        return 0
    if op.kind == 0:
        if op.pc == 0:
            op.pc = 1
            return 14
        if op.pc == 1:
            state.mode, op.pc = 0, 2
            return 15
        return finish(op)
    if op.kind == 1:
        if op.pc == 0:
            if state.mode != 1:
                return finish(op)
            op.pc = 1
            return 1
        if op.pc == 1:
            op.pc = 2
            if reply == 0:
                return 2
        if op.pc == 2:
            op.pc = 3
            return 3
        if op.pc == 3:
            if reply == 0:
                return finish(op)
            op.pc = 4
            return 4
        if op.pc == 4:
            if reply == 0:
                op.pc = 8
                return 8
            op.pc = 5
            return 5
        if op.pc == 5:
            op.pc = 6
            return 6
        if op.pc == 6:
            op.pc = 8
            return 7
        if op.pc == 8:
            state.mode, op.screen_pc, op.pc = 2, 0, 9
        if op.pc == 9:
            service = screen_next(state, op, reply)
            return service if service else finish(op, True)
    if op.kind == 2:
        if op.pc == 0:
            if state.mode != 2:
                return finish(op)
            op.pc = 1
            return 1
        if op.pc == 1:
            op.pc = 2
            if reply != 0:
                return 13
        if op.pc == 2:
            state.mode, op.screen_pc, op.pc = 1, 0, 3
        if op.pc == 3:
            service = screen_next(state, op, reply)
            return service if service else finish(op, True)
    if op.kind == 3:
        if op.pc == 0:
            if op.held:
                if state.mode == 0:
                    state.mode = 1
                op.screen_pc, op.pc = 0, 1
            else:
                if state.mode == 2:
                    op.pc = 10
                    return 1
                op.pc = 20
        if op.pc == 1:
            service = screen_next(state, op, reply)
            return service if service else finish(op)
        if op.pc == 10:
            op.pc = 11
            if reply != 0:
                return 13
        if op.pc == 11:
            state.mode, op.screen_pc, op.pc = 1, 0, 12
        if op.pc == 12:
            service = screen_next(state, op, reply)
            if service:
                return service
            op.pc = 20
        if op.pc == 20:
            state.mode, op.screen_pc, op.pc = 0, 0, 21
        if op.pc == 21:
            service = screen_next(state, op, reply)
            return service if service else finish(op)
    if op.kind == 4:
        if op.pc == 0:
            if state.mode != 2:
                return finish(op)
            op.pc = 1
            return 1
        if op.pc == 1:
            if reply == 0:
                return finish(op)
            op.pc = 2
            return 16
        if op.pc == 2:
            state.telemetry_accumulator = f32(state.telemetry_accumulator + op.time_slice)
            if state.telemetry_accumulator < f32(0.25):
                return finish(op)
            state.telemetry_accumulator = f32(0.0)
            op.pc = 3
            return 17
        return finish(op)
    if op.kind == 5:
        if op.pc == 0:
            op.pc = 1
            return 1
        if op.pc == 1:
            op.pc = 2
            if reply != 0:
                return 13
        if op.pc == 2:
            op.pc = 3
            return 9
        if op.pc == 3:
            op.pc = 4
            if reply != 0:
                return 18
        if op.pc == 4:
            op.pc = 5
            return 19
        return finish(op)
    return finish(op)


class ProtocolBackend:
    def __init__(self, world, *, mutant=None):
        self.world, self.mutant, self.counter = world, mutant, 0
        self.shared_operation = None

    def invoke(self, name, argument, dt):
        w = self.world
        self.counter += 1
        identity = self.counter
        op = Operation(KINDS[name], held=argument, time_slice=dt)
        if self.mutant == "reentry_overwrite":
            self.shared_operation = op
        w.trace_step(event="begin", id=identity, operation=asdict(op))
        reply = 0
        for _ in range(64):
            if self.mutant == "reentry_overwrite":
                op = self.shared_operation
            opcode = next_step(w.state, op, reply)
            w.trace_step(event="step", id=identity, reply=reply, opcode=opcode,
                         operation=asdict(op), mode=w.state.mode,
                         accumulator_bits=bits(w.state.telemetry_accumulator))
            if opcode == 0:
                w.trace_step(event="end", id=identity, answer=op.answer)
                return op.answer
            if opcode == 1:
                answer = w.ui_state["ui_present"]
            elif opcode == 9:
                answer = w.ui_state["screen_present"]
            elif opcode in SERVICES:
                if self.mutant == "skip_markers" and opcode == 16:
                    answer = False
                else:
                    answer = w.service(SERVICES[opcode])
            else:
                raise ValueError("unknown emitted opcode")
            reply = int(answer) if opcode in BOOL_OPCODES else 0
        raise ValueError("continuation step budget exhausted")
