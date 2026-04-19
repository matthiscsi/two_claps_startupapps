from src.clap_state import ClapDecision, DoubleClapStateMachine


def test_double_clap_within_window_triggers():
    machine = DoubleClapStateMachine(min_interval=0.2, max_interval=1.0)

    first = machine.register_clap(0.5)
    second = machine.register_clap(0.9)

    assert first.decision == ClapDecision.ACCEPTED
    assert first.clap_count == 1
    assert second.decision == ClapDecision.DOUBLE_CLAP
    assert second.state == "IDLE"


def test_second_clap_too_fast_is_ignored():
    machine = DoubleClapStateMachine(min_interval=0.2, max_interval=1.0)
    machine.register_clap(1.0)
    event = machine.register_clap(1.1)
    assert event.decision == ClapDecision.NONE
    assert event.reason == "min_interval"
    assert event.clap_count == 1


def test_waiting_state_times_out():
    machine = DoubleClapStateMachine(min_interval=0.2, max_interval=1.0)
    machine.register_clap(1.0)
    event = machine.on_tick(2.2)
    assert event.state == "IDLE"
    assert event.clap_count == 0
