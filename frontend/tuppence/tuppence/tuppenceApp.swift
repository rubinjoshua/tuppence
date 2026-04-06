//
//  tuppenceApp.swift
//  tuppence
//
//  Created by Joshua Rubin on 30/3/2026.
//

import SwiftUI

@main
struct tuppenceApp: App {
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                // Reload settings from iOS Settings when app becomes active
                AppSettings.shared.loadFromSettings()
            }
        }
    }
}
