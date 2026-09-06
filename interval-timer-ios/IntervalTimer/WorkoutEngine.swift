import Combine
import Foundation
import UIKit

/// De klok van de training: houdt bij welk segment loopt, hoeveel er nog over
/// is en wanneer welk piepje klinkt. Tijd wordt uit `Date` afgeleid, zodat de
/// timer niet wegloopt als de app op de achtergrond staat.
@MainActor
final class WorkoutEngine: ObservableObject {
    @Published var workout: Workout {
        didSet {
            guard workout != oldValue else { return }
            Storage.save(workout)
            reset()
        }
    }

    @Published private(set) var saved: [SavedWorkout]
    @Published private(set) var isRunning = false
    @Published private(set) var isFinished = false
    @Published private(set) var hasStarted = false
    @Published private(set) var remaining: Int = 0
    @Published private(set) var elapsed: Int = 0
    @Published private(set) var index = 0

    @Published var isSoundOn: Bool {
        didSet {
            Storage.saveSound(isSoundOn)
            audio.isEnabled = isSoundOn
        }
    }

    private let audio = AudioCoach()
    private var segments: [Segment] = []
    private var deadline: Date?
    private var elapsedBefore = 0
    private var lastCountdownBeep: Int?
    private var timer: DispatchSourceTimer?

    init() {
        let stored = Storage.loadWorkout()
        workout = stored
        saved = Storage.loadSaved()
        isSoundOn = Storage.loadSound()
        audio.isEnabled = isSoundOn
        segments = stored.segments
        remaining = segments.first?.duration ?? 0
    }

    // MARK: - Afgeleide waarden voor het scherm

    var current: Segment? { segments.indices.contains(index) ? segments[index] : nil }
    var total: Int { workout.totalDuration }
    var totalRemaining: Int { max(0, total - elapsed) }
    var progress: Double { total > 0 ? min(1, Double(elapsed) / Double(total)) : 0 }

    var phase: Phase? { hasStarted ? current?.phase : nil }
    var headline: String {
        if isFinished { return "Klaar!" }
        return hasStarted ? (current?.phase.label ?? "Interval Timer") : "Interval Timer"
    }

    var clock: String { Workout.clock(isFinished ? 0 : (hasStarted ? remaining : total)) }

    var subtitle: String {
        if isFinished { return "Training van \(Workout.clock(total)) afgerond" }
        guard hasStarted else { return "Totaal \(Workout.clock(total))" }
        return "Nog \(Workout.clock(totalRemaining)) van \(Workout.clock(total))"
    }

    var roundText: String { "Ronde \(current?.round ?? 1)/\(workout.rounds)" }
    var exerciseText: String { "Oefening \(current?.exercise ?? 1)/\(workout.exercises)" }

    // MARK: - Bediening

    func toggle() { isRunning ? pause() : start() }

    func start() {
        if isFinished { reset() }
        guard !segments.isEmpty else { return }

        let fresh = !hasStarted
        isRunning = true
        hasStarted = true
        lastCountdownBeep = nil
        deadline = Date().addingTimeInterval(Double(remaining))

        audio.beginSession()
        if fresh, let phase = current?.phase { audio.play(.forPhase(phase)) }

        UIApplication.shared.isIdleTimerDisabled = true
        startTimer()
    }

    func pause() {
        isRunning = false
        stopTimer()
        deadline = nil
        audio.endSession()
        UIApplication.shared.isIdleTimerDisabled = false
    }

    func reset() {
        stopTimer()
        isRunning = false
        isFinished = false
        hasStarted = false
        deadline = nil
        audio.endSession()
        UIApplication.shared.isIdleTimerDisabled = false

        segments = workout.segments
        index = 0
        elapsedBefore = 0
        elapsed = 0
        remaining = segments.first?.duration ?? 0
        lastCountdownBeep = nil
    }

    // MARK: - Opgeslagen trainingen

