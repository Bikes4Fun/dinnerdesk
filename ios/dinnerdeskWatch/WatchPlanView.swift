import SwiftUI

struct WatchPlanView: View {
    @EnvironmentObject private var store: Store

    var body: some View {
        NavigationStack {
            Group {
                if let plan = store.plan {
                    if plan.slots.isEmpty {
                        ContentUnavailableView("No Meals Scheduled", 
                        systemImage: "calendar")
                    } else {
                        List {
                          // Groups slots by day index similarly to your iPhone app logic
                            ForEach(plan.slots) { slot in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(slot.recipeName)
                                        .font(.headline)
                                        .lineLimit(2)
                                    
                                    HStack {
                                        Text("\(slot.servings) servings")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                        
                                        Spacer()
                                        
                                        // Visual status ring or checkmark indicator
                                        Image(systemName: slot.cooked ? "checkmark.circle.fill" : "circle")
                                            .foregroundStyle(slot.cooked ? Color.green : Color.secondary)
                                    }
                                }
                                .padding(.vertical, 4)
                                // Easy tap interaction to toggle cooked status right from the watch wrist
                                .onTapGesture {
                                    Task { await store.toggleCooked(slot) }
                                }
                            }
                        }
                    }
                } else {
                    ProgressView("Loading Plan...")
                }
            }
            .navigationTitle("My Plan")
        }
    }
}
