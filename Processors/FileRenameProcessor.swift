import Foundation
import CoreXLSX

// MARK: - File Rename Processor
// Matches Python file_renamer.py parsing/naming logic exactly.
struct FileRenameProcessor {
    let excelFile: URL
    let coordinator: RenameStateManager
    let readLine: () -> String?

    init(excelFile: URL, coordinator: RenameStateManager, readLine: @escaping () -> String? = { Swift.readLine() }) {
        self.excelFile = excelFile
        self.coordinator = coordinator
        self.readLine = readLine
    }

    // MARK: - Public
    func process() throws {
        coordinator.clearWarnedAmbiguousHeaders()
        let files = collectFiles()
        guard !files.isEmpty else {
            Console.warning("No files found to rename.")
            Console.info("Files should be located in or under: \(excelFile.deletingLastPathComponent().path)")
            return
        }

        let filesByFolder = Dictionary(grouping: files, by: { $0.deletingLastPathComponent() })

        try prepareBackup(for: filesByFolder)

        var allOps = [RenameOperation]()
        var renamedCount = 0
        var emptyFiles = [String]()
        let baseDir = excelFile.deletingLastPathComponent()

        // Collect contexts for each folder (matches Python get_excel_context_for_file)
        var folderContexts = [URL: (context: ExcelContext, sheetName: String)]()
        for folder in filesByFolder.keys {
            if let ctx = resolveContext(folder: folder) {
                folderContexts[folder] = ctx
            }
        }

        for (folder, folderFiles) in filesByFolder {
            print()
            Console.rule("Folder: \(folder.lastPathComponent)", dashCount: 10)
            let keys = Array(filesByFolder.keys)
            let sectionNum = (keys.firstIndex(of: folder).map { $0 + 1 }) ?? 1
            let totalFolders = filesByFolder.count
            Console.info("Folder \(sectionNum)/\(totalFolders): \(folder.lastPathComponent)")

            guard let (ctx, sheetName) = folderContexts[folder] else {
                Console.warning("Skipping folder \(folder.lastPathComponent), no matching Excel data found.")
                continue
            }

            Console.info("Using worksheet: \(sheetName)")

            // Parse folder name for fallback row number (matches Python ParseResult.from_folder_path)
            let parseResult = ParseResult.from(folderPath: folder)

            // Sort preference (matches Python per-sheet sort question)
            print("\nSort files for worksheet '\(sheetName)'? (y/n): ", terminator: "")
            let sortChoice = readLine()?.trimmingCharacters(in: .whitespaces).lowercased() ?? ""

            var sheetRowMapping: [Int: Int]? = nil
            var useCustomSort = false

            if sortChoice == "y" {
                let sortCol = askSortColumn(ctx: ctx, sheetName: sheetName)
                if let col = sortCol, let colIdx = ExcelColumns.index(for: col) {
                    Console.success("Sort by column: \(col)")
                    sheetRowMapping = buildRowMapping(ctx: ctx, colIdx: colIdx)
                    useCustomSort = true
                } else {
                    Console.info("Using built-in row numbers as sequence numbers")
                }
            } else {
                Console.info("No sorting, keep original filenames")
            }

            let paddingWidth = String(ctx.grid.count).count

            // Process files in this folder
            for file in folderFiles {
                guard file.lastPathComponent != Config.dsStore else { continue }

                let result = renameSingleFile(
                    file: file,
                    ctx: ctx,
                    paddingWidth: paddingWidth,
                    sheetRowMapping: sheetRowMapping,
                    useCustomSort: useCustomSort,
                    sortChoice: sortChoice,
                    parseResult: parseResult,
                    baseDir: baseDir
                )

                switch result {
                case .success(let op):
                    allOps.append(op)
                    renamedCount += 1
                case .skipped:
                    break
                case .failure(let errorMsg, let op):
                    if let op = op { allOps.append(op) }
                    let filename = file.lastPathComponent
                    if errorMsg.contains("All columns empty") || errorMsg.contains("all columns empty") {
                        emptyFiles.append(filename)
                    } else if errorMsg.contains("No row number found") || errorMsg.contains("Invalid column letters") {
                        Console.warning("WARNING: \(errorMsg)")
                    } else if errorMsg.contains("Filename unchanged") {
                        // No warning needed
                    } else {
                        Console.warning("Error processing \(filename): \(errorMsg)")
                    }
                }
            }
        }

        // Finalize batch (matches Python rename_history.commit_batch)
        if !allOps.isEmpty, let backupDir = coordinator.backupDirectory {
            let batch = RenameBatch(operations: allOps, backupDirName: backupDir.lastPathComponent)
            coordinator.appendBatch(batch)
        }

        print()
        Console.success("Renamed: \(renamedCount) files")
        if !emptyFiles.isEmpty {
            Console.warning("\(emptyFiles.count) files had all empty columns and were not renamed")
        }
    }

