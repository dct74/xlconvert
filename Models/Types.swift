import Foundation

// MARK: - Menu
enum MenuOption: String, CaseIterable {
    case wpSheet = "1", controlSheet = "2", renameFiles = "3", undo = "4", exit = "q"
    private static let validSet = Set(Self.allCases.map(\.rawValue))
    static func isValid(_ val: String) -> Bool { validSet.contains(val.lowercased()) }
}

// MARK: - Folder Rules
enum RuleType { case columnAll, singleCell }
struct FolderRule { let type: RuleType; let colLetter: String; let column: String; let display: String; let row: Int? }
struct SheetControlConfig { let rules: [FolderRule]; let startRow: Int }

// MARK: - Rename Operations
enum OperationStatus: String, Codable { case success, failed, skipped, pending }
struct RenameOperation: Codable {
    let oldRelativePath: String; let newRelativePath: String; let relativeBackupPath: String
    var status: OperationStatus; let errorMessage: String?; var isRestored: Bool = false
}
struct RenameBatch: Codable {
    let version: Int
    var operations: [RenameOperation]
    let backupDirName: String

    init(operations: [RenameOperation], backupDirName: String) {
        self.version = Config.historyVersion
        self.operations = operations
        self.backupDirName = backupDirName
    }

    enum CodingKeys: String, CodingKey {
        case version, operations, backupDirName
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        version = try container.decodeIfPresent(Int.self, forKey: .version) ?? Config.historyVersion
        operations = try container.decode([RenameOperation].self, forKey: .operations)
        backupDirName = try container.decode(String.self, forKey: .backupDirName)
    }
}

// MARK: - Excel Context
struct ExcelContext {
    let filePath: URL; let sheetName: String; let startRow: Int; let headers: [String: [Int]]; let grid: [[String]]
}

// MARK: - File Metadata
enum FileNamePartType { case digitsOnly, lettersOnly, mixed, empty }
struct FileMeta { let row: Int; let colLetters: [String]; let ext: String; let directory: URL; let originalFilename: String }

// MARK: - ParseResult
struct ParseResult {
    let sheetName: String?
    let rowNumber: Int?
    let baseFolderName: String?
    let isValid: Bool

    static func from(folderPath: URL) -> ParseResult {
        let folderName = folderPath.lastPathComponent
        if let match = try? Config.Regex.folderNamePattern.wholeMatch(in: folderName),
           let row = Int(match.1) {
            return ParseResult(
                sheetName: folderPath.deletingLastPathComponent().lastPathComponent,
                rowNumber: row,
                baseFolderName: String(match.2),
                isValid: true
            )
        }
        return ParseResult(sheetName: nil, rowNumber: nil, baseFolderName: nil, isValid: false)
    }
}
