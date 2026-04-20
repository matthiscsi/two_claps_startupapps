from src.ui_logic import describe_detector_state


def test_describe_detector_state_device_error():
    label, color = describe_detector_state(
        detector_available=False,
        detector_active=False,
        state="IDLE",
        clap_count=0,
        peak=0.0,
        threshold=0.15,
    )
    assert label == "Device Error"
    assert color


def test_describe_detector_state_clap_detected():
    label, _ = describe_detector_state(
        detector_available=True,
        detector_active=True,
        state="WAITING",
        clap_count=1,
        peak=0.3,
        threshold=0.15,
    )
    assert label == "Clap Detected"


def test_describe_detector_state_listening():
    label, _ = describe_detector_state(
        detector_available=True,
        detector_active=True,
        state="IDLE",
        clap_count=0,
        peak=0.1,
        threshold=0.15,
    )
    assert label in {"Listening", "Noise Too Low"}


def test_describe_detector_state_too_loud():
    label, _ = describe_detector_state(
        detector_available=True,
        detector_active=True,
        state="IDLE",
        clap_count=0,
        peak=0.45,
        threshold=0.15,
    )
    assert label == "Too Loud"
