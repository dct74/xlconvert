import Foundation

// MARK: - Folder Processing Protocol (Reduces inter-processor duplication)
protocol FolderProcessor {
    var excelFile: URL { get }
    var coordinator: RenameStateManager { get }
    var readLine: () -> String? { get }
}

extension FolderProcessor {
    func resolveAndDisplayContext(targetSheetName: String? = nil) throws -> ExcelContext {
        let ctx = try ConsoleIO.resolveExcelContext(for: excelFile, targetSheetName: targetSheetName, readLine: readLine)
        Console.info("Available headers: \(ctx.grid[0].map { $0.isEmpty ? "\"\"" : $0 }.joined(separator: " | "))")
        return ctx
    }

    func createBaseFolder(sheetName: String? = nil, createdCount: inout Int) -> URL? {
        let topFolder = excelFile.assumedBaseFolder
        guard FileSystem.createFolderSafely(at: topFolder, count: &createdCount) else {
            return nil
        }
        if let name = sheetName {
            let sheetFolder = topFolder.appendingPathComponent(StringTransform.sanitize(name))
            guard FileSystem.createFolderSafely(at: sheetFolder, count: &createdCount) else {
                return nil
            }
            return sheetFolder
        }
        return topFolder
    }
}