    // MARK: - File Collection and Context Resolution

    private func collectFiles() -> [URL] {
        // matcher Python collect_files_from_folders
        let fm = FileManager.default
        let excelDir = excelFile.deletingLastPathComponent()
        let excelFilename = StringTransform.sanitize(excelFile.deletingPathExtension().lastPathComponent)
        let excelFolder = excelDir.appendingPathComponent(excelFilename)
        let startDir = fm.fileExists(atPath: excelFolder.path) ? excelFolder : excelDir

        guard fm.fileExists(atPath: startDir.path) else {
            Console.error("ERROR: start_dir does not exist!")
            return []
        }

        guard let enumerator = fm.enumerator(at: startDir, includingPropertiesForKeys: [.isRegularFileKey]) else {
            return []
        }

        var files = [URL]()
        for case let fileURL as URL in enumerator {
            guard let values = try? fileURL.resourceValues(forKeys: [.isRegularFileKey]),
                  values.isRegularFile == true else { continue }

            let name = fileURL.lastPathComponent
            // Skip backup dirs (matches Python: if BACKUP_DIR_PREFIX in root_path.name)
            let parentFolderName = fileURL.deletingLastPathComponent().lastPathComponent
            if parentFolderName.hasPrefix(Config.Paths.backupPrefix) { continue }

            // Skip .DS_Store and the excel file itself (matches Python)
            if name == Config.dsStore || name == excelFile.lastPathComponent { continue }

            files.append(fileURL)
        }
        return files
    }

    private func resolveContext(folder: URL) -> (context: ExcelContext, sheetName: String)? {
        // Matches Python find_sheet_for_folder logic: use folder name relative to excel dir
        let excelDir = excelFile.deletingLastPathComponent()
        let excelName = StringTransform.sanitize(excelFile.deletingPathExtension().lastPathComponent)

        // Try to find sheet name from folder structure
        let relativePath = folder.path.replacingOccurrences(of: excelDir.path + "/", with: "")
        let parts = relativePath.split(separator: "/").map(String.init)

        var targetSheetName: String?
        if parts.count >= 2 && parts[0] == excelName {
            targetSheetName = parts[1]
        } else if parts.count >= 1 {
            targetSheetName = parts[0]
        }

        guard let sheetName = targetSheetName else { return nil }

        // Try to load the sheet
        guard let file = XLSXFile(filepath: excelFile.path) else { return nil }
        guard let workbook = try? file.parseWorkbooks().first else { return nil }
        let sheetPaths = (try? file.parseWorksheetPathsAndNames(workbook: workbook)) ?? []
        let availableNames = sheetPaths.compactMap(\.name)

        // Find matching sheet by name
        guard let matchedName = ConsoleIO.findSheetName(in: availableNames, target: sheetName) else {
            // Fallback: use first sheet (matches Python)
            if let firstName = availableNames.first {
                Console.warning("Sheet '\(sheetName)' not found, using first sheet '\(firstName)'")
                if let ctx = try? ExcelParser.readExcelToGrid(path: excelFile, sheetName: firstName, startRow: Config.Limits.defaultExcelStartRow) {
                    return (ctx, firstName)
                }
            }
            return nil
        }

        guard let ctx = try? ExcelParser.readExcelToGrid(path: excelFile, sheetName: matchedName, startRow: Config.Limits.defaultExcelStartRow) else {
            return nil
        }
        return (ctx, matchedName)
    }

    // MARK: - Backup

    private func prepareBackup(for filesByFolder: [URL: [URL]]) throws {
        try FileSystem.initBackupDirectory(excelFile: excelFile, coordinator: coordinator)
        guard let backupDir = coordinator.backupDirectory else {
            throw AppError.backupFailed("Failed to initialize backup directory.")
        }
        let sourceDir = excelFile.deletingLastPathComponent()
        try FileSystem.ensureSameVolume(sourceDir: sourceDir, backupDir: backupDir)
        if !FileSystem.backupFolderStructure(sourceFolders: Array(filesByFolder.keys), to: backupDir, baseDir: sourceDir) {
            cleanupFailedBackup(backupDir)
            throw AppError.backupFailed("CRITICAL: Aborting rename process because folder structure backup failed.")
        }
        Console.success("Backup completed.")
    }

