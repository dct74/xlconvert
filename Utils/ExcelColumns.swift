import Foundation

// MARK: - Namespace: ExcelColumns
enum ExcelColumns {
    static func letter(for index: Int) -> String? {
        guard (0..<Config.Limits.maxExcelColumns).contains(index), let aScalar = "A".first?.asciiValue, let scalar = UnicodeScalar(Int(aScalar) + index) else { return nil }
        return String(scalar)
    }
    static func index(for letter: String) -> Int? {
        let upper = letter.uppercased()
        var result = 0
        guard let aVal = Character("A").asciiValue else { return nil }
        for char in upper {
            guard let asciiVal = char.asciiValue, asciiVal >= aVal, asciiVal <= aVal + 25 else { return nil }
            result = result * 26 + Int(asciiVal - aVal + 1)
        }
        let zeroBased = result - 1
        guard (0..<Config.Limits.maxExcelColumns).contains(zeroBased) else { return nil }
        return zeroBased
    }
}
