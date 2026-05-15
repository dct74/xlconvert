import Foundation

// MARK: - Namespace: StringTransform
enum StringTransform {
    static func sanitize(_ s: String?) -> String {
        guard let str = s else { return "" }
        let trimmed = str.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return "" }

        let stem = trimmed.split(separator: ".").first?.uppercased() ?? ""
        if Config.reservedWindowsNames.contains(String(stem)) {
            return "_\(trimmed)_"
        }

        return trimmed.replacing(Config.Regex.invalidChars, with: "")
    }
    static func safeUTF8Truncate(_ string: String, maxByteLen: Int) -> String {
        if string.utf8.count <= maxByteLen { return string }
        var result = ""; var currentBytes = 0
        for char in string {
            let charBytes = char.utf8.count
            if currentBytes + charBytes > maxByteLen { break }
            result.append(char); currentBytes += charBytes
        }
        return result
    }
    static func truncatePathComponent(_ component: String, maxLen: Int = Config.Limits.maxPathComponentLength) -> (String, Bool) {
        if component.utf8.count <= maxLen { return (component, false) }
        var stem = component; var ext = ""
        if let dotIndex = component.lastIndex(of: "."), dotIndex != component.startIndex {
            stem = String(component[..<dotIndex]); ext = String(component[dotIndex...])
        }
        let extLen = ext.utf8.count; let suffix = "..."; let suffixLen = suffix.utf8.count
        let maxStemLen = maxLen - extLen - suffixLen
        if maxStemLen <= 0 {
            let safeStr = safeUTF8Truncate(component, maxByteLen: maxLen)
            Console.warning("Path truncated (ext too long): \(component) -> \(safeStr)")
            return (safeStr, true)
        }
        let safeStem = safeUTF8Truncate(stem, maxByteLen: maxStemLen)
        let finalStr = safeStem + suffix + ext
        Console.warning("Path truncated: \(component) -> \(finalStr)")
        return (finalStr, true)
    }
    private static func isValidDate(year: Int, month: Int, day: Int) -> Bool {
        var components = DateComponents(); components.year = year; components.month = month; components.day = day
        return Calendar.current.date(from: components) != nil
    }
    private static func validateAndFormatDate(year: Int, month: Int, day: Int) -> String? {
        guard (Config.Limits.yearMin...Config.Limits.yearMax).contains(year), (1...12).contains(month), (1...31).contains(day), isValidDate(year: year, month: month, day: day) else { return nil }
        return String(format: "%04d%02d%02d", year, month, day)
    }
    static func formatDateString(_ value: String) -> String {
        var strValue = value.trimmingCharacters(in: .whitespaces)
        guard !strValue.isEmpty else { return "" }

        // Remove date-time suffix
        strValue = strValue.replacing(Config.Regex.dateTimeSuffix, with: "")

        // If all digits and not 8 digits, early return sanitize
        let isAllDigits = strValue.unicodeScalars.allSatisfy { CharacterSet.decimalDigits.contains($0) }
        if isAllDigits && strValue.count != 8 {
            return sanitize(strValue)
        }

        // Try date separator split
        let parts = strValue.components(separatedBy: CharacterSet(charactersIn: "-/.")).filter { !$0.isEmpty }
        if parts.count == 3 {
            // YYYY-MM-DD
            if parts[0].count == 4, let y = Int(parts[0]), let m = Int(parts[1]), let d = Int(parts[2]),
               let formatted = validateAndFormatDate(year: y, month: m, day: d) {
                return formatted
            }
            // MM-DD-YYYY or DD-MM-YYYY
            if parts[2].count == 4, let y = Int(parts[2]) {
                if let m = Int(parts[0]), let d = Int(parts[1]),
                   let formatted = validateAndFormatDate(year: y, month: m, day: d) {
                    return formatted
                }
                if let d = Int(parts[0]), let m = Int(parts[1]),
                   let formatted = validateAndFormatDate(year: y, month: m, day: d) {
                    return formatted
                }
            }
        }

        // Chinese date pattern search
        let nsStr = strValue as NSString
        let chinesePattern = "(\\d{4})年(\\d{1,2})月(\\d{1,2})日"
        if let cnRegex = try? NSRegularExpression(pattern: chinesePattern),
           let cnMatch = cnRegex.firstMatch(in: strValue, range: NSRange(location: 0, length: nsStr.length)) {
            let yRange = cnMatch.range(at: 1)
            let mRange = cnMatch.range(at: 2)
            let dRange = cnMatch.range(at: 3)
            if let y = Int(nsStr.substring(with: yRange)),
               let m = Int(nsStr.substring(with: mRange)),
               let d = Int(nsStr.substring(with: dRange)),
               let formatted = validateAndFormatDate(year: y, month: m, day: d) {
                return formatted
            }
        }

        // 8-digit date
        if (try? Config.Regex.eightDigit.wholeMatch(in: strValue)) != nil {
            if let y = Int(strValue.prefix(4)),
               let m = Int(strValue[strValue.index(strValue.startIndex, offsetBy: 4)..<strValue.index(strValue.startIndex, offsetBy: 6)]),
               let d = Int(strValue.suffix(2)),
               let formatted = validateAndFormatDate(year: y, month: m, day: d) {
                return formatted
            }
        }

        // Fallback: sanitize
        return sanitize(strValue)
    }
}
