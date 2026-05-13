import Foundation
import CoreXLSX

// MARK: - WPSheet Processor
// Matches Python wpsheet_to_folders.py logic exactly.
// Fixed columns A(0), B(1), C(2), D(3), E(4). Auto-detects section/number patterns.
struct WPSheetProcessor: FolderProcessor {
    let excelFile: URL
    let coordinator: RenameStateManager
    let readLine: () -> String?

    func process() throws {
        guard let file = XLSXFile(filepath: excelFile.path) else {
            throw AppError.excelParsingError(CoreXLSXError.dataIsNotAnArchive)
        }
        guard let workbook = try file.parseWorkbooks().first else {
            throw AppError.abort("No workbooks found.")
        }
        let sheetPaths = try file.parseWorksheetPathsAndNames(workbook: workbook)
        let sheetNames = sheetPaths.compactMap { $0.name }

        guard !sheetNames.isEmpty else {
            Console.error("No worksheets found in Excel file.")
            return
        }

        let excelFilename = StringTransform.sanitize(excelFile.deletingPathExtension().lastPathComponent)
        let topFolder = excelFile.deletingLastPathComponent().appendingPathComponent(excelFilename)
        var totalFoldersCreated = 0

        // Create top folder
        guard FileSystem.createFolderSafely(at: topFolder, count: &totalFoldersCreated) else {
            throw AppError.abort("Failed to create top folder.")
        }

        // Process each sheet
        for sheetName in sheetNames {
            do {
                let ctx = try ExcelParser.readExcelToGrid(path: excelFile, sheetName: sheetName, startRow: 2)
                let grid = ctx.grid
                guard grid.count > 1 else {
                    Console.warning("Worksheet '\(sheetName)' is empty, skipping")
                    continue
                }

                let cleanSheetName = StringTransform.sanitize(sheetName)
                let sheetFolder = topFolder.appendingPathComponent(cleanSheetName)

                guard FileSystem.createFolderSafely(at: sheetFolder, count: &totalFoldersCreated) else { continue }

                let created = processSheetHierarchy(sheetFolder: sheetFolder, grid: grid)
                totalFoldersCreated += created
            } catch {
                Console.warning("Error processing sheet '\(sheetName)': \(error.localizedDescription)")
                continue
            }
        }

        print()
        Console.success("Folder creation completed: \(totalFoldersCreated) folders created")
    }

