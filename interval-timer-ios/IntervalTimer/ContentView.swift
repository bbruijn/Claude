import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var engine: WorkoutEngine
    @State private var editing: Workout.Field?
    @State private var showingSaved = false
    @State private var justSaved = false

    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    hero
                    settings
                }
                .frame(minHeight: geometry.size.height, alignment: .top)
            }
            .scrollBounceBehavior(.basedOnSize)
        }
        .background(Theme.background)
        .ignoresSafeArea(.container, edges: .bottom)
        .sheet(item: $editing) { field in
            EditFieldSheet(field: field, value: engine.workout[field]) { engine.workout[field] = $0 }
        }
        .sheet(isPresented: $showingSaved) {
            SavedWorkoutsSheet()
        }
    }

    // MARK: - Hero

    private var hero: some View {
        ZStack(alignment: .bottomTrailing) {
            VStack(alignment: .leading, spacing: 4) {
                Text(engine.headline)
                    .font(.system(size: 19, weight: .semibold))

                if engine.hasStarted && !engine.isFinished {
                    Text("\(engine.roundText) · \(engine.exerciseText)")
                        .font(.system(size: 14, weight: .medium))
                        .opacity(0.72)
                } else {
                    Text(" ").font(.system(size: 14, weight: .medium))
                }

                Text(engine.clock)
                    .font(.system(size: 88, weight: .light, design: .default))
                    .monospacedDigit()
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                    .padding(.top, 6)

                Text(engine.subtitle)
                    .font(.system(size: 14, weight: .medium))
                    .opacity(0.7)

                ProgressBar(value: engine.progress)
                    .frame(height: 4)
                    .padding(.top, 14)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 22)
            .padding(.top, 18)
            .padding(.bottom, 30)
            .foregroundStyle(Theme.ink(for: engine.phase, finished: engine.isFinished))
            .background(
                (engine.isFinished ? Theme.done : Theme.color(for: engine.phase))
                    .animation(.easeInOut(duration: 0.35), value: engine.phase)
                    .animation(.easeInOut(duration: 0.35), value: engine.isFinished)
            )
            .clipShape(UnevenRoundedRectangle(bottomLeadingRadius: 34, bottomTrailingRadius: 34))
            .saturation(engine.hasStarted && !engine.isRunning && !engine.isFinished ? 0.6 : 1)

            PlayButton(isRunning: engine.isRunning) { engine.toggle() }
                .padding(.trailing, 26)
                .offset(y: 32)
        }
        .zIndex(1)
    }

    // MARK: - Instellingen

    private var settings: some View {
        VStack(spacing: 8) {
            Button {
                showingSaved = true
            } label: {
                SettingRow(icon: "rectangle.lefthalf.filled",
                           tint: Color(white: 0.56),
                           label: "Laad Vorige Training",
                           value: "»",
                           valueIsChevron: true)
            }
            .buttonStyle(.plain)

            ForEach(Workout.Field.allCases) { field in
                Button {
                    editing = field
                } label: {
                    SettingRow(icon: Theme.icon(for: field),
                               tint: Theme.tint(for: field),
                               label: field.title,
                               value: display(field),
                               isActive: isActive(field))
                }
                .buttonStyle(.plain)
            }

            actions
            hint
        }
        .padding(.horizontal, 12)
        .padding(.top, 48)
        .padding(.bottom, 34)
    }

    private var actions: some View {
        HStack(spacing: 8) {
            GhostButton(title: "Herstellen") { engine.reset() }
            GhostButton(title: justSaved ? "Opgeslagen" : "Training opslaan") {
                engine.saveCurrent()
                justSaved = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { justSaved = false }
            }
            GhostButton(title: engine.isSoundOn ? "Geluid aan" : "Geluid uit",
                        dimmed: !engine.isSoundOn) {
                engine.isSoundOn.toggle()
            }
        }
        .padding(.top, 14)
    }

    private var hint: some View {
        Text("Geluid mengt door je muziek heen en loopt door met het scherm op slot.")
            .font(.system(size: 12))
            .foregroundStyle(.white.opacity(0.55))
            .multilineTextAlignment(.center)
            .padding(.top, 14)
            .padding(.horizontal, 8)
    }

    private func display(_ field: Workout.Field) -> String {
        switch field {
        case .rounds: return "\(engine.workout.rounds)X"
        case .exercises: return "\(engine.workout.exercises)"
        default: return Workout.clock(engine.workout[field])
        }
    }

    /// Markeert de rij van de fase die nu loopt.
    private func isActive(_ field: Workout.Field) -> Bool {
        guard engine.isRunning, let phase = engine.phase else { return false }
        switch (phase, field) {
        case (.work, .work), (.rest, .rest), (.reset, .resetRound): return true
        default: return false
        }
    }
}

// MARK: - Onderdelen

private struct ProgressBar: View {
    let value: Double

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(.black.opacity(0.18))
                Capsule()
                    .fill(.primary)
                    .frame(width: max(0, geometry.size.width * value))
            }
        }
    }
}

private struct PlayButton: View {
    let isRunning: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                Circle().fill(.black)
                Image(systemName: isRunning ? "pause.fill" : "play.fill")
                    .font(.system(size: 26, weight: .medium))
                    .foregroundStyle(.white)
            }
            .frame(width: 64, height: 64)
            .shadow(color: .black.opacity(0.45), radius: 9, y: 6)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(isRunning ? "Pauzeren" : "Starten")
    }
}

private struct SettingRow: View {
    let icon: String
    let tint: Color
    let label: String
    let value: String
    var valueIsChevron = false
    var isActive = false

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 22))
                .foregroundStyle(valueIsChevron ? .white : tint)
                .frame(width: 30)

            Text(label)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(.white)

            Spacer(minLength: 8)

            Text(value)
                .font(.system(size: valueIsChevron ? 22 : 26, weight: .semibold))
                .monospacedDigit()
                .foregroundStyle(valueIsChevron ? .white : tint)
        }
        .padding(.horizontal, 18)
        .frame(minHeight: 62)
        .background(tint.opacity(0.16).background(Theme.card))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(tint, lineWidth: isActive ? 2 : 0)
        )
    }
}

private struct GhostButton: View {
    let title: String
    var dimmed = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 14, weight: .semibold))
                .frame(maxWidth: .infinity, minHeight: 44)
                .foregroundStyle(dimmed ? .white.opacity(0.55) : .white)
                .background(
                    RoundedRectangle(cornerRadius: 14)
                        .strokeBorder(.white.opacity(0.16), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    ContentView().environmentObject(WorkoutEngine())
}
