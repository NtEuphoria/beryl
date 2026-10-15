//! Bounded plain member-box and emitted-handler ABI probe; no gameplay services.
module sparkos.component_state_probe

pub struct State {
    ready: bool = true
    count: i32 = 17
    elapsed: f32 = 0.125f32
}

pub fn on_init(inout state: State) {
    state.count += 1
}

pub fn on_frame(inout state: State, time_slice: f32) {
    state.count += 1
    state.elapsed += time_slice
}

pub fn on_delete(inout state: State) {
    state.ready = false
    state.count = -7
}

pub fn mutate_fields(inout state: State) {
    state.ready = false
    state.count += 5
    state.elapsed += 0.25f32
}

pub fn replace(inout state: State) {
    state = State{ready: false, count: 41, elapsed: 0.5f32}
}

pub fn reset(inout state: State) {
    state = State{}
}
