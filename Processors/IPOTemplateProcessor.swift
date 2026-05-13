import Foundation
import CoreXLSX

// MARK: - IPO Template Processor
// Matches Python ipo_template_to_folders.py logic exactly.
// Hardcoded columns A(Chapter), B(Subsection), C(Detail), starts at Excel row 3.
struct IPOTemplateProcessor: FolderProcessor {
    let excelFile: URL
    let coordinator: RenameStateManager
    let readLine: () -> String?

    func process() throws {
        guard let file = XLSXFile(filepath: excelFile.path) else {
            throw AppError.excelParsingError(CoreXLSXError.dataIsNotAnArchive)
        }
        guard let workbook = try file.parseWorkbooks().first else {
            throw AppError.abort("No workbooks found in the Excel file.")
        }
        let sheetPaths = try file.parseWorksheetPathsAndNames(workbook: workbook)
        guard let (_, sheetPath) = sheetPaths.first else {
            throw AppError.abort("No worksheets found in the Excel file.")
        }
        let ws = try file.parseWorksheet(at: sheetPath)
        let rows = ws.data?.rows ?? []
        let mergeItems = ws.mergeCells?.items ?? []
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
            if (14...22).contains(nfId) { return true }
            if (27...36).contains(nfId) { return true }
            guard nfId >= 164, let numberFormats = styles.numberFormats else { return false }
            for nf in numberFormats.items where nf.id == nfId {
                let fc = nf.formatCode.lowercased()
                if fc.contains("y") || (fc.contains("m") && fc.contains("d")) {
                    return true
                }
            }
            return false
        }

        // Resolve cell string: shared string cells carry the index; resolve it here.
        func resolveCellString(_ cell: Cell) -> String? {
            guard let raw = cell.value else { return nil }
            if cell.type == .sharedString {
                guard let idx = Int(raw), idx < ssItems.count else { return nil }
                if let t = ssItems[idx].text { return t }
                return nil
            }
            // Convert date serial numbers (e.g. "46037" → "2026/1/15")
            if isDateFormatCell(cell), let date = cell.dateValue {
                return dateFormatter.string(from: date)
            }
            return raw
        }

        // Build merged-cell map (matches Python merged_map logic)
        var mergedMap: [String: String] = [:]
        for mc in mergeItems {
            let parts = mc.reference.split(separator: ":")
            guard parts.count == 2 else { continue }
            let tlCol = parts[0].prefix(while: { $0.isLetter })
            let tlRow = Int(parts[0].drop(while: { $0.isLetter })) ?? 0
            let brCol = parts[1].prefix(while: { $0.isLetter })
            let brRow = Int(parts[1].drop(while: { $0.isLetter })) ?? 0
            let tlColIdx = ExcelColumns.index(for: String(tlCol)) ?? 0
            let brColIdx = ExcelColumns.index(for: String(brCol)) ?? tlColIdx
            // Find top-left value
            var topLeftValue = ""
            if let rowData = rows.first(where: { $0.reference == tlRow }),
               let cell = rowData.cells.first(where: { ExcelColumns.index(for: $0.reference.column.value) == tlColIdx }),
               let val = resolveCellString(cell) {
                topLeftValue = val
            }
            for r in tlRow...brRow {
                for c in tlColIdx...brColIdx {
                    guard let letter = ExcelColumns.letter(for: c) else { continue }
                    mergedMap["\(r):\(letter)"] = topLeftValue
                }
            }
        }

        // Helper to get cell value (matches Python get_cell_value)
        func getCellValue(row: Int, col: Int) -> String? {
            guard let colLetter = ExcelColumns.letter(for: col - 1) else { return nil }
            let key = "\(row):\(colLetter)"
            if let val = mergedMap[key], !val.isEmpty {
                return val
            }
            // Check regular cell data
            if let rowData = rows.first(where: { $0.reference == row }),
               let colIdx = ExcelColumns.index(for: colLetter),
               let cell = rowData.cells.first(where: { ExcelColumns.index(for: $0.reference.column.value) == colIdx }),
               let val = resolveCellString(cell), !val.isEmpty {
                return val
            }
            return nil
        }

        // Create top folder (matches Python: top_folder = excel_file.parent / sanitize(excel_file.stem))
        let topFolderName = StringTransform.sanitize(excelFile.deletingPathExtension().lastPathComponent)
        let topFolder = excelFile.deletingLastPathComponent().appendingPathComponent(topFolderName)
        var foldersCreated = 0

        guard FileSystem.createFolderSafely(at: topFolder, count: &foldersCreated) else {
            throw AppError.abort("Failed to create top-level folder.")
        }

        // Find max row
        let maxRow = Int(rows.map(\.reference).max() ?? 0)
        guard maxRow >= 3 else {
            Console.info("No data rows found (needs at least row 3).")
            return
        }

        // Process rows from row 3 onward (matches Python: for row in range(3, max_row + 1))
        var currentChapterFolder: URL?
        var currentSubsectionFolder: URL?
        var currentAVal = ""
        var currentBVal = ""

        for row in 3...maxRow {
            let rawA = getCellValue(row: row, col: 1) ?? ""
            let rawB = getCellValue(row: row, col: 2) ?? ""
            let rawC = getCellValue(row: row, col: 3) ?? ""

            let valA = rawA.trimmingCharacters(in: .whitespaces)
            let valB = rawB.trimmingCharacters(in: .whitespaces)
            let valC = rawC.trimmingCharacters(in: .whitespaces)

            // Skip blank rows (matches Python: if not val_a and not val_b and not val_c: continue)
            if valA.isEmpty && valB.isEmpty && valC.isEmpty {
                continue
            }

            // Chapter: A has value, B and C are empty (matches Python: if val_a and not val_b and not val_c)
            if !valA.isEmpty && valB.isEmpty && valC.isEmpty {
                let folderName = StringTransform.sanitize(valA)
                if folderName.isEmpty { continue }

                let chapterURL = topFolder.appendingPathComponent(folderName)
                guard FileSystem.createFolderSafely(at: chapterURL, count: &foldersCreated) else { continue }
                currentChapterFolder = chapterURL
                currentSubsectionFolder = nil
                currentAVal = ""
                currentBVal = ""
                continue
            }

            // Subsection: A and B both have values (matches Python: elif val_a and val_b)
            if !valA.isEmpty && !valB.isEmpty {
                guard let chapterFolder = currentChapterFolder else { continue }

                // Only create subsection folder if A or B changed (matches Python)
                if currentSubsectionFolder == nil || valA != currentAVal || valB != currentBVal {
                    let folderName = StringTransform.sanitize("\(StringTransform.sanitize(valA)) \(StringTransform.sanitize(valB))")
                    if folderName.isEmpty { continue }

                    let subURL = chapterFolder.appendingPathComponent(folderName)
                    guard FileSystem.createFolderSafely(at: subURL, count: &foldersCreated) else { continue }
                    currentSubsectionFolder = subURL
                    currentAVal = valA
                    currentBVal = valB
                }
            }

            // Detail: C has value (matches Python: if val_c: — note: this is NOT elif, so it runs after the subsection block)
            if !valC.isEmpty {
                guard let subFolder = currentSubsectionFolder else { continue }

                let folderName = StringTransform.sanitize(valC)
                if folderName.isEmpty { continue }

                let detailURL = subFolder.appendingPathComponent(folderName)
                guard FileSystem.createFolderSafely(at: detailURL, count: &foldersCreated) else { continue }
            }
        }

        Console.success("Folder creation completed, created \(foldersCreated) folders in total")
        Console.info("Folder structure located at: \(topFolder.path)")
    }
}