    private func cleanupFailedBackup(_ backupDir: URL) {
        try? FileManager.default.removeItem(at: backupDir)
        coordinator.backupDirectory = nil
    }

    // MARK: - Sorting

    private func askSortColumn(ctx: ExcelContext, sheetName: String) -> String? {
        // Matches Python get_sort_column: tries up to MAX_SORT_ATTEMPTS
        for _ in 0..<Config.Limits.maxSortAttempts {
            print("Specify sort column for Sheet '\(sheetName)' (A-Z) or press Enter to sort by row number: ", terminator: "")
            guard let input = readLine()?.trimmingCharacters(in: .whitespaces).uppercased(), !input.isEmpty else {
                return nil
            }
            if input.count == 1, let first = input.first, first.isLetter,
               let colIdx = ExcelColumns.index(for: input), colIdx < ctx.grid[0].count {
                return input
            }
            Console.error("Invalid input, please enter a single letter")
        }
        Console.warning("Multiple invalid attempts, skipping sorting")
        return nil
    }

    private func buildRowMapping(ctx: ExcelContext, colIdx: Int) -> [Int: Int] {
        // Matches Python create_row_mapping
        // Python: df_with_index["_original_row"] = range(EXCEL_START_ROW, len(df) + EXCEL_START_ROW)
        // Python: df_sorted = df_with_index.sort_values(by="_sort_key")
        let sortedIndices = (1..<ctx.grid.count).sorted { a, b in
            let valA = (colIdx < ctx.grid[a].count ? ctx.grid[a][colIdx] : "").lowercased()
            let valB = (colIdx < ctx.grid[b].count ? ctx.grid[b][colIdx] : "").lowercased()
            if valA == valB { return a < b }
            return valA < valB
        }
        var mapping = [Int: Int]()
        // Python: row_mapping[original_row] = order_num
        // original_row in Python = idx + EXCEL_START_ROW, where idx = 0-based DataFrame index
        // In Swift grid: idx = r - 1, so original_row = (r-1) + 2 = r + 1
        for (order, r) in sortedIndices.enumerated() {
            mapping[r + 1] = order + 1  // r+1 = Excel row number (matches Python row_num)
        }
        return mapping
    }

    // MARK: - Core Rename Logic (matches Python rename_single_file_compat)

    private enum RenameResult {
        case success(RenameOperation)
        case skipped(String)
        case failure(String, RenameOperation?)
    }

    private func getFileNamePartType(_ filename: String) -> FileNamePartType {
        // Matches Python get_filename_part_type
        let stem = URL(fileURLWithPath: filename).deletingPathExtension().lastPathComponent
        if stem.isEmpty { return .empty }
        let isDigits = stem.allSatisfy { $0.isASCII && $0.isNumber }
        if isDigits { return .digitsOnly }
        let isLetters = stem.allSatisfy { $0.isASCII && $0.isLetter }
        if isLetters { return .lettersOnly }
        return .mixed
    }

