import SwiftUI

/// The first-open privacy screen. Shows until this guest kitchen (or account) agrees to the current
/// privacy version (auth/status privacy_agreed). "I understand, continue" is the agreement.
/// Same screen as the website's PrivacyAgreement.jsx and Android's PrivacyAgreement.
struct PrivacyAgreementView: View {
  @EnvironmentObject private var session: Session
  @State private var busy = false
  @State private var error: String?
  @State private var showPrivacy = false
  @State private var showSignIn = false

  private var signedIn: Bool { session.status?.authenticated == true }

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 16) {
        Text(Copy.appName)
          .font(Theme.action)
          .foregroundStyle(Theme.accent)
        Text(Copy.text("privacy.agree.title"))
          .font(Theme.bigTitle)
          .foregroundStyle(Theme.ink)
        Text(Copy.text(signedIn ? "privacy.agree.updated" : "privacy.agree.guest"))
          .font(Theme.body)
          .foregroundStyle(Theme.ink)

        PrivacySummaryView(compact: true)

        if !signedIn {
          Text(Copy.text("privacy.agree.device"))
            .font(Theme.subtitle)
            .foregroundStyle(Theme.accent)
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.aubergineTint, in: RoundedRectangle(cornerRadius: 12))
        }

        if let error { ErrorBanner(message: error) }

        Button {
          Task { await agree() }
        } label: {
          HStack {
            Spacer()
            if busy { ProgressView().tint(Theme.bg) } else { Text(Copy.text("privacy.agree.button")).font(Theme.action) }
            Spacer()
          }
          .frame(minHeight: 52)
          .foregroundStyle(Theme.bg)
          .background(Theme.ink, in: Capsule())
        }
        .disabled(busy)

        Text(Copy.text("privacy.agree.fine"))
          .font(Theme.subtitle)
          .foregroundStyle(Theme.muted)
          .multilineTextAlignment(.center)
          .frame(maxWidth: .infinity)

        VStack(spacing: 4) {
          Button(Copy.text("privacy.agree.read")) { showPrivacy = true }
            .frame(minHeight: 44)
          if !signedIn {
            Button("Create an account instead") { showSignIn = true }
              .frame(minHeight: 44)
          }
        }
        .font(Theme.action)
        .foregroundStyle(Theme.accent)
        .frame(maxWidth: .infinity)
      }
      .padding(20)
    }
    .background(Theme.bg)
    .sheet(isPresented: $showPrivacy) {
      NavigationStack {
        PrivacyView()
          .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { showPrivacy = false } } }
      }
      .environmentObject(session)
    }
    .sheet(isPresented: $showSignIn) {
      AuthView(isSheet: true).environmentObject(session)
    }
  }

  private func agree() async {
    busy = true
    error = nil
    defer { busy = false }
    do {
      try await AuthAPI.agreeToPrivacy()
      await session.refresh()
    } catch {
      self.error = KitchenAPI.message(error)
    }
  }
}
