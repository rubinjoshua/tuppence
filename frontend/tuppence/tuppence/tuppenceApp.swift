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
                .task {
                    _ = StoreKitManager.shared
                }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                AppSettings.shared.loadFromSettings()
            }
        }
    }
}
