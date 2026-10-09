"""Exercise the actual iPhone timer parser with Foundation on a Swift-equipped host."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_ios_timer_capture_groups_and_durations(tmp_path):
    swift = shutil.which("swift")
    if not swift:
        pytest.skip("Swift runtime is required for the native timer parser regression")
    source = (Path(__file__).resolve().parents[1] / "ios/dinnerdesk/StepTimer.swift").read_text()
    parser = source.split("/// A start button", 1)[0].replace("import SwiftUI", "import Foundation")
    harness = r'''
let cases: [(String, [Int])] = [
  ("Simmer 10 minutes.", [600]),
  ("Cook 3-4 minutes, then rest 5 minutes.", [180, 300]),
  ("Stir 15–30 seconds.", [15]),
  ("Bake 1 to 2 hours.", [3600]),
  ("Rest 1 1/2 hours.", [5400]),
  ("Rest ½ hour.", [1800]),
  ("Cook for an hour.", [3600]),
  ("Cook 0 minutes or 25 hours.", []),
  ("Chop the onion.", []),
  ("Simmer 10 minutes, then simmer 10 minutes.", [600]),
  ("Sauté 🥕 for 3–4 minutes.", [180]),
]
for (text, expected) in cases {
  let actual = StepTime.find(in: text).map(\.seconds)
  precondition(actual == expected, "\(text): expected \(expected), got \(actual)")
}
precondition(StepTime.find(in: "Cook 3–4 minutes.").first?.label == "3–4 minutes")
'''
    script = tmp_path / "TimerRegression.swift"
    script.write_text(parser + harness)
    result = subprocess.run([swift, str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
