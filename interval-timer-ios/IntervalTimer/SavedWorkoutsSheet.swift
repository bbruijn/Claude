import SwiftUI

/// De lijst achter "Laad Vorige Training".
struct SavedWorkoutsSheet: View {
    @EnvironmentObject private var engine: WorkoutEngine
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if engine.saved.isEmpty {
                    ContentUnavailableView(
                        "Nog geen trainingen",
                        systemImage: "clock.arrow.circlepath",
                        description: Text("Tik op “Training opslaan” om de huidige instellingen te bewaren.")
                    )
                } else {
                    List {
                        ForEach(engine.saved) { entry in
                            Button {
                                engine.load(entry)
                                dismiss()
                            } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(entry.name)
                                        .font(.system(size: 16, weight: .semibold))
                                        .foregroundStyle(.white)
                                    Text(entry.workout.summary)
                                        .font(.system(size: 13))
                                        .foregroundStyle(.white.opacity(0.6))
                                }
                            }
                            .listRowBackground(Theme.card)
                        }
                        .onDelete { offsets in
                            offsets.map { engine.saved[$0] }.forEach(engine.delete)
                        }
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .background(Theme.background)
            .navigationTitle("Vorige trainingen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Sluiten") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationBackground(Theme.background)
        .preferredColorScheme(.dark)
    }
}
