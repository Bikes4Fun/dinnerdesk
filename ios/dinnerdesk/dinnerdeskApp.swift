//
//  dinnerdeskApp.swift
//  dinnerdesk
//
//  Created by Deanna Garrett 2026.
//

import SwiftUI

@main
struct dinnerdeskApp: App {
  init() {
    Theme.registerFonts()
    Theme.configureAppearance()
    Copy.validate()
  }

  var body: some Scene {
    WindowGroup {
      ContentView()
        .font(Theme.body)
        .onReceive(
          NotificationCenter.default.publisher(
            for: UIContentSizeCategory.didChangeNotification
          )
        ) { _ in
          Theme.configureAppearance()
        }
    }
  }
}