    private func renameSingleFile(
        file: URL,
        ctx: ExcelContext,
        paddingWidth: Int,
        sheetRowMapping: [Int: Int]?,
        useCustomSort: Bool,
        sortChoice: String,
        parseResult: ParseResult,
        baseDir: URL
    ) -> RenameResult {
        let filename = file.lastPathComponent
        if filename == Config.dsStore { return .skipped("ds_store") }

        let namePart = file.deletingPathExtension().lastPathComponent
        let ext = file.pathExtension
        let extWithDot = ext.isEmpty ? "" : ".\(ext)"
        let parts = namePart.split(separator: "-").map(String.init)

        // Extract row number and column parts (matches Python logic exactly)
        var rowNum: Int?
        var startIdx = 0
        let partType = getFileNamePartType(filename)

        if partType == .digitsOnly {
            rowNum = Int(namePart)
            startIdx = 1  // All digits → row num, use all columns for values (no dash)
        } else if !parts.isEmpty && Int(parts[0]) != nil {
            rowNum = Int(parts[0])
            startIdx = 1  // First part is row number
        } else if partType == .lettersOnly && parseResult.isValid, let prRow = parseResult.rowNumber {
            rowNum = prRow
            startIdx = 0  // Letters only → use parse result row
        } else if parseResult.isValid, let prRow = parseResult.rowNumber {
            rowNum = prRow
            startIdx = 0
        }

        guard let row = rowNum else {
            return .failure("No row number found: \(filename)", nil)
        }

        // Row number validation (matches Python get_row_index)
        let dataRowIndex = row - ctx.startRow + 1  // Python: row_num - EXCEL_START_ROW
        guard dataRowIndex >= 1, dataRowIndex < ctx.grid.count else {
            return .failure("Row number \(row) out of range: \(filename)", nil)
        }

        // Extract column parts (matches Python start_idx logic)
        let columnParts: [String]
        if startIdx == 0 {
            columnParts = parts
        } else if startIdx < parts.count {
            columnParts = Array(parts[startIdx...])
        } else {
            columnParts = []
        }

        // Validate column parts (matches Python: all must be letters-only)
        let allLetters = columnParts.allSatisfy { (try? Config.Regex.lettersOnly.wholeMatch(in: $0)) != nil }
        if !columnParts.isEmpty && !allLetters {
            return .failure("Invalid column letters in filename: \(filename)", nil)
        }

        // Order string (matches Python)
        let orderStr: String
        if useCustomSort, let mapping = sheetRowMapping, let orderNum = mapping[row] {
            orderStr = String(format: "%0\(paddingWidth)d-", orderNum)
        } else if sortChoice == "y" {
            orderStr = String(format: "%0\(paddingWidth)d-", row)
        } else {
            orderStr = ""
        }

        // Find actual data table header row by scanning column A for "序号" (serial number header).
        // For sheets 3-6 (著作权/专利权/商标权/集成电路), the header row may be at rows 7-9 (grid[6]-grid[8]),
        // not at row 1 (grid[0]). Auto-detect avoids empty/default column names from title rows.
        var headerRowIndex = 0
        for i in 0..<ctx.grid.count {
            let colA = ctx.grid[i].first ?? ""
            if colA == "序号" || colA == "注册号" {
                headerRowIndex = i
                break
            }
        }

        // Build headers dict for column name lookup (matches Python get_headers_dict)
        var letterToHeader: [String: String] = [:]
        for (i, header) in ctx.grid[headerRowIndex].enumerated() {
            if let letter = ExcelColumns.letter(for: i) {
                letterToHeader[letter.lowercased()] = header
                letterToHeader[letter.uppercased()] = header
            }
        }

        // Generate new filename parts (matches Python three branches)
        let newParts: [String]
        let dataRow = ctx.grid[dataRowIndex]

        if columnParts.isEmpty {
            // No column letters → scan ALL columns for non-empty values (matches Python)
            var allEmpty = true
            var collected = [String]()
            for colIdx in 0..<dataRow.count {
                let val = (colIdx < dataRow.count ? dataRow[colIdx] : "").trimmingCharacters(in: .whitespaces)
                if val.isEmpty { continue }
                let formatted = StringTransform.formatDateString(val)
                let clean = StringTransform.sanitize(formatted)
                if !clean.isEmpty {
                    collected.append(clean)
                    allEmpty = false
                }
            }
            if allEmpty { return .failure("All columns empty: \(filename)", nil) }
            newParts = collected
        } else if columnParts.count == 1, let singlePart = columnParts.first {
            // Single part with letters → use header names (matches Python)
            var collected = [String]()
            for ch in singlePart.uppercased() {
                let colLetter = String(ch)
                if let header = letterToHeader[colLetter] {
                    let cleanHeader = StringTransform.sanitize(header)
                    collected.append(cleanHeader.isEmpty ? colLetter : cleanHeader)
                } else {
                    collected.append(colLetter)
                }
            }
            newParts = collected
        } else {
            // Multiple parts → flatten letters, get cell values (matches Python)
            var allLetters = [String]()
            for part in columnParts {
                for ch in part.uppercased() { allLetters.append(String(ch)) }
            }
            var allEmpty = true
            var collected = [String]()
            for colLetter in allLetters {
                guard let colIdx = ExcelColumns.index(for: colLetter) else { continue }
                let val = (colIdx < dataRow.count ? dataRow[colIdx] : "").trimmingCharacters(in: .whitespaces)
                if val.isEmpty { continue }
                let formatted = StringTransform.formatDateString(val)
                let clean = StringTransform.sanitize(formatted)
                if !clean.isEmpty {
                    collected.append(clean)
                    allEmpty = false
                }
            }
            if allEmpty { return .failure("All columns empty: \(filename)", nil) }
            newParts = collected
        }

        guard !newParts.isEmpty else {
            return .failure("No valid columns: \(filename)", nil)
        }

        let newName = newParts.joined(separator: "-")
        let newFilename = "\(orderStr)\(newName)\(extWithDot)"

        guard newFilename != filename else {
            return .skipped("Filename unchanged: \(filename)")
        }

        // Execute rename
        let oldRel = FileSystem.getRelativePath(from: baseDir, to: file)
        let (safeName, _) = StringTransform.truncatePathComponent(newFilename)
        let finalURL = FileSystem.getUniqueFilePath(originalURL: file.deletingLastPathComponent().appendingPathComponent(safeName))
        let newRel = FileSystem.getRelativePath(from: baseDir, to: finalURL)

        do {
            try FileManager.default.moveItem(at: file, to: finalURL)
            let op = RenameOperation(oldRelativePath: oldRel, newRelativePath: newRel, relativeBackupPath: oldRel, status: .success, errorMessage: nil)
            return .success(op)
        } catch {
            let op = RenameOperation(oldRelativePath: oldRel, newRelativePath: newRel, relativeBackupPath: oldRel, status: .failed, errorMessage: error.localizedDescription)
            Console.error("Failed to rename \(filename): \(error.localizedDescription)")
            return .failure(error.localizedDescription, op)
        }
    }