    // Matches Python process_sheet_hierarchy exactly
    private func processSheetHierarchy(sheetFolder: URL, grid: [[String]]) -> Int {
        var foldersCreated = 0
        var currentSection: String? = nil
        var currentNumber: String? = nil
        var currentAValue: String? = nil
        var lastCreatedAValue: String? = nil
        var currentBValue: String? = nil
        var processingNumber = false

        // Data rows: grid[0]=header, grid[1+]=data (= Python df.iterrows() starting at idx=0)
        for r in 1..<grid.count {
            let row = grid[r]
            let excelRowNum = r + 1  // idx+EXCEL_START_ROW = (r-1)+2 = r+1

            // Scan all cells for section/number patterns
            var rowHasSection = false
            var rowHasNumber = false
            var sectionValue = ""
            var numberValue = ""

            for cell in row {
                let c = cell.trimmingCharacters(in: .whitespaces)
                guard !c.isEmpty else { continue }

                if !rowHasSection,
                   let _ = try? Config.Regex.chineseSection.prefixMatch(in: c) {
                    rowHasSection = true
                    sectionValue = c
                    break
                }

                if !rowHasNumber,
                   let _ = try? Config.Regex.chineseNumber.prefixMatch(in: c) {
                    rowHasNumber = true
                    numberValue = c
                    break
                }
            }

            // Process section row (matches Python: if row_has_section)
            if rowHasSection {
                let secName = StringTransform.sanitize(sectionValue)
                guard !secName.isEmpty else { continue }

                currentSection = secName
                currentNumber = nil
                currentAValue = nil
                lastCreatedAValue = nil
                currentBValue = nil
                processingNumber = false

                let sectionFolder = sheetFolder.appendingPathComponent(secName)
                FileSystem.createFolderSafely(at: sectionFolder, count: &foldersCreated)
                continue
            }

            // Process number row (matches Python: elif row_has_number)
            if rowHasNumber {
                guard let sec = currentSection else {
                    Console.warning("Number '\(numberValue)' found without preceding section at row \(excelRowNum), skipping")
                    continue
                }

                let numName = StringTransform.sanitize(numberValue)
                guard !numName.isEmpty else { continue }

                currentNumber = numName
                currentAValue = nil
                lastCreatedAValue = nil
                currentBValue = nil
                processingNumber = true

                let numberFolder = sheetFolder.appendingPathComponent(sec).appendingPathComponent(numName)
                FileSystem.createFolderSafely(at: numberFolder, count: &foldersCreated)
                continue
            }

            // Data row processing (matches Python data row block)
            guard processingNumber, let sec = currentSection, let num = currentNumber else { continue }

            // Minimum columns check (Python: if len(row) < 3: continue)
            guard row.count >= 3 else { continue }

            // Skip blank rows (Python: check columns A-E all empty)
            let isBlank = (0..<min(5, row.count)).allSatisfy { row[$0].trimmingCharacters(in: .whitespaces).isEmpty }
            if isBlank { continue }

            // Get values A-E (Python: row.iloc[0..4])
            let aVal = row.indices.contains(0) ? row[0] : ""
            let bVal = row.indices.contains(1) ? row[1] : ""
            let cVal = row.indices.contains(2) ? row[2] : ""
            let dVal = row.indices.contains(3) ? row[3] : ""
            let eVal = row.indices.contains(4) ? row[4] : ""

            let aHasContent = !aVal.trimmingCharacters(in: .whitespaces).isEmpty
            let bHasContent = !bVal.trimmingCharacters(in: .whitespaces).isEmpty

            // Track merged cell values (matches Python)
            if aHasContent { currentAValue = aVal.trimmingCharacters(in: .whitespaces) }
            if bHasContent { currentBValue = bVal.trimmingCharacters(in: .whitespaces) }

            // Determine A logic (matches Python)
            let useALogic: Bool
            let effectiveAVal: String?
            if let ca = currentAValue, !ca.isEmpty {
                useALogic = true
                effectiveAVal = ca
            } else if aHasContent {
                useALogic = true
                effectiveAVal = aVal.trimmingCharacters(in: .whitespaces)
            } else {
                useALogic = false
                effectiveAVal = nil
            }

            var level4Name = ""
            var level5Name = ""
            var level6Name = ""

            if useALogic, let ea = effectiveAVal {
                // A logic: lvl4=A, lvl5=B+space+C, lvl6=D+space+E (matches Python)
                let aStr = StringTransform.sanitize(ea)
                guard !aStr.isEmpty else { continue }
                level4Name = aStr

                let effectiveB: String?
                if bHasContent { effectiveB = bVal.trimmingCharacters(in: .whitespaces) }
                else if let cb = currentBValue, !cb.isEmpty { effectiveB = cb }
                else { effectiveB = nil }

                let bStr = (effectiveB.flatMap { StringTransform.sanitize($0) }) ?? ""
                let cStr = cVal.trimmingCharacters(in: .whitespaces).isEmpty ? "" : StringTransform.sanitize(cVal.trimmingCharacters(in: .whitespaces))
                level5Name = "\(bStr) \(cStr)".trimmingCharacters(in: .whitespaces)

                let dStr = dVal.trimmingCharacters(in: .whitespaces).isEmpty ? "" : StringTransform.sanitize(dVal.trimmingCharacters(in: .whitespaces))
                let eStr = eVal.trimmingCharacters(in: .whitespaces).isEmpty ? "" : StringTransform.sanitize(eVal.trimmingCharacters(in: .whitespaces))
                level6Name = "\(dStr) \(eStr)".trimmingCharacters(in: .whitespaces)
            } else {
                // No-A logic: lvl4=B+C, lvl5=D+E, lvl6=none (matches Python)
                let effectiveB: String?
                if bHasContent { effectiveB = bVal.trimmingCharacters(in: .whitespaces) }
                else if let cb = currentBValue, !cb.isEmpty { effectiveB = cb }
                else { effectiveB = nil }

                guard let eb = effectiveB else {
                    Console.warning("Row \(excelRowNum) has empty B column and no previous B value, skipping")
                    continue
                }

                let bStr = StringTransform.sanitize(eb)
                let cStr = cVal.trimmingCharacters(in: .whitespaces).isEmpty ? "" : StringTransform.sanitize(cVal.trimmingCharacters(in: .whitespaces))
                level4Name = cStr.isEmpty ? bStr : "\(bStr) \(cStr)".trimmingCharacters(in: .whitespaces)

                let dStr = dVal.trimmingCharacters(in: .whitespaces).isEmpty ? "" : StringTransform.sanitize(dVal.trimmingCharacters(in: .whitespaces))
                let eStr = eVal.trimmingCharacters(in: .whitespaces).isEmpty ? "" : StringTransform.sanitize(eVal.trimmingCharacters(in: .whitespaces))
                level5Name = "\(dStr) \(eStr)".trimmingCharacters(in: .whitespaces)
                level6Name = ""
            }

            // Dedup level-4 folder (matches Python)
            let skipLevel4: Bool
            if useALogic, let ea = effectiveAVal {
                skipLevel4 = (ea == lastCreatedAValue)
            } else {
                skipLevel4 = false
            }

            guard !level4Name.isEmpty else {
                Console.warning("Row \(excelRowNum) has empty level-4 name, skipping")
                continue
            }

            let numberFolder = sheetFolder.appendingPathComponent(sec).appendingPathComponent(num)
            let level4Folder = numberFolder.appendingPathComponent(level4Name)

            if !skipLevel4 {
                FileSystem.createFolderSafely(at: level4Folder, count: &foldersCreated)
                if useALogic, let ea = effectiveAVal {
                    lastCreatedAValue = ea
                }
            }

            // Create level-5 folder (matches Python)
            if !level5Name.isEmpty {
                let level5Folder = level4Folder.appendingPathComponent(level5Name)
                FileSystem.createFolderSafely(at: level5Folder, count: &foldersCreated)

                // Create level-6 folder (only in A logic — matches Python)
                if useALogic && !level6Name.isEmpty {
                    let level6Folder = level5Folder.appendingPathComponent(level6Name)
                    FileSystem.createFolderSafely(at: level6Folder, count: &foldersCreated)
                }
            } else if useALogic && !level6Name.isEmpty {
                Console.warning("Row \(excelRowNum) has level-6 name but no level-5 name, skipping level-6")
            }
        }

        return foldersCreated
    }
}
