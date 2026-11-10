"""
Unit tests for target finder filtering logic.
"""

from chaosui.core.models import TargetInfo
from chaosui.core.target_finder import TargetFinder


def test_target_filtering():
    targets = [
        TargetInfo(selector="#pay-btn", tag_name="button", text="Pay Now", is_submit=True),
        TargetInfo(selector="#cancel-btn", tag_name="button", text="Cancel", is_destructive=True),
        TargetInfo(selector="#email-input", tag_name="input", input_type="email"),
        TargetInfo(selector="#submit-input", tag_name="input", input_type="submit"),
    ]

    submits = TargetFinder.filter_submit_targets(targets)
    assert len(submits) == 2  # #pay-btn and #submit-input

    inputs = TargetFinder.filter_input_targets(targets)
    assert len(inputs) == 1  # #email-input (excludes submit input)
    assert inputs[0].selector == "#email-input"

    buttons = TargetFinder.filter_buttons(targets)
    assert len(buttons) == 3
