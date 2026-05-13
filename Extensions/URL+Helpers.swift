import Foundation

// MARK: - URL Helpers
extension URL {
    func relativePath(from base: URL) -> String {
        let destComponents = self.standardizedFileURL.resolvingSymlinksInPath().pathComponents
        let baseComponents = base.standardizedFileURL.resolvingSymlinksInPath().pathComponents

        var i = 0
        while i < destComponents.count && i < baseComponents.count && destComponents[i] == baseComponents[i] {
            i += 1
        }

        var relComponents = Array(repeating: "..", count: baseComponents.count - i)
        relComponents.append(contentsOf: destComponents[i...])
        return relComponents.joined(separator: "/")
    }

    var assumedBaseFolder: URL { self.deletingLastPathComponent().appendingPathComponent(StringTransform.sanitize(self.deletingPathExtension().lastPathComponent)) }
}
