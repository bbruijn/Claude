import SwiftUI

/// De kleuren uit het ontwerp: oranje hero in rust, per fase een eigen kleur,
/// en een getinte rij per instelling.
enum Theme {
    static let background = Color(red: 0.05, green: 0.05, blue: 0.06)
    static let card = Color(red: 0.17, green: 0.17, blue: 0.18)

    static let idle = Color(red: 1.0, green: 0.29, blue: 0.12)
    static let work = Color(red: 0.20, green: 0.78, blue: 0.35)
    static let rest = Color(red: 1.0, green: 0.23, blue: 0.19)
    static let exercises = Color(red: 0.85, green: 0.85, blue: 0.87)
    static let rounds = Color(red: 0.49, green: 0.48, blue: 1.0)
    static let resetRound = Color(red: 1.0, green: 0.84, blue: 0.04)
    static let done = Color(red: 0.11, green: 0.11, blue: 0.12)

    static func color(for phase: Phase?) -> Color {
        switch phase {
        case .work: return work
        case .rest: return rest
        case .reset: return resetRound
        case nil: return idle
        }
    }

    /// Zwarte tekst op de lichte fasekleuren, wit op rood en op het eindscherm.
    static func ink(for phase: Phase?, finished: Bool) -> Color {
        if finished { return .white }
        return phase == .rest ? .white : .black
    }

    static func tint(for field: Workout.Field) -> Color {
        switch field {
        case .work: return work
        case .rest: return rest
        case .exercises: return exercises
        case .rounds: return rounds
        case .resetRound: return resetRound
        }
    }

    static func icon(for field: Workout.Field) -> String {
        switch field {
        case .work: return "play.circle.fill"
        case .rest: return "pause.circle.fill"
        case .exercises: return "bolt.circle.fill"
        case .rounds: return "arrow.clockwise"
        case .resetRound: return "clock"
        }
    }
}
