import Foundation
import CoreXLSX

// MARK: - Namespace: ConsoleIO
enum ConsoleIO {
    static func getSheetNames(from file: XLSXFile) throws -> [String] {
        guard let workbook = try file.parseWorkbooks().first else {
            throw AppError.abort("No workbooks found in the Excel file.")
        }
        // Use workbook.sheets.items to preserve natural sheet order.
        // parseWorksheetPathsAndNames returns order from the .rels file which can be reversed.
        return workbook.sheets.items.compactMap(\.name)
    }
    static func findSheetName(in sheets: [String], target: String) -> String? {
        sheets.first { $0.caseInsensitiveCompare(target) == .orderedSame }
    }
    static func calculatePaddingWidth(forDataCount count: Int) -> Int {
        if count <= 0 { return 1 }; return String(count).count
    }
    static func askForStartRow(sheetName: String, readLine: @escaping () -> String? = { Swift.readLine() }) -> Int {
        print("Sheet '\(sheetName)': Data starts from which row? (Default: \(Config.Limits.defaultExcelStartRow), min: \(Config.Limits.minDataStartRow)):", terminator: " ")
        if let input = readLine()?.trimmingCharacters(in: .whitespaces), !input.isEmpty {
            if let r = Int(input), r >= Config.Limits.minDataStartRow { return r } else { Console.warning("Invalid input. Using default.") }
        }
        return Config.Limits.defaultExcelStartRow
    }
    static func askForColumnIndex(prompt: String, ctx: ExcelContext, readLine: @escaping () -> String? = { Swift.readLine() }) -> Int? {
        while true {
            print("\(prompt) (A-Z):", terminator: " ")
            guard let input = readLine()?.trimmingCharacters(in: .whitespaces).uppercased(), !input.isEmpty else { return nil }
            if let letter = input.first, letter.isLetter, let idx = ExcelColumns.index(for: String(letter)) {
                if idx < (ctx.grid.first?.count ?? 0) { return idx } else { Console.warning("Column \(letter) is out of bounds for this sheet.") }
            } else { Console.warning("Invalid column letter.") }
        }
    }

    static func resolveExcelContext(for excelFile: URL, targetSheetName: String? = nil, readLine: @escaping () -> String? = { Swift.readLine() }) throws -> ExcelContext {
        if let fileSize = try? FileManager.default.attributesOfItem(atPath: excelFile.path)[.size] as? Int64,
           fileSize > Config.Limits.largeFileWarningThresholdBytes {
            Console.warning("Excel file is large (\(fileSize / 1024 / 1024)MB). Parsing may consume significant memory.")
        }

        guard let file = XLSXFile(filepath: excelFile.path) else {
            throw AppError.excelParsingError(CoreXLSXError.dataIsNotAnArchive)
        }
        let sheetNames = try ConsoleIO.getSheetNames(from: file)
        let sheetName: String
        if let target = targetSheetName {
            sheetName = target
        } else if sheetNames.count == 1 {
            sheetName = sheetNames[0]
        } else {
            print("Available sheets: \(sheetNames.joined(separator: ", "))")
            print("Enter sheet name (default: \(Config.Defaults.sheetName)):", terminator: " ")
            sheetName = readLine()?.trimmingCharacters(in: .whitespaces) ?? Config.Defaults.sheetName
        }
        let startRow = ConsoleIO.askForStartRow(sheetName: sheetName, readLine: readLine)
        guard let matchedName = ConsoleIO.findSheetName(in: sheetNames, target: sheetName) else { throw AppError.abort("Sheet '\(sheetName)' not found in the Excel file.") }
        return try ExcelParser.readExcelToGrid(path: excelFile, sheetName: matchedName, startRow: startRow)
    }
    static func getExcelFile(readLine: @escaping () -> String? = { Swift.readLine() }, fileManager: FileManager = .default) -> URL? {
        print("Drag and drop an Excel file here, or press Enter to search current directory:")
        guard let input = readLine()?.trimmingCharacters(in: .whitespaces) else { return nil }
        var pathStr = input.replacingOccurrences(of: "'", with: "").replacingOccurrences(of: "\"", with: "").replacingOccurrences(of: "\\ ", with: " ")
        pathStr = (pathStr as NSString).standardizingPath
        let url = URL(fileURLWithPath: pathStr)
        if url.pathExtension.lowercased() == "xlsx" && fileManager.fileExists(atPath: url.path) { return url }
        if let files = try? fileManager.contentsOfDirectory(at: URL(fileURLWithPath: fileManager.currentDirectoryPath), includingPropertiesForKeys: nil), let xlsx = files.first(where: { $0.pathExtension.lowercased() == "xlsx" }) { return xlsx }
        Console.error("No Excel file found.")
        return nil
    }
}
