import Foundation
import WatchConnectivity
import Combine

@MainActor
final class WatchConnectivityManager: NSObject, ObservableObject, WCSessionDelegate {
    static let shared = WatchConnectivityManager()
    @Published var receivedPayload: [String: Any]?
    @Published private(set) var sessionRevision = 0
    @Published private(set) var hasPhoneSession = false
    private var lastSessionDate = 0.0
    private var cookieObserver: NSObjectProtocol?

    private override init() {
        super.init()
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
        #if os(iOS)
        cookieObserver = NotificationCenter.default.addObserver(
            forName: .NSHTTPCookieManagerCookiesChanged,
            object: nil, queue: .main
        ) { _ in
            Task { @MainActor in self.publishSession() }
        }
        #endif
    }

    #if os(iOS)
    private func sessionPayload() -> [String: Any] {
        let cookies = (HTTPCookieStorage.shared.cookies(for: API.origin) ?? [])
            .filter { $0.name == "wp_session" }
            .compactMap { $0.properties }
            .map { properties in
                Dictionary(uniqueKeysWithValues: properties.map { ($0.key.rawValue, $0.value) })
            }
        return ["kind": "phoneSession", "cookies": cookies,
                "date": Date().timeIntervalSince1970]
    }

    func publishSession() {
        guard WCSession.default.activationState == .activated else { return }
        let payload = sessionPayload()
        do { try WCSession.default.updateApplicationContext(payload) }
        catch { print("Unable to sync phone session: \(error.localizedDescription)") }
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(payload, replyHandler: nil, errorHandler: nil)
        }
    }
    #endif

    func requestPhoneSession() {
        #if os(watchOS)
        let session = WCSession.default
        guard session.activationState == .activated else { return }
        receive(session.receivedApplicationContext)
        guard session.isReachable else { return }
        session.sendMessage(["kind": "requestPhoneSession"], replyHandler: { payload in
            Task { @MainActor in self.receive(payload) }
        }, errorHandler: { _ in })
        #endif
    }

    private func receive(_ payload: [String: Any]) {
        #if os(watchOS)
        if payload["kind"] as? String == "phoneSession",
           let date = payload["date"] as? Double, date > lastSessionDate,
           let properties = payload["cookies"] as? [[String: Any]] {
            let cookies = properties.compactMap { values -> HTTPCookie? in
                let fields = Dictionary(uniqueKeysWithValues: values.map {
                    (HTTPCookiePropertyKey(rawValue: $0.key), $0.value)
                })
                guard let cookie = HTTPCookie(properties: fields),
                      cookie.name == "wp_session",
                      cookie.domain.trimmingCharacters(in: CharacterSet(charactersIn: ".")) == API.origin.host
                else { return nil }
                return cookie
            }
            let old = (HTTPCookieStorage.shared.cookies(for: API.origin) ?? [])
            let changed = old.filter { $0.name == "wp_session" }.map(\.value) != cookies.map(\.value)
            lastSessionDate = date
            for cookie in old { HTTPCookieStorage.shared.deleteCookie(cookie) }
            for cookie in cookies { HTTPCookieStorage.shared.setCookie(cookie) }
            hasPhoneSession = !cookies.isEmpty
            if changed || sessionRevision == 0 {
                ResponseCache.clear()
                Freshness.invalidateAll()
                sessionRevision += 1
            }
            return
        }
        #endif
        receivedPayload = payload
    }

    func sendUpdate(_ payload: [String: Any]) {
        guard WCSession.default.activationState == .activated else { return }
        if WCSession.default.isReachable {
            WCSession.default.sendMessage(payload, replyHandler: nil) { _ in
                WCSession.default.transferUserInfo(payload)
            }
        } else {
            WCSession.default.transferUserInfo(payload)
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
        Task { @MainActor in self.receive(message) }
    }

    nonisolated func session(_ session: WCSession, didReceiveMessage message: [String: Any],
                             replyHandler: @escaping ([String: Any]) -> Void) {
        Task { @MainActor in
            #if os(iOS)
            if message["kind"] as? String == "requestPhoneSession" {
                replyHandler(self.sessionPayload())
                return
            }
            #endif
            self.receive(message)
            replyHandler([:])
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveApplicationContext context: [String: Any]) {
        Task { @MainActor in self.receive(context) }
    }

    nonisolated func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        Task { @MainActor in self.receive(userInfo) }
    }

    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        Task { @MainActor in
            #if os(iOS)
            self.publishSession()
            #else
            self.requestPhoneSession()
            #endif
        }
    }

    #if os(iOS)
    nonisolated func sessionDidBecomeInactive(_ session: WCSession) {}
    nonisolated func sessionDidDeactivate(_ session: WCSession) { session.activate() }
    #endif

    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        guard activationState == .activated else { return }
        Task { @MainActor in
            #if os(iOS)
            self.publishSession()
            #else
            self.requestPhoneSession()
            #endif
        }
    }
}
