//! Experimental scalar continuation protocol, not an engine component or tablet port.
//! Each invocation owns Operation; only State is shared during synchronous reentry.
module sparkos.tablet_lifecycle_prototype

pub struct State {
    mode: i32 = 0
    telemetry_accumulator: f32 = 0f32
}

pub struct Operation {
    kind: i32 = 0
    pc: i32 = 0
    screen_pc: i32 = 0
    held: bool = false
    time_slice: f32 = 0f32
    answer: bool = false
}

// Opcodes: 0 done, 1 read UI presence, 2 create UI, 3 UI.Open,
// 4 find input, 5 SetInput, 6 GetKeybinds, 7 SetKeybinds, 8 missing-input log,
// 9 read screen presence, 10 create screen, 11 Enable(owner), 12 Disable,
// 13 UI.Close, 14 superclass post-init, 15 set FRAME mask, 16 UpdateMarkers,
// 17 RefreshTelemetry, 18 screen.Destroy, 19 superclass delete.
// Presence replies and Open/input replies are 0/1. Other replies are ignored.
// The host validates the opcode/reply domain and services each yield immediately.
fn finish(inout operation: Operation, answer: bool) -> i32 {
    operation.answer = answer
    operation.pc = 999
    return 0
}

fn screen_next(let state: State, inout operation: Operation, reply: i32) -> i32 {
    if operation.screen_pc == 0 {
        if state.mode == 1 { operation.screen_pc = 1 }
        else { operation.screen_pc = 4 }
        return 9
    }
    if operation.screen_pc == 1 {
        operation.screen_pc = 2
        if reply == 0 { return 10 }
    }
    if operation.screen_pc == 2 {
        operation.screen_pc = 3
        return 11
    }
    if operation.screen_pc == 4 {
        operation.screen_pc = 5
        if reply != 0 { return 12 }
    }
    operation.screen_pc = 99
    return 0
}

pub fn next(inout state: State, inout operation: Operation, reply: i32) -> i32 {
    if operation.pc == 999 { return 0 }

    // OnPostInit: superclass first, reset mode only, then register FRAME.
    if operation.kind == 0 {
        if operation.pc == 0 {
            operation.pc = 1
            return 14
        }
        if operation.pc == 1 {
            state.mode = 0
            operation.pc = 2
            return 15
        }
        return finish(inout operation, false)
    }

    // Focus: UI.Open and input hookup precede the FOCUSED commit.
    if operation.kind == 1 {
        if operation.pc == 0 {
            if state.mode != 1 { return finish(inout operation, false) }
            operation.pc = 1
            return 1
        }
        if operation.pc == 1 {
            operation.pc = 2
            if reply == 0 { return 2 }
        }
        if operation.pc == 2 {
            operation.pc = 3
            return 3
        }
        if operation.pc == 3 {
            if reply == 0 { return finish(inout operation, false) }
            operation.pc = 4
            return 4
        }
        if operation.pc == 4 {
            if reply == 0 {
                operation.pc = 8
                return 8
            }
            operation.pc = 5
            return 5
        }
        if operation.pc == 5 {
            operation.pc = 6
            return 6
        }
        if operation.pc == 6 {
            operation.pc = 8
            return 7
        }
        if operation.pc == 8 {
            state.mode = 2
            operation.screen_pc = 0
            operation.pc = 9
        }
        if operation.pc == 9 {
            let service = screen_next(state, inout operation, reply)
            if service != 0 { return service }
            return finish(inout operation, true)
        }
    }

    // Unfocus: Close observes FOCUSED; HELD is committed before screen enabling.
    if operation.kind == 2 {
        if operation.pc == 0 {
            if state.mode != 2 { return finish(inout operation, false) }
            operation.pc = 1
            return 1
        }
        if operation.pc == 1 {
            operation.pc = 2
            if reply != 0 { return 13 }
        }
        if operation.pc == 2 {
            state.mode = 1
            operation.screen_pc = 0
            operation.pc = 3
        }
        if operation.pc == 3 {
            let service = screen_next(state, inout operation, reply)
            if service != 0 { return service }
            return finish(inout operation, true)
        }
    }

    // SetHeld(false) preserves Unfocus's transient HELD screen synchronization.
    if operation.kind == 3 {
        if operation.pc == 0 {
            if operation.held {
                if state.mode == 0 { state.mode = 1 }
                operation.screen_pc = 0
                operation.pc = 1
            } else {
                if state.mode == 2 {
                    operation.pc = 10
                    return 1
                }
                operation.pc = 20
            }
        }
        if operation.pc == 1 {
            let service = screen_next(state, inout operation, reply)
            if service != 0 { return service }
            return finish(inout operation, false)
        }
        if operation.pc == 10 {
            operation.pc = 11
            if reply != 0 { return 13 }
        }
        if operation.pc == 11 {
            state.mode = 1
            operation.screen_pc = 0
            operation.pc = 12
        }
        if operation.pc == 12 {
            let service = screen_next(state, inout operation, reply)
            if service != 0 { return service }
            operation.pc = 20
        }
        if operation.pc == 20 {
            state.mode = 0
            operation.screen_pc = 0
            operation.pc = 21
        }
        if operation.pc == 21 {
            let service = screen_next(state, inout operation, reply)
            if service != 0 { return service }
            return finish(inout operation, false)
        }
    }

    // EOnFrame checks once. Reentry from markers does not add a second gate.
    if operation.kind == 4 {
        if operation.pc == 0 {
            if state.mode != 2 { return finish(inout operation, false) }
            operation.pc = 1
            return 1
        }
        if operation.pc == 1 {
            if reply == 0 { return finish(inout operation, false) }
            operation.pc = 2
            return 16
        }
        if operation.pc == 2 {
            state.telemetry_accumulator += operation.time_slice
            if state.telemetry_accumulator < 0.25f32 { return finish(inout operation, false) }
            state.telemetry_accumulator = 0f32
            operation.pc = 3
            return 17
        }
        return finish(inout operation, false)
    }

    // OnDelete does not change mode or accumulator; superclass runs last.
    if operation.kind == 5 {
        if operation.pc == 0 {
            operation.pc = 1
            return 1
        }
        if operation.pc == 1 {
            operation.pc = 2
            if reply != 0 { return 13 }
        }
        if operation.pc == 2 {
            operation.pc = 3
            return 9
        }
        if operation.pc == 3 {
            operation.pc = 4
            if reply != 0 { return 18 }
        }
        if operation.pc == 4 {
            operation.pc = 5
            return 19
        }
        return finish(inout operation, false)
    }

    // Invalid operation kinds are not part of the fixture's admitted protocol.
    return finish(inout operation, false)
}
