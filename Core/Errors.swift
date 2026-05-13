import Foundation

// MARK: - Error Handling
enum AppError: Error, LocalizedError {
    case backupFailed(String)
    case abort(String)
    case fileSystemError(Error)
    case excelParsingError(Error)
    var errorDescription: String? {
        switch self {
        case .backupFailed(let msg), .abort(let msg): return msg
        case .fileSystemError(let error): return "File system error: \(error.localizedDescription)"
        case .excelParsingError(let error): return "Excel parsing error: \(error.localizedDescription)"
        }
    }
}
