"""Compile real API/Session code with mocked auth responses; no server or simulator needed."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1] / "dinnerdesk"
session = (root / "AuthView.swift").read_text().split("@MainActor", 1)[1].split("/// Wrap the app", 1)[0]
with tempfile.TemporaryDirectory() as directory:
    scratch = Path(directory)
    (scratch / "Session.swift").write_text('import Foundation\nimport Combine\n' + '@MainActor' + session)
    (scratch / "Check.swift").write_text(r'''
import Foundation
struct AuthStatus { let authenticated: Bool }
@MainActor enum AuthAPI {
  static var responses: [Result<AuthStatus, Error>] = []
  static func status() async throws -> AuthStatus { try responses.removeFirst().get() }
  static func logout() async throws {}
}
@MainActor enum KitchenAPI {
  static var response: Result<[String: Any], Error> = .success(["tour_done": true])
  static func prefs() async throws -> [String: Any] { try response.get() }
  static func message(_ error: Error) -> String { error.localizedDescription }
}
@main struct Check {
  @MainActor static func main() async {
    let session = Session()
    AuthAPI.responses = [.failure(URLError(.networkConnectionLost)), .success(AuthStatus(authenticated: true))]
    await session.refresh()
    precondition(session.status == nil && session.loadError != nil)
    await session.refresh()
    precondition(session.status?.authenticated == true && session.loadError == nil)
    AuthAPI.responses = [.failure(URLError(.networkConnectionLost)), .success(AuthStatus(authenticated: true))]
    await session.refresh()
    precondition(session.status?.authenticated == true && session.loadError != nil)
    await session.refresh()
    precondition(session.status?.authenticated == true && session.loadError == nil)
    AuthAPI.responses = [.failure(URLError(.cancelled))]
    await session.refresh()
    precondition(session.status?.authenticated == true && session.loadError == nil)
    KitchenAPI.response = .failure(CancellationError())
    await session.checkTour()
    precondition(session.loadError == nil && !session.showTour)
    KitchenAPI.response = .success([:])
    await session.checkTour()
    precondition(session.showTour)
    var fatalNotifications = 0
    let observer = NotificationCenter.default.addObserver(forName: Notification.Name("dinnerdeskFailure"), object: nil, queue: nil) { _ in fatalNotifications += 1 }
    API.reportFailure(URLError(.networkConnectionLost))
    API.reportFailure(URLError(.timedOut))
    API.reportFailure(URLError(.cancelled))
    API.reportFailure(APIError.http(503, ""))
    precondition(fatalNotifications == 0)
    NotificationCenter.default.removeObserver(observer)
    print("PASS: startup retry, retained session, cancellation, tour retry, no fatal request notifications")
  }
}
''')
    subprocess.run(["xcrun", "swiftc", "-module-cache-path", str(scratch / "cache"), str(root / "API.swift"), str(scratch / "Session.swift"), str(scratch / "Check.swift"), "-o", str(scratch / "check")], check=True)
    subprocess.run([str(scratch / "check")], check=True)
