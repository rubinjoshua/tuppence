//
//  NetworkMonitor.swift
//  tuppence
//
//  Lightweight wrapper around NWPathMonitor that surfaces reachability
//  and posts a Notification when status changes. Used by the offline
//  queue: when the device transitions back online we flush pending
//  expenses.
//

import Foundation
import Network

final class NetworkMonitor {
    static let shared = NetworkMonitor()

    static let didGoOnlineNotification = Notification.Name("NetworkMonitorDidGoOnline")

    private(set) var isOnline: Bool = true

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "com.tuppence.network-monitor")
    private var hasInitialPath = false

    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            let online = path.status == .satisfied
            DispatchQueue.main.async {
                let wasOnline = self.isOnline
                self.isOnline = online
                self.hasInitialPath = true
                if !wasOnline && online {
                    NotificationCenter.default.post(name: Self.didGoOnlineNotification, object: nil)
                }
            }
        }
        monitor.start(queue: queue)
    }

    /// Best-effort synchronous read. The path monitor updates asynchronously,
    /// so this is a hint, not a guarantee — the API call will be the
    /// ultimate truth.
    var isLikelyOnline: Bool {
        // If we haven't received our first update yet, assume online so we
        // attempt the API call rather than queuing pre-emptively.
        return hasInitialPath ? isOnline : true
    }
}
