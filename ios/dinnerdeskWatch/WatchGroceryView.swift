import SwiftUI

struct WatchGroceryView: View {
    @EnvironmentObject private var store: Store

    var body: some View {
        NavigationStack {
            Group {
                if store.grocery.isEmpty {
                    ContentUnavailableView("List is Empty", systemImage: "cart")
                } else {
                    List {
                        // Filter out checked items natively if user prefers a clean focus list
                        let visibleLines = store.grocery.filter { line in
                            !(store.hideChecked && (line.checked || line.neverShop))
                        }
                        
                        ForEach(visibleLines) { line in
                            HStack(spacing: 8) {
                                Image(systemName: line.checked ? "checkmark.circle.fill" : "circle")
                                    .font(.title3)
                                    .foregroundStyle(line.checked ? .green : .orange) // matches your Accent theme
                                
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(line.name)
                                        .font(.body)
                                        .strikethrough(line.checked)
                                        .foregroundStyle(line.checked ? .secondary : .primary)
                                        .lineLimit(2)
                                    
                                    if !line.quantity.isEmpty {
                                        Text(line.quantity)
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .padding(.vertical, 2)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                Task { await store.toggleGrocery(line) }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Grocery")
            .refreshable {
                await store.loadGrocery(rebuild: true)
            }
        }
    }
}
