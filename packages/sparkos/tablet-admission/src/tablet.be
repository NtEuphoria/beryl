module sparkos.tablet_admission

/// Signature-admission fixture only. This does not implement the tablet.
pub struct State {
    state: i32 = 0
    telemetry_accumulator: f32 = 0f32
    focused: bool = false
}

/// Empty callback fixture; no lifecycle behavior is claimed.
pub fn on_post_init(inout state: State) {}

/// Empty callback fixture; no telemetry behavior is claimed.
pub fn on_frame(inout state: State, time_slice: f32) {}

/// Empty callback fixture; no teardown behavior is claimed.
pub fn on_delete(inout state: State) {}
