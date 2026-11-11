"""Run the real prep models against the cross-platform fixture on a Mac with Xcode."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
models = (root / 'ios/dinnerdesk/Models.swift').read_text(encoding='utf-8')
task = models.split('nonisolated struct PrepTask:', 1)[1].split('nonisolated struct PrepMeal:', 1)[0]
presentation = models.split('nonisolated struct PrepMeal:', 1)[1].split('/// Recipe steps not in Weekend prep', 1)[0]
source = 'import Foundation\nnonisolated struct PrepTask:' + task + '\nnonisolated struct PrepMeal:' + presentation
check = r'''
import Foundation

struct Fixture: Decodable {
  let task: PrepTask
  let expected: [PrepInstructionGroup]
}

@main struct Check {
  static func main() throws {
    let decoder = JSONDecoder()
    decoder.keyDecodingStrategy = .convertFromSnakeCase
    let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
    let fixture = try decoder.decode(Fixture.self, from: data)
    let groups = PrepTaskPresentation(fixture.task).instructionGroups
    precondition(groups.count == fixture.expected.count)
    for (actual, expected) in zip(groups, fixture.expected) {
      precondition(actual.text == expected.text)
      precondition(actual.quantities == expected.quantities)
      precondition(actual.added == expected.added)
      precondition(actual.meals.map(\.id) == expected.meals.map(\.id))
      precondition(actual.meals.map(\.name) == expected.meals.map(\.name))
      precondition(actual.meals.map(\.day) == expected.meals.map(\.day))
    }
    precondition(fixture.task.meals[0].steps![0].key == "source57")
    precondition(fixture.task.meals[0].steps![0].text == "Whisk the other half to make the glaze.")
    precondition(fixture.task.storage == "Refrigerate in a covered container.")
    var task = fixture.task
    task.instructionGroups = []
    precondition(PrepTaskPresentation(task).instructionGroups.isEmpty)
    task.instructionGroups = fixture.expected
    precondition(PrepTaskPresentation(task).instructionGroups.count == fixture.expected.count)
    print("PASS: iOS shared prep contract, cache fallback, source identities, amounts, storage")
  }
}
'''
with tempfile.TemporaryDirectory() as directory:
    scratch = Path(directory)
    (scratch / 'Models.swift').write_text(source, encoding='utf-8')
    (scratch / 'Check.swift').write_text(check, encoding='utf-8')
    subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(scratch / 'cache'),
                    str(scratch / 'Models.swift'), str(scratch / 'Check.swift'), '-o', str(scratch / 'check')], check=True)
    subprocess.run([str(scratch / 'check'), str(root / 'tests/fixtures/prep_presentation.json')], check=True)
