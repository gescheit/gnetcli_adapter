from unittest.mock import Mock, call, patch

from gnetcli_adapter.progress_tracker import LogProgressTracker, ProgressBarTracker


def test_progress_bar_suppressed_error_reports_last_command():
    progress_bar = Mock()
    tracker = ProgressBarTracker(Mock(fqdn="device.example.net"), progress_bar)
    tracker.set_total(2)

    tracker.run_command("ignored command")
    tracker.command_done_error_suppressed("ignored error")

    assert tracker.done_steps == 1
    progress_bar.set_progress.assert_has_calls(
        [
            call("device.example.net", 0, 2, "ignored command"),
            call("device.example.net", 1, 2, "Error (suppressed): ignored command"),
        ]
    )


def test_log_tracker_marks_suppressed_error():
    tracker = LogProgressTracker(Mock(fqdn="device.example.net"))

    with patch("gnetcli_adapter.progress_tracker.logger") as logger:
        tracker.command_done_error_suppressed("ignored error")

    logger.info.assert_called_once_with("device.example.net - Error (suppressed): ignored error")
