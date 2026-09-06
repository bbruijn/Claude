import Foundation

/// De vijf instelbare waarden van een training.
struct Workout: Codable, Equatable {
    var work = 60
    var rest = 90
    var exercises = 1
    var rounds = 8
    var resetRound = 0

    enum Field: String, CaseIterable, Identifiable {
        case work, rest, exercises, rounds, resetRound
        var id: String { rawValue }

        var title: String {
            switch self {
            case .work: return "Werk"
            case .rest: return "Uitrusten"
            case .exercises: return "Oefeningen"
            case .rounds: return "Rondes"
            case .resetRound: return "Ronde resetten"
            }
        }

        /// Duurvelden krijgen minuut/seconde-wielen, tellers één wiel.
        var isDuration: Bool {
            switch self {
            case .work, .rest, .resetRound: return true
            case .exercises, .rounds: return false
            }
        }

        var range: ClosedRange<Int> {
            switch self {
            case .work: return 1...3600
            case .rest: return 0...3600
            case .resetRound: return 0...1800
            case .exercises: return 1...50
            case .rounds: return 1...99
            }
        }
    }

    subscript(field: Field) -> Int {
        get {
            switch field {
            case .work: return work
            case .rest: return rest
            case .exercises: return exercises
            case .rounds: return rounds
            case .resetRound: return resetRound
            }
        }
        set {
            let value = min(field.range.upperBound, max(field.range.lowerBound, newValue))
            switch field {
            case .work: work = value
            case .rest: rest = value
            case .exercises: exercises = value
            case .rounds: rounds = value
            case .resetRound: resetRound = value
            }
        }
    }

    /// Het volledige programma: per ronde elke oefening werk + rust, tussen
    /// rondes de reset. De laatste rust vervalt — de training eindigt na het
    /// laatste werkinterval.
    var segments: [Segment] {
        var result: [Segment] = []
        for round in 1...max(1, rounds) {
            for exercise in 1...max(1, exercises) {
                result.append(Segment(phase: .work, duration: work, round: round, exercise: exercise))
                if rest > 0 {
                    result.append(Segment(phase: .rest, duration: rest, round: round, exercise: exercise))
                }
            }
            if round < rounds, resetRound > 0 {
                result.append(Segment(phase: .reset, duration: resetRound, round: round, exercise: exercises))
            }
        }
        while let last = result.last, last.phase != .work { result.removeLast() }
        return result
    }

    var totalDuration: Int { segments.reduce(0) { $0 + $1.duration } }

    var summary: String {
        "\(Self.clock(work)) werk · \(Self.clock(rest)) rust · \(exercises) oef. · \(rounds)X · \(Self.clock(totalDuration))"
    }

    static func clock(_ seconds: Int) -> String {
        let s = max(0, seconds)
        let hours = s / 3600, minutes = (s % 3600) / 60, rest = s % 60
        return hours > 0
            ? String(format: "%d:%02d:%02d", hours, minutes, rest)
            : String(format: "%02d:%02d", minutes, rest)
    }
}

enum Phase: String, Codable {
    case work, rest, reset

    var label: String {
        switch self {
        case .work: return "Werk"
        case .rest: return "Uitrusten"
        case .reset: return "Ronde resetten"
        }
    }
}

struct Segment: Equatable {
    let phase: Phase
    let duration: Int
    let round: Int
    let exercise: Int
}

/// Een opgeslagen training in "Laad Vorige Training".
struct SavedWorkout: Codable, Identifiable, Equatable {
    var id = UUID()
    var name: String
    var workout: Workout
}
