import Foundation

// MARK: - Chinese-ordinal parsing and directory sequence-prefix helpers
//
// Python-only enhancement ported to Swift (keeps folder trees in sync): to let
// directories whose names begin with a Chinese ordinal (第X部分 / 第X章 / 一、…)
// sort numerically, we prefix each such directory with an Arabic sequence number
// padded with leading zeros, e.g.:
//
//    "第一章 发行人本次发行上市的批准" -> "01 第一章 发行人本次发行上市的批准"
//    "第二部分 尽职调查工作记录"        -> "02 第二部分 尽职调查工作记录"
//
// Padding rule (user-confirmed "C"): at least 2 digits, widening only when the
// largest ordinal at that level needs more. Width is therefore computed per
// parent directory: all ordinal-named children under one parent = one level.
//
// Supported Chinese numerals: 一..九, 十, 十一..十九, 二十..九十九, 一百.

enum SequencePrefix {
    // Chinese digit character -> ones value.
    private static let digitValues: [Character: Int] = [
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9,
    ]
    private static let numberChars: Set<Character> = Set("一二三四五六七八九十百零")
    private static let unitChars: Set<Character> = Set("部分章节编篇款项")

    // MARK: - Parsing

    /// Consume leading Chinese numeral chars from `chars` (skipping prefix
    /// chars before them if `skipping` is provided). Returns (token, restIdx).
    private static func takeNumber(_ chars: [Character], from start: Int = 0) -> (token: String, count: Int)? {
        var i = start
        while i < chars.count, numberChars.contains(chars[i]) {
            i += 1
        }
        guard i > start else { return nil }
        return (String(chars[start..<i]), i - start)
    }

    /// Parse a leading Chinese numeral (一..一百) into an Int.
    static func chineseNumberToInt(_ text: String) -> Int? {
        let chars = Array(text)
        guard let (token, _) = takeNumber(chars) else { return nil }
        guard token != "零" else { return nil }
        if token == "一百" { return 100 }
        if token.hasPrefix("百") { return nil }  // only 一百 supported
        if token == "十" { return 10 }
        if let idx = token.firstIndex(of: "十") {
            // tens-and-ones forms: 二十 / 二十三 / 十一 / 十九
            let tensToken = String(token[..<idx])
            let onesToken = String(token[token.index(after: idx)...])
            let tens: Int
            if tensToken.isEmpty {
                tens = 1  // 十一 = 11
            } else {
                guard tensToken.count == 1, let v = digitValues[Character(tensToken)] else { return nil }
                tens = v
            }
            var result = tens * 10
            if !onesToken.isEmpty {
                guard onesToken.count == 1, let v = digitValues[Character(onesToken)] else { return nil }
                result += v
            }
            return result
        }
        // plain single digit 一..九
        guard token.count == 1, let v = digitValues[Character(token)] else { return nil }
        return v
    }

    /// Return (seqtype, number) if `name` starts with a supported ordinal.
    /// seqtype carries the trailing unit word for `第X<unit>` (so 第X章 and
    /// 第X部分 are distinct sequences) or a marker for the `X、` family.
    static func stripOrdinalPrefix(_ name: String) -> (seqtype: String, number: Int)? {
        let chars = Array(name)
        // Family 1: 第X部分/章/节 ...
        if name.hasPrefix("第") {
            guard let num = takeNumber(chars, from: 1) else { return nil }
            guard let value = chineseNumberToInt(num.token) else { return nil }
            var u = num.count + 1
            let unitStart = u
            while u < chars.count, unitChars.contains(chars[u]) {
                u += 1
            }
            guard u > unitStart else { return nil }
            let unit = String(chars[unitStart..<u])
            return ("第" + unit, value)
        }
        // Family 2: X、条目
        guard let num = takeNumber(chars) else { return nil }
        let after = num.count
        guard after < chars.count, chars[after] == "、" else { return nil }
        guard let value = chineseNumberToInt(num.token) else { return nil }
        return ("、", value)
    }

    // MARK: - Renaming

    /// Prefix ordinal-named directories under `rootURL` with Arabic numbers.
    /// Walks deepest-first so renaming a child never invalidates a parent path.
    /// Width chosen per (parent, seqtype) as max(2, digits of max ordinal).
    /// Returns number of directories renamed.
    @discardableResult
    static func addSequencePrefix(rootURL: URL) -> Int {
        struct Node { let depth: Int; let url: URL }
        var nodes: [Node] = []
        let fm = FileManager.default

        func collect(_ dir: URL, _ depth: Int) {
            guard let children = try? fm.contentsOfDirectory(
                at: dir, includingPropertiesForKeys: [.isDirectoryKey], options: []
            ) else { return }
            for child in children {
                var isDir: ObjCBool = false
                guard fm.fileExists(atPath: child.path, isDirectory: &isDir), isDir.boolValue else { continue }
                nodes.append(Node(depth: depth + 1, url: child))
                collect(child, depth + 1)
            }
        }
        collect(rootURL, 0)
        nodes.sort { $0.depth > $1.depth }  // deepest first

        // Group children by parent & seqtype to size widths.
        struct Key: Hashable { let parent: String; let seqtype: String }
        var widths: [Key: Int] = [:]
        for node in nodes {
            let parent = node.url.deletingLastPathComponent().path
            let base = node.url.lastPathComponent
            guard let (seqtype, num) = stripOrdinalPrefix(base) else { continue }
            let key = Key(parent: parent, seqtype: seqtype)
            let digits = String(num).count
            widths[key] = max(widths[key] ?? 0, max(2, digits))
        }

        var renamed = 0
        for node in nodes {  // deepest-first
            let parent = node.url.deletingLastPathComponent().path
            let base = node.url.lastPathComponent
            guard let (seqtype, num) = stripOrdinalPrefix(base) else { continue }
            guard let w = widths[Key(parent: parent, seqtype: seqtype)] else { continue }
            let newName = String(format: "%0\(w)d %@", num, base)
            guard newName != base else { continue }
            let dest = node.url.deletingLastPathComponent().appendingPathComponent(newName)
            do {
                try fm.moveItem(at: node.url, to: dest)
                renamed += 1
            } catch {
                Console.warning("Failed to rename \(base): \(error.localizedDescription)")
            }
        }
        return renamed
    }
}
