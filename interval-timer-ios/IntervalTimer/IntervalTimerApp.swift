import SwiftUI

@main
struct IntervalTimerApp: App {
    @StateObject private var engine = WorkoutEngine()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(engine)
                .preferredColorScheme(.dark)
        }
    }
}
