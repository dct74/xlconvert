import Foundation
import CoreXLSX

// MARK: - ControlSheet Processor
// Creates a folder per sheet name, with optional subfolders based on user-specified column rules.
// Creates a folder per sheet name, with optional subfolders based on user-specified column rules.
struct ControlSheetProcessor: FolderProcessor {
    let excelFile: URL
    let coordinator: RenameStateManager
    let readLine: () -> String?

    init(excelFile: URL, coordinator: RenameStateManager, readLine: @escaping () -> String? = { Swift.readLine() }) {
        self.excelFile = excelFile
        self.coordinator = coordinator
        self.readLine = readLine
    }

    // MARK: - Rule Parsing
    private func parseControlRuleInput(_ input: String, ctx: ExcelContext) -> [FolderRule] {
        var rules = [FolderRule]()
        for part in input.split(separator: ",") {
            let p = String(part).trimmingCharacters(in: .whitespaces)
            if let match = try? Config.Regex.singleLetter.wholeMatch(in: p),
               let colIdx = ExcelColumns.index(for: String(match.1)) {
                guard colIdx < ctx.grid[0].count else {
                    Console.warning("Column \(match.1) exceeds actual sheet width (\(ctx.grid[0].count) columns).")
                    continue
                }
                rules.append(FolderRule(
                    type: .columnAll,
                    colLetter: String(match.1).uppercased(),
                    column: ctx.grid[0][colIdx],
                    display: "Column \(String(match.1).uppercased()) (all non-empty)",
                    row: nil
                ))
            } else if let match = try? Config.Regex.rowCol.wholeMatch(in: p),
                      let colIdx = ExcelColumns.index(for: String(match.2)),
                      let r = Int(match.1) {
                guard colIdx < ctx.grid[0].count else {
                    Console.warning("Column \(match.2) exceeds actual sheet width (\(ctx.grid[0].count) columns).")
                    continue
                }
                guard r >= Config.Limits.defaultExcelStartRow,
                      r <= ctx.grid.count + Config.Limits.defaultExcelStartRow - 2 else {
                    Console.warning("\(p) (Row number out of range, valid: \(Config.Limits.defaultExcelStartRow)-\(ctx.grid.count + Config.Limits.defaultExcelStartRow - 2))")
                    continue
                }
                rules.append(FolderRule(
                    type: .singleCell,
                    colLetter: String(match.2).uppercased(),
                    column: ctx.grid[0][colIdx],
                    display: "Row \(r), Column \(String(match.2).uppercased())",
                    row: r
                ))
            } else if !p.isEmpty {
                Console.warning("\(p) (Format error, should be: column letter or row-col, e.g.: b or 3-b)")
            }
        }
        return rules
    }

    // MARK: - Collect Sheet Info & Rules
    // For each sheet: asks data start row, reads grid, then optionally collects folder rules.
    // Returns all sheets (including those without rules) so every sheet name gets a folder.
    private func collectControlRules() throws -> [(name: String, config: SheetControlConfig?, ctx: ExcelContext?)]? {
        guard let file = XLSXFile(filepath: excelFile.path) else {
            throw AppError.excelParsingError(CoreXLSXError.dataIsNotAnArchive)
        }
        let sheetNames = try ConsoleIO.getSheetNames(from: file)
        var allSheets: [(name: String, config: SheetControlConfig?, ctx: ExcelContext?)] = []

        // Print instructions
        Console.info("\nThe script will create hierarchical folders with structure: filename>Sheet name")
        Console.info("\nWhether to create subfolders under Sheet folder and rules:")
        Console.info("\n- Column letter: Create folders using all non-empty cells in this column of the Sheet, e.g. b")
        Console.info("- Row number-Column letter: Create folders using specified row-column cell in the Sheet, e.g. 3-b")
        Console.info("- Press Enter directly at rule prompt: No subfolders under Sheet folder")
        Console.info("")
        Console.warning("Note:")
        Console.info("\n- Headers must be at the top of the table")
        Console.info("- Line breaks in cells must be natural line breaks")
        Console.info("- Merged cells in the table need to be replaced with cross-row center alignment")
        Console.info("- No extra spaces or invisible characters in cells")
        Console.info("- No special characters not supported by file/folder naming in cells")

        let startRow = Config.Limits.defaultExcelStartRow

        for sheetName in sheetNames {

            let ctx: ExcelContext?
            do {
                guard let matchedName = ConsoleIO.findSheetName(in: sheetNames, target: sheetName) else {
                    Console.warning("Sheet '\(sheetName)' not found, skipping.")
                    continue
                }
                ctx = try ExcelParser.readExcelToGrid(path: excelFile, sheetName: matchedName, startRow: startRow)
            } catch {
                print()
                Console.warning("Sheet '\(sheetName)': \(error.localizedDescription) Folder will be created without subfolders.")
                allSheets.append((name: sheetName, config: nil, ctx: nil))
                continue
            }

            guard let validCtx = ctx, validCtx.grid.count > 1 else {
                // Header only or empty — create folder without subfolders
                allSheets.append((name: sheetName, config: nil, ctx: ctx))
                print()
                Console.info("Sheet '\(sheetName)' has no data rows. Folder will be created without subfolders.")
                continue
            }

            // Ask for optional subfolder rules
            var hasAddedRules = false
            while !hasAddedRules {
                print("\nSelect rule for Sheet '\(sheetName)' (press Enter to skip subfolders): ", terminator: "")
                guard let input = readLine()?.trimmingCharacters(in: .whitespaces) else { break }

                if input.isEmpty { break }

                let rules = parseControlRuleInput(input, ctx: validCtx)
                var invalidRules = [String]()

                for part in input.split(separator: ",") {
                    let p = String(part).trimmingCharacters(in: .whitespaces)
                    if let _ = try? Config.Regex.singleLetter.wholeMatch(in: p) { continue }
                    if let _ = try? Config.Regex.rowCol.wholeMatch(in: p) { continue }
                    if !p.isEmpty { invalidRules.append(p) }
                }

                if !invalidRules.isEmpty {
                    Console.warning("Invalid rules:")
                    for inv in invalidRules { Console.warning(" - \(inv) (Format error)") }
                    continue
                }

                if !rules.isEmpty {
                    allSheets.append((name: sheetName, config: SheetControlConfig(rules: rules, startRow: startRow), ctx: validCtx))
                    hasAddedRules = true
                    let summary = rules.map(\.display).joined(separator: ", ")
                    Console.success("Added rules for Sheet '\(sheetName)': \(summary)")
                } else {
                    Console.warning("No valid rules parsed. Please try again or press Enter to skip.")
                }
            }

            if !hasAddedRules {
                allSheets.append((name: sheetName, config: nil, ctx: validCtx))
                Console.info("Sheet '\(sheetName)' will be created without subfolders.")
            }
        }
        return allSheets.isEmpty ? nil : allSheets
    }

