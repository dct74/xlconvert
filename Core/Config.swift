import Foundation

// MARK: - Configuration & Constants
enum Config {
    enum Limits {
        static let headerRow = 1
        static let minDataStartRow = headerRow + 1
        static let defaultExcelStartRow = minDataStartRow
        static let maxExcelColumns = 26
        static let maxExcelRows = 10000
        static let maxFoldersToCreate = 5000
        static let maxMergeCellArea = 10000
        static let maxPathComponentLength = 255
        static let yearMin = 1900
        static let yearMax = 2100
        static let largeFileWarningThresholdMB = 50
        static var largeFileWarningThresholdBytes: Int { largeFileWarningThresholdMB * 1024 * 1024 }
        static let maxUniquePathAttempts = 9999
        static let maxSortAttempts = 3
    }
    enum Paths {
        static let maxLength = 1024
        static let backupPrefix = "_backup_"
        static let undoHistoryFilename = ".rename_history.json"
    }
    enum Display {
        static let panelLineWidth = 50
        static let maxTitleDisplayChars = 20
    }
    enum Regex {
        static let invalidChars = #/[<>:"\/\\|?*]/#
        static let chineseSection = #/^第[一二三四五六七八九十]+部分/#
        static let chineseNumber = #/^[一二三四五六七八九十]+、/#
        static let dateTimeSuffix = #/\s+(\d{2}:\d{2}:\d{2}|\d{6})$/#
        static let chineseDate = #/^(\d{4})年(\d{1,2})月(\d{1,2})日$/#
        static let eightDigit = #/^\d{8}$/#
        static let singleLetter = #/^([a-zA-Z])$/#
        static let rowCol = #/^(\d+)-([a-zA-Z])$/#
        static let filenamePrefix = #/^(\d+)(?:-([a-zA-Z]+))?/#
        static let folderNamePattern = #/^(\d+)-(.+)$/#
        static let lettersOnly = #/^[a-zA-Z]+$/#
        static let multiSpace = #/\s+/#
        static let dateSeparator = #/[-/.]/#
    }
    enum InputKeys {
        static let yes = "y"
        static let no = "n"
        static let quit = "q"
        static let undo = "u"
    }
    enum Defaults {
        static let sheetName = "Sheet1"
        static let defaultColumnPrefix = "Column_"
        static let tempRestorePrefix = ".temp_restore_"
    }

    static let dsStore = ".DS_Store"
    static let historyVersion = 1

    static let reservedWindowsNames: Set<String> = [
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    ]
}
