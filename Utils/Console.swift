import Foundation

// MARK: - Console Utilities
enum Console {
    static func displayWidth(of string: String) -> Int {
        return string.unicodeScalars.reduce(0) { width, scalar in
            if scalar.properties.isEmojiPresentation { return width + 2 }
            switch scalar.value {
            case 0x1100...0x115F, 0x2E80...0x303F, 0x3040...0x33BF, 0x3400...0x4DBF,
                 0x4E00...0x9FFF, 0xA960...0xA97F, 0xAC00...0xD7AF, 0xF900...0xFAFF,
                 0xFE10...0xFE6F, 0xFF01...0xFF60, 0xFFE0...0xFFE6:
                return width + 2
            default:
                return width + 1
            }
        }
    }
    private static func padRight(toWidth width: Int, string: String) -> String {
        let currentWidth = displayWidth(of: string)
        if currentWidth >= width { return string }
        return string + String(repeating: " ", count: width - currentWidth)
    }
    static func success(_ msg: String) { print("\u{001B}[32m✔ \(msg)\u{001B}[0m") }
    static func warning(_ msg: String) { print("\u{001B}[33m⚠️ \(msg)\u{001B}[0m") }
    static func error(_ msg: String) { print("\u{001B}[31m✗ \(msg)\u{001B}[0m") }
    static func info(_ msg: String) { print(msg) }
    static func debug(_ msg: String) { print("\u{001B}[90m ↳ \(msg)\u{001B}[0m") }
    static func rule(_ title: String = "", dashCount: Int = Config.Display.panelLineWidth) {
        let line = String(repeating: "─", count: dashCount)
        print(title.isEmpty ? line : "\(line) \(title) \(line)")
    }
    static func panel(_ title: String, _ content: String) {
        let lines = content.split(separator: "\n").map { String($0) }
        let maxContentDisplayWidth = lines.map { displayWidth(of: $0) }.max() ?? 0
        var displayTitle = title
        if displayTitle.count > Config.Display.maxTitleDisplayChars {
            displayTitle = String(displayTitle.prefix(Config.Display.maxTitleDisplayChars - 3)) + "..."
        }
        let titleUsedWidth = 3 + displayWidth(of: displayTitle)
        let innerWidth = max(maxContentDisplayWidth + 2, titleUsedWidth + 2)
        let titleLinePadding = max(0, innerWidth - titleUsedWidth)
        print("┌─ \(displayTitle) " + String(repeating: "─", count: titleLinePadding) + "┐")
        for line in lines {
            let paddedLine = padRight(toWidth: maxContentDisplayWidth, string: line)
            print("│ \(paddedLine) │")
        }
        print("└" + String(repeating: "─", count: innerWidth) + "┘")
    }
}
