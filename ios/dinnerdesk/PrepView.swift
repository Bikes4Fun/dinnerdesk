import SwiftUI

struct PrepView: View {
  @EnvironmentObject private var store: Store
  @Environment(\.selectTab) private var selectTab
  @Environment(\.dismiss) private var dismiss

  @State private var expanded: Set<Int> = []
  @State private var updating: Set<String> = []

  var body: some View {
    List {
      if let err = store.error {
        ErrorBanner(message: err)
      }
      Section {
        Text(Copy.text("prep.about"))
          .foregroundStyle(Theme.muted)
      }
      if store.prepTasks.isEmpty {
        Section {
          EmptyState(
            title: "No prep yet",
            message:
              "Add meals on Plan. Make-ahead steps like chopping, grating and sauces show up here.",  // TODO: what is this message? add meals ON plan? Meals show up here? or Prep steps?
            systemImage: "list.clipboard"
          )
          .listRowInsets(EdgeInsets())
          .listRowSeparator(.hidden)
          .listRowBackground(Theme.bg)
          Button("Back to plan") {
            selectTab(.plan)
            dismiss()
          }
        }
      } else {
        ForEach(store.prepTasks) { task in
          VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
              Button {
                Task { await store.togglePrep(task) }
              } label: {
                Image(systemName: task.done ? "checkmark.circle.fill" : "circle")
                  .font(.title3)
                  .foregroundStyle(task.done ? Theme.accent : Theme.muted)
              }.buttonStyle(.borderless)
                .accessibilityLabel(task.done ? "Mark \(task.title) not done" : "Mark all of \(task.title) done")
              Button {
                if expanded.contains(task.id) {
                  expanded.remove(task.id)
                } else {
                  expanded.insert(task.id)
                }
              } label: {
                HStack(alignment: .top) {
                  // Closed: just what the task is and who it's for. Details open below.
                  VStack(alignment: .leading, spacing: 4) {
                    Text(task.title).font(Theme.mealName).strikethrough(task.done)
                      .foregroundStyle(Theme.ink).multilineTextAlignment(.leading)
                    Text(summary(task)).font(Theme.subtitle).foregroundStyle(Theme.muted)
                      .multilineTextAlignment(.leading)
                    if task.auto == true {
                      Text("Suggested from your recipes").font(Theme.count).foregroundStyle(
                        Theme.accent)
                    }
                  }.frame(maxWidth: .infinity, alignment: .leading)
                  Image(systemName: expanded.contains(task.id) ? "chevron.up" : "chevron.down")
                    .foregroundStyle(Theme.accent)
                }
              }.buttonStyle(.plain).contentShape(Rectangle())
                .accessibilityValue(expanded.contains(task.id) ? "Expanded" : "Collapsed")
            }
            if expanded.contains(task.id) {
              if !task.quantities.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                  ForEach(task.quantities, id: \.self) {
                    Text($0).font(Theme.count).foregroundStyle(Theme.muted)
                  }
                }
              }
              ForEach(task.meals) { meal in
                VStack(alignment: .leading, spacing: 8) {
                  NavigationLink(meal.name) { RecipeDetailView(id: meal.id) }.font(Theme.mealName)
                  if let steps = meal.steps, !steps.isEmpty {
                    ForEach(steps) { step in
                      HStack(alignment: .top, spacing: 10) {
                        Button {
                          let key = "\(task.id):\(meal.id):\(step.key)"
                          updating.insert(key)
                          Task {
                            await store.togglePrepItem(taskId: task.id, mealId: meal.id, step: step)
                            updating.remove(key)
                          }
                        } label: {
                          Image(systemName: (step.done ?? false) ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle((step.done ?? false) ? Theme.accent : Theme.muted)
                            .frame(width: 44, height: 44)
                        }.buttonStyle(.plain)
                          .disabled(updating.contains("\(task.id):\(meal.id):\(step.key)"))
                          .accessibilityLabel((step.done ?? false) ? "Mark not done" : "Mark done")
                          .accessibilityValue(step.text)
                        VStack(alignment: .leading, spacing: 0) {
                          Text(step.text).font(Theme.body)
                            .strikethrough(step.done ?? false)
                            .foregroundStyle((step.done ?? false) ? Theme.muted : Theme.ink)
                          HStack(spacing: 4) {
                            ThumbsControl(
                              rating: step.rating ?? 0, subject: "this prep step", size: 15
                            ) { next in
                              Task {
                                await store.ratePrepStep(
                                  taskId: task.id, mealId: meal.id, step: step, next)
                              }
                            }
                            .padding(.leading, -12)
                            Text(stepNote(step)).font(Theme.subtitle).foregroundStyle(Theme.muted)
                          }
                        }
                      }
                    }
                  } else {
                    ForEach(Array(meal.instructions.enumerated()), id: \.offset) { _, text in
                      Text(text).font(Theme.body).foregroundStyle(Theme.muted)
                    }
                  }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
              }
            }
          }

        }
      }
    }
    .scrollContentBackground(.hidden)
    .background(Theme.bg)
    .navigationTitle("Weekend prep")
    .largeNavigationTitle()
    .refreshable { await store.loadPrep() }
    .task { await store.loadPrep() }
  }

  /// "For Roast beef, Salisbury steak · 1 of 2 done"
  private func summary(_ task: PrepTask) -> String {
    let names = task.meals.map(\.name).joined(separator: ", ")
    let steps = task.meals.flatMap { $0.steps ?? [] }
    let done = steps.filter { $0.done ?? false }.count
    guard steps.count > 1, done > 0, done < steps.count else { return "For \(names)" }
    return "For \(names) · \(done) of \(steps.count) done"
  }

  private func stepNote(_ step: PrepStep) -> String {
    switch step.rating ?? 0 {
    case 1: return "Useful ahead"
    case -1: return "Not useful ahead"
    default: return "Useful to do ahead?"
    }
  }
}
