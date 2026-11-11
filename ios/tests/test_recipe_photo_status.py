"""Decode the shared photo/review contract using the real iOS models on Mac/Xcode."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
models = (root / "ios/dinnerdesk/Models.swift").read_text(encoding="utf-8")
start = models.index("nonisolated struct RecipeGalleryPhoto:")
end = models.index("nonisolated struct GroceryList:", start)
source = "import Foundation\n" + models[start:end]
check = r'''
import Foundation

@main struct Check {
  static func main() throws {
    let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
    let decoder = JSONDecoder()
    decoder.keyDecodingStrategy = .convertFromSnakeCase
    let recipe = try decoder.decode(RecipeDetail.self, from: data)
    precondition(recipe.reviewed && recipe.photos.count == 2)
    precondition(recipe.photos[0].tested == true && recipe.photos[0].primary)
    precondition(recipe.photos[0].credit == "Photo: Dinnerdesk")
    precondition(recipe.photos[0].sourceUrl == "https://example.test/photos/tested")
    precondition(recipe.photos[1].ai && recipe.photos[1].tested == false)
    var old = try JSONSerialization.jsonObject(with: data) as! [String: Any]
    old.removeValue(forKey: "photos")
    old.removeValue(forKey: "reviewed")
    let cached = try decoder.decode(RecipeDetail.self, from: JSONSerialization.data(withJSONObject: old))
    precondition(!cached.reviewed && cached.photos.count == 1)
    precondition(cached.photos[0].tested == nil)
    old["photos"] = []
    let empty = try decoder.decode(RecipeDetail.self, from: JSONSerialization.data(withJSONObject: old))
    precondition(empty.photos.isEmpty)
    print("PASS: iOS recipe approval, photo flags, credits and old-cache fallback")
  }
}
'''
with tempfile.TemporaryDirectory() as directory:
    scratch = Path(directory)
    (scratch / "Models.swift").write_text(source, encoding="utf-8")
    (scratch / "Check.swift").write_text(check, encoding="utf-8")
    subprocess.run(["xcrun", "swiftc", "-module-cache-path", str(scratch / "cache"),
                    str(scratch / "Models.swift"), str(scratch / "Check.swift"), "-o", str(scratch / "check")], check=True)
    subprocess.run([str(scratch / "check"), str(root / "tests/fixtures/recipe_photo_status.json")], check=True)
