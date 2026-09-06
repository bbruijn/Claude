import AVFoundation
import Foundation

/// Speelt de piepjes van de timer.
///
/// De audiosessie staat op `.playback` met `.mixWithOthers`: de tonen mengen
/// door muziek van een andere app heen in plaats van die te onderbreken. De
/// achtergrondmodus `audio` houdt de app draaiend met het scherm op slot, maar
/// alleen zolang er werkelijk audio speelt — daarom loopt er tijdens een
/// training een stille buffer mee.
final class AudioCoach {
    enum Cue {
        case tick, work, rest, reset, done

        static func forPhase(_ phase: Phase) -> Cue {
            switch phase {
            case .work: return .work
            case .rest: return .rest
            case .reset: return .reset
            }
        }
    }

    var isEnabled = true

    private let engine = AVAudioEngine()
    private let cuePlayer = AVAudioPlayerNode()
    private let keepAlivePlayer = AVAudioPlayerNode()
    private let format = AVAudioFormat(standardFormatWithSampleRate: 44_100, channels: 1)!

    private var cueBuffers: [String: AVAudioPCMBuffer] = [:]
    private var silence: AVAudioPCMBuffer?
    private var isHoldingSession = false

    init() {
        buildGraph()
        renderCues()
        observeAudioNotifications()
    }

    // MARK: - Sessie

    /// Aanroepen zodra een training loopt: sessie actief, stille loop aan.
    func beginSession() {
        guard !isHoldingSession else { return }
        do {
            let session = AVAudioSession.sharedInstance()
            // Geen .duckOthers: dat zou de muziek de hele training zachter
            // zetten in plaats van alleen tijdens een piepje.
            try session.setCategory(.playback, mode: .default, options: [.mixWithOthers])
            try session.setActive(true)
            try startEngineIfNeeded()
            startKeepAlive()
            isHoldingSession = true
        } catch {
            isHoldingSession = false
        }
    }

    /// Aanroepen bij pauze, herstellen of het einde van de training.
    func endSession() {
        guard isHoldingSession else { return }
        isHoldingSession = false
        keepAlivePlayer.stop()
        cuePlayer.stop()
        engine.pause()
        try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
    }

    // MARK: - Afspelen

    func play(_ cue: Cue) {
        guard isEnabled, let buffer = cueBuffers[key(for: cue)] else { return }
        do {
            try startEngineIfNeeded()
            if !cuePlayer.isPlaying { cuePlayer.play() }
            cuePlayer.scheduleBuffer(buffer, at: nil, options: [])
        } catch {
            // Zonder werkende engine blijft de timer gewoon doorlopen.
        }
    }

    // MARK: - Opbouw

    private func buildGraph() {
        engine.attach(cuePlayer)
        engine.attach(keepAlivePlayer)
        engine.connect(cuePlayer, to: engine.mainMixerNode, format: format)
        engine.connect(keepAlivePlayer, to: engine.mainMixerNode, format: format)
        engine.prepare()
    }

    private func startEngineIfNeeded() throws {
        if !engine.isRunning { try engine.start() }
    }

    private func startKeepAlive() {
        let buffer = silence ?? makeBuffer(seconds: 1, tones: [])
        silence = buffer
        keepAlivePlayer.scheduleBuffer(buffer, at: nil, options: [.loops])
        if !keepAlivePlayer.isPlaying { keepAlivePlayer.play() }
    }

    // MARK: - Tonen

    private struct Tone {
        let frequency: Double
        let start: Double
        let duration: Double
        let gain: Float
    }

    private func key(for cue: Cue) -> String {
        switch cue {
        case .tick: return "tick"
        case .work: return "work"
        case .rest: return "rest"
        case .reset: return "reset"
        case .done: return "done"
        }
    }

    private func renderCues() {
        cueBuffers["tick"] = makeBuffer(seconds: 0.2, tones: [
            Tone(frequency: 760, start: 0, duration: 0.12, gain: 0.5)
        ])
        cueBuffers["work"] = makeBuffer(seconds: 0.5, tones: [
            Tone(frequency: 980, start: 0, duration: 0.16, gain: 0.7),
            Tone(frequency: 1_240, start: 0.16, duration: 0.28, gain: 0.7)
        ])
        cueBuffers["rest"] = makeBuffer(seconds: 0.4, tones: [
            Tone(frequency: 480, start: 0, duration: 0.34, gain: 0.6)
        ])
        cueBuffers["reset"] = makeBuffer(seconds: 0.4, tones: [
            Tone(frequency: 620, start: 0, duration: 0.3, gain: 0.6)
        ])
        cueBuffers["done"] = makeBuffer(seconds: 0.9, tones: [
            Tone(frequency: 880, start: 0, duration: 0.22, gain: 0.7),
            Tone(frequency: 1_100, start: 0.22, duration: 0.22, gain: 0.7),
            Tone(frequency: 1_320, start: 0.44, duration: 0.4, gain: 0.75)
        ])
    }

    /// Rendert tonen naar PCM. Een sinus met een zwakke derde harmonische komt
    /// beter door muziek heen dan een kale sinus; de envelope voorkomt kliks.
    private func makeBuffer(seconds: Double, tones: [Tone]) -> AVAudioPCMBuffer {
        let rate = format.sampleRate
        let frames = AVAudioFrameCount(seconds * rate)
        let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames)!
        buffer.frameLength = frames
        guard let samples = buffer.floatChannelData?[0] else { return buffer }
        for i in 0..<Int(frames) { samples[i] = 0 }

        for tone in tones {
            let first = Int(tone.start * rate)
            let count = Int(tone.duration * rate)
            let attack = max(1.0, 0.006 * rate)
            let release = max(1.0, 0.05 * rate)
            for n in 0..<count {
                let index = first + n
                guard index < Int(frames) else { break }
                let t = Double(n) / rate
                let wave = sin(2 * .pi * tone.frequency * t)
                    + 0.28 * sin(2 * .pi * tone.frequency * 3 * t)
                let envelope = min(Double(n) / attack, min(1.0, Double(count - n) / release))
                samples[index] += Float(wave * envelope * 0.72) * tone.gain
            }
        }
        return buffer
    }

    // MARK: - Onderbrekingen

    private func observeAudioNotifications() {
        let center = NotificationCenter.default
        center.addObserver(forName: AVAudioSession.interruptionNotification,
                           object: nil, queue: .main) { [weak self] note in
            self?.handleInterruption(note)
        }
        center.addObserver(forName: AVAudioSession.mediaServicesWereResetNotification,
                           object: nil, queue: .main) { [weak self] _ in
            self?.rebuildAfterReset()
        }
    }

    private func handleInterruption(_ note: Notification) {
        guard let info = note.userInfo,
              let raw = info[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }

        switch type {
        case .began:
            keepAlivePlayer.pause()
            cuePlayer.pause()
        case .ended:
            let options = (info[AVAudioSessionInterruptionOptionKey] as? UInt).map {
                AVAudioSession.InterruptionOptions(rawValue: $0)
            }
            guard options?.contains(.shouldResume) ?? true, isHoldingSession else { return }
            isHoldingSession = false
            beginSession()
        @unknown default:
            break
        }
    }

    private func rebuildAfterReset() {
        let wasHolding = isHoldingSession
        isHoldingSession = false
        buildGraph()
        renderCues()
        if wasHolding { beginSession() }
    }
}