    // MARK: - Resolve Folder Components
    private func resolveFolderComponents(
        for dataIndex: Int,   // 1-based data row index (grid[r] where r = dataIndex)
        row: [String],
        rules: [FolderRule],
        paddingWidth: Int,
        grid: [[String]]
    ) -> [String]? {
        var components = [String]()

        for rule in rules {
            guard let colIdx = ExcelColumns.index(for: rule.colLetter), colIdx < row.count else { return nil }
            let excelRowNum = dataIndex + 1

            if rule.type == .singleCell {
                // Only process matching row
                guard let ruleRow = rule.row, dataIndex + 1 == ruleRow else { return nil }
            }

            // Get cell value
            let cellValue = colIdx < row.count ? row[colIdx] : ""
            let trimmed = cellValue.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty else { return nil }
            let cleanValue = StringTransform.sanitize(trimmed)
            guard !cleanValue.isEmpty else { return nil }

            let folderName: String
            if rule.type == .columnAll {
                folderName = String(format: "%0\(paddingWidth)d-", excelRowNum) + cleanValue
            } else {
                folderName = cleanValue
            }

            components.append(folderName)
        }

        return components.isEmpty ? nil : components
    }

    // MARK: - Process Sheet
    // Always creates a folder for the sheet name.
    // Only creates subfolders when rules are specified and grid data is available.
    private func processSheet(
        name: String,
        config: SheetControlConfig?,
        ctx: ExcelContext?,
        topFolder: URL,
        totalCount: inout Int
    ) {
        let sheetFolder = topFolder.appendingPathComponent(StringTransform.sanitize(name))
        guard FileSystem.createFolderSafely(at: sheetFolder, count: &totalCount) else { return }

        // Subfolders only when rules + data are available
        guard let config = config, !config.rules.isEmpty, let ctx = ctx, ctx.grid.count > 1 else { return }

        // padding_width = len(str(len(df) + 1)) = len(str(grid.count))
        let paddingWidth = String(ctx.grid.count).count

        // data starts at grid[1]
        for r in 1..<ctx.grid.count {
            guard let components = resolveFolderComponents(
                for: r,
                row: ctx.grid[r],
                rules: config.rules,
                paddingWidth: paddingWidth,
                grid: ctx.grid
            ) else { continue }

            let depthCount = components.count
            var buildPath = sheetFolder
            for comp in components {
                buildPath = buildPath.appendingPathComponent(comp)
                FileSystem.safeCreateDirectory(at: buildPath)
            }
            totalCount += depthCount
        }
    }

    // MARK: - Process (main flow)
    func process() throws {
        guard let allSheets = try collectControlRules() else { return }
        var totalCount = 0
        guard let topFolder = createBaseFolder(createdCount: &totalCount) else {
            throw AppError.abort("Failed to create top-level folder.")
        }

        for (sheetName, config, ctx) in allSheets {
            processSheet(name: sheetName, config: config, ctx: ctx, topFolder: topFolder, totalCount: &totalCount)
        }
        print()
        Console.success("Created \(totalCount) folders.")
    }
}