    func saveCurrent() {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "nl_NL")
        formatter.dateFormat = "d MMM HH:mm"
        let entry = SavedWorkout(name: formatter.string(from: Date()), workout: workout)
        saved = ([entry] + saved.filter { $0.workout != workout }).prefix(12).map { $0 }
        Storage.saveSaved(saved)
    }

    func load(_ entry: SavedWorkout) { workout = entry.workout }

    func delete(_ entry: SavedWorkout) {
        saved.removeAll { $0.id == entry.id }
        Storage.saveSaved(saved)
    }

    // MARK: - Klok

    private func startTimer() {
        stopTimer()
        let source = DispatchSource.makeTimerSource(queue: .main)
        source.schedule(deadline: .now(), repeating: .milliseconds(50), leeway: .milliseconds(10))
        source.setEventHandler { [weak self] in
            MainActor.assumeIsolated { self?.tick() }
        }
        source.resume()
        timer = source
    }

    private func stopTimer() {
        timer?.cancel()
        timer = nil
    }

    private func tick() {
        guard isRunning, let deadline else { return }
        var left = deadline.timeIntervalSinceNow

        // Aftellen: 3-2-1 vlak voor het einde van een segment.
        let whole = Int(ceil(left))
        if whole > 0, whole <= 3, lastCountdownBeep != whole {
            lastCountdownBeep = whole
            audio.play(.tick)
        }

        while left <= 0 {
            // Was de app onderbroken, dan slaan we de gemiste piepjes over.
            let quiet = left < -1.5
            guard advance(overshoot: -left, quiet: quiet) else { return }
            guard let next = self.deadline else { return }
            left = next.timeIntervalSinceNow
        }

        remaining = Int(ceil(max(0, left)))
        elapsed = elapsedBefore + (current.map { $0.duration - Int(ceil(max(0, left))) } ?? 0)
    }

    /// Zet door naar het volgende segment. Geeft `false` als de training klaar is.
    @discardableResult
    private func advance(overshoot: Double, quiet: Bool) -> Bool {
        guard let finished = current else { return false }
        elapsedBefore += finished.duration
        index += 1
        lastCountdownBeep = nil

        guard let next = current else {
            isRunning = false
            isFinished = true
            remaining = 0
            elapsed = total
            stopTimer()
            deadline = nil
            UIApplication.shared.isIdleTimerDisabled = false
            if !quiet { audio.play(.done) }
            audio.endSession()
            return false
        }

        deadline = Date().addingTimeInterval(Double(next.duration) - overshoot)
        remaining = next.duration
        if !quiet { audio.play(.forPhase(next.phase)) }
        return true
    }
}

/// Bewaart instellingen tussen sessies.
enum Storage {
    private static let workoutKey = "workout.v1"
    private static let savedKey = "saved.v1"
    private static let soundKey = "sound.v1"

    static func loadWorkout() -> Workout {
        guard let data = UserDefaults.standard.data(forKey: workoutKey),
              let value = try? JSONDecoder().decode(Workout.self, from: data) else { return Workout() }
        return value
    }

    static func save(_ workout: Workout) {
        guard let data = try? JSONEncoder().encode(workout) else { return }
        UserDefaults.standard.set(data, forKey: workoutKey)
    }

    static func loadSaved() -> [SavedWorkout] {
        guard let data = UserDefaults.standard.data(forKey: savedKey),
              let value = try? JSONDecoder().decode([SavedWorkout].self, from: data) else { return [] }
        return value
    }

    static func saveSaved(_ list: [SavedWorkout]) {
        guard let data = try? JSONEncoder().encode(list) else { return }
        UserDefaults.standard.set(data, forKey: savedKey)
    }

    static func loadSound() -> Bool {
        UserDefaults.standard.object(forKey: soundKey) as? Bool ?? true
    }

    static func saveSound(_ on: Bool) {
        UserDefaults.standard.set(on, forKey: soundKey)
    }
}