    // MARK: - Undo

    func undoLastBatch() {
        guard !coordinator.isHistoryEmpty else { Console.warning("Nothing to undo."); return }
        let baseDir = excelFile.deletingLastPathComponent()
        guard let batch = coordinator.lastBatch else { return }
        let backupDir = baseDir.appendingPathComponent(batch.backupDirName)
        let fm = FileManager.default
        var success = 0, originallyFailed = 0, alreadyRestored = 0, failed = 0
        var hasNewProgress = false

        for i in batch.operations.indices.reversed() {
            var op = batch.operations[i]
            if op.isRestored { alreadyRestored += 1; continue }
            if op.status != .success { originallyFailed += 1; continue }
            let backupFileURL = backupDir.appendingPathComponent(op.relativeBackupPath)
            let originalFileURL = baseDir.appendingPathComponent(op.oldRelativePath)
            guard fm.fileExists(atPath: backupFileURL.path) else { Console.warning("Backup missing for \(originalFileURL.lastPathComponent), skipping restore."); failed += 1; continue }
            let tempRestoreURL = originalFileURL.deletingLastPathComponent().appendingPathComponent("\(Config.Defaults.tempRestorePrefix)\(UUID().uuidString)")
            if fm.fileExists(atPath: originalFileURL.path) {
                do { try fm.moveItem(at: originalFileURL, to: tempRestoreURL) } catch { Console.warning("Failed to move current file to temp state: \(error.localizedDescription)"); failed += 1; continue }
            }
            do {
                try fm.moveItem(at: backupFileURL, to: originalFileURL)
                if fm.fileExists(atPath: tempRestoreURL.path) { try fm.removeItem(at: tempRestoreURL) }
                // Delete the renamed file now that the original is restored
                let renamedFileURL = baseDir.appendingPathComponent(op.newRelativePath)
                if renamedFileURL != originalFileURL, fm.fileExists(atPath: renamedFileURL.path) {
                    try fm.removeItem(at: renamedFileURL)
                }
                op.isRestored = true
                coordinator.updateLastBatch { currentBatch in currentBatch.operations[i] = op }
                hasNewProgress = true; success += 1
            } catch {
                Console.error("Failed to restore \(originalFileURL.lastPathComponent): \(error.localizedDescription)")
                Console.error("Original file is safely preserved at: \(tempRestoreURL.path)")
                failed += 1
            }
        }

        let totalOps = batch.operations.count
        if failed == 0 && success + originallyFailed + alreadyRestored == totalOps {
            coordinator.removeLastBatch()
            if let remaining = try? fm.contentsOfDirectory(at: backupDir, includingPropertiesForKeys: nil), remaining.isEmpty {
                try? fm.removeItem(at: backupDir)
            }
            Console.success("Undo completed: \(success) restored, \(originallyFailed) originally failed, \(alreadyRestored) already restored.")
        } else if failed == 0 {
            if hasNewProgress { coordinator.saveHistory() }
            Console.success("Undo progress: \(success) restored, \(originallyFailed) originally failed, \(alreadyRestored) already restored.")
        } else {
            if hasNewProgress { coordinator.saveHistory() }
            Console.error("Undo halted with \(failed) errors! Progress is saved. You can retry 'Undo' to continue.")
        }
    }
}
