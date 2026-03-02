from __future__ import annotations

from benjamin.core.ops.doctor import run_doctor


def test_doctor_reports_empty_state_as_warning(tmp_path):
    report = run_doctor(state_dir=tmp_path)

    assert report.ok is True
    assert report.summary.missing > 0
    assert report.summary.invalid_lines == 0
