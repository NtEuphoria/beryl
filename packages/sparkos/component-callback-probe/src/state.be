//! Isolated engine-callback fixture. No tablet services, ownership or performance claim.
module sparkos.component_callback_probe

pub struct State {
    ready: bool = true
    init_count: i32 = 0
    frame_count: i32 = 0
    delete_count: i32 = 0
    elapsed: f32 = 0f32
}

pub fn on_init(inout state: State) {
    state.init_count += 1
}

pub fn on_frame(inout state: State, time_slice: f32) {
    state.frame_count += 1
    state.elapsed += time_slice
}

pub fn on_delete(inout state: State) {
    state.delete_count += 1
    state.ready = false
}
