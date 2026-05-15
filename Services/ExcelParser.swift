import Foundation
import CoreXLSX

// MARK: - Namespace: ExcelParser
enum ExcelParser {
    static func getHeadersDict(_ grid: [[String]], maxCol: Int) -> [String: [Int]] {
        guard let firstRow = grid.first else { return [:] }
        var dict = [String: [Int]]()
        for i in 0..<maxCol {
            guard i < firstRow.count else { continue }
            let header = firstRow[i]
            if let letter = ExcelColumns.letter(for: i) {
                dict[letter, default: []].append(i); dict[letter.lowercased(), default: []].append(i); dict[header, default: []].append(i)
            }
        }
        return dict
    }

    static func readExcelToGrid(path: URL, sheetName: String, startRow: Int = Config.Limits.defaultExcelStartRow) throws -> ExcelContext {
        guard startRow >= Config.Limits.minDataStartRow else { throw AppError.abort("Start row must be at least \(Config.Limits.minDataStartRow) (Row \(Config.Limits.headerRow) is reserved for headers).") }
        guard let file = XLSXFile(filepath: path.path) else { throw AppError.excelParsingError(CoreXLSXError.dataIsNotAnArchive) }
        guard let workbook = try file.parseWorkbooks().first else { throw AppError.abort("No workbooks found in the Excel file.") }
        let sheetPaths = try file.parseWorksheetPathsAndNames(workbook: workbook)
        guard let (_, sheetPath) = sheetPaths.first(where: { $0.name?.caseInsensitiveCompare(sheetName) == .orderedSame }) else { throw AppError.abort("Sheet '\(sheetName)' not found in the Excel file.") }
        let ws: Worksheet
        do { ws = try file.parseWorksheet(at: sheetPath) } catch { throw AppError.excelParsingError(error) }
        let rows = ws.data?.rows ?? []
        let sharedStrings = try file.parseSharedStrings()
        let ssItems = sharedStrings?.items ?? []
        let styles = try? file.parseStyles()
        let dateFormatter: DateFormatter = {
            let df = DateFormatter()
            df.dateFormat = "yyyy/M/d"
            df.calendar = Calendar(identifier: .gregorian)
            df.timeZone = TimeZone.autoupdatingCurrent
            return df
        }()
        func isDateFormatCell(_ cell: Cell) -> Bool {
            guard let styles, let format = cell.format(in: styles) else {
                return cell.type == .date
            }
            let nfId = format.numberFormatId
            // Built-in date format IDs: 14-22
            if (14...22).contains(nfId) { return true }
            // Locale-specific date formats (27-36)
            if (27...36).contains(nfId) { return true }
            // Custom formats (>= 164)
            guard nfId >= 164, let numberFormats = styles.numberFormats else { return false }
            for nf in numberFormats.items where nf.id == nfId {
                let fc = nf.formatCode.lowercased()
                if fc.contains("y") || (fc.contains("m") && fc.contains("d")) {
                    return true
                }
            }
            return false
        }
        func resolveCellString(_ cell: Cell) -> String {
            guard let raw = cell.value else { return "" }
            if cell.type == .sharedString {
                guard let idx = Int(raw), idx < ssItems.count else { return "" }
                // Simple text (direct <t> element)
                if let t = ssItems[idx].text, !t.isEmpty {
                    return t
                }
                // Rich text (concatenate <r><t> runs)
                let richJoined = ssItems[idx].richText.compactMap { $0.text }.joined()
                if !richJoined.isEmpty {
                    return richJoined
                }
                return ""
            }
            // Convert date serial numbers (e.g. "46037" → "2026/1/15")
            if isDateFormatCell(cell), let date = cell.dateValue {
                return dateFormatter.string(from: date)
            }
            return raw
        }
        let maxRow = Int(rows.map(\.reference).max() ?? 0)
        guard maxRow <= Config.Limits.maxExcelRows else { throw AppError.abort("Excel row count (\(maxRow)) exceeds safe limit (\(Config.Limits.maxExcelRows)).") }
        var gridData = [Int: [Int: String]]()
        for row in rows {
            for cell in row.cells {
                guard let colIdx = ExcelColumns.index(for: cell.reference.column.value) else { continue }
                let rowIdx = Int(cell.reference.row)
                gridData[rowIdx, default: [:]][colIdx] = resolveCellString(cell)
            }
        }
        if let mergeItems = ws.mergeCells?.items {
            for mc in mergeItems {
                let parts = mc.reference.split(separator: ":")
                guard parts.count == 2 else { continue }
                let tl = parts[0], br = parts[1]
                let tlCol = tl.prefix(while: { $0.isLetter })
                let tlRowS = tl.drop(while: { $0.isLetter })
                let brCol = br.prefix(while: { $0.isLetter })
                let brRowS = br.drop(while: { $0.isLetter })
                guard let startIdx = ExcelColumns.index(for: String(tlCol)), let endIdx = ExcelColumns.index(for: String(brCol)), let tlr = Int(tlRowS), let brr = Int(brRowS) else { continue }
                guard startIdx < Config.Limits.maxExcelColumns, endIdx < Config.Limits.maxExcelColumns else { continue }
                let area = (brr - tlr + 1) * (endIdx - startIdx + 1)
                if area > Config.Limits.maxMergeCellArea { Console.warning("Skipping abnormally large merged cell area (\(area) cells). Possible corrupted Excel format."); continue }
                let val = gridData[tlr]?[startIdx] ?? ""
                for r in tlr...brr { for cIdx in startIdx...endIdx { if gridData[r]?[cIdx] == nil || gridData[r]?[cIdx]?.isEmpty == true { gridData[r, default: [:]][cIdx] = val } } }
            }
        }
        guard maxRow >= startRow else { throw AppError.abort("Sheet '\(sheetName)' has no data rows (max row \(maxRow) is less than start row \(startRow)).") }

        var maxCol = 0
        for rowIdx in startRow...maxRow {
            if let rowData = gridData[rowIdx], let maxKey = rowData.keys.max() {
                maxCol = max(maxCol, maxKey + 1)
            }
        }
        if maxCol == 0, let headerRowData = gridData[startRow - 1] {
            maxCol = (headerRowData.keys.max() ?? 0) + 1
        }
        maxCol = min(maxCol, Config.Limits.maxExcelColumns)

        var grid = [[String]](); var hRow = [String]()
        for c in 0..<maxCol {
            if ExcelColumns.letter(for: c) != nil { hRow.append(gridData[startRow - 1]?[c] ?? "\(Config.Defaults.defaultColumnPrefix)\(c+1)") }
            else { hRow.append("\(Config.Defaults.defaultColumnPrefix)\(c+1)") }
        }
        grid.append(hRow)
        for r in startRow...maxRow { var row = [String](); for c in 0..<maxCol { row.append(gridData[r]?[c] ?? "") }; grid.append(row) }
        return ExcelContext(filePath: path, sheetName: sheetName, startRow: startRow, headers: getHeadersDict(grid, maxCol: maxCol), grid: grid)
    }
}
