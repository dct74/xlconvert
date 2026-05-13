import Foundation

// MARK: - State Coordinator (Thread-Safe with Modern Primitive)
final class RenameStateManager {
    private let lock = UnfairLock()

    private var _backupDirectory: URL?
    var backupDirectory: URL? {
        get { lock.withLock { _backupDirectory } }
        set { lock.withLock { _backupDirectory = newValue } }
    }

    private var _warnedAmbiguousHeaders = Set<String>()

    private var _renameHistory: [RenameBatch] = []

    private let historyFileURL: URL

    init(excelFile: URL) {
        let tempFilename = "ExcelConverter_\(excelFile.lastPathComponent)_\(Config.Paths.undoHistoryFilename)"
        self.historyFileURL = FileManager.default.temporaryDirectory.appendingPathComponent(tempFilename)
        loadHistory()
    }

    var isHistoryEmpty: Bool {
        lock.withLock { _renameHistory.isEmpty }
    }

    var lastBatch: RenameBatch? {
        lock.withLock { _renameHistory.last }
    }

    func appendBatch(_ batch: RenameBatch) {
        lock.withLock { _renameHistory.append(batch) }
        saveHistory()
    }

    func removeLastBatch() {
        lock.withLock { _ = _renameHistory.popLast() }
        saveHistory()
    }

    func updateLastBatch(_ update: (inout RenameBatch) -> Void) {
        lock.withLock {
            guard !_renameHistory.isEmpty else { return }
            update(&_renameHistory[_renameHistory.count - 1])
        }
    }

    func clearWarnedAmbiguousHeaders() {
        lock.withLock { _warnedAmbiguousHeaders.removeAll() }
    }

    func markAmbiguousHeaderWarned(_ header: String) {
        lock.withLock { _warnedAmbiguousHeaders.insert(header) }
    }

    func isAmbiguousHeaderWarned(_ header: String) -> Bool {
        lock.withLock { _warnedAmbiguousHeaders.contains(header) }
    }

    func saveHistory() {
        let encoder = JSONEncoder(); encoder.outputFormatting = .prettyPrinted
        do {
            let history = lock.withLock { _renameHistory }
            let data = try encoder.encode(history)
            try data.write(to: historyFileURL)
        }
        catch { Console.warning("Failed to save rename history: \(error.localizedDescription)") }
    }

    private func loadHistory() {
        guard FileManager.default.fileExists(atPath: historyFileURL.path) else { return }
        do {
            let data = try Data(contentsOf: historyFileURL)
            let batches = try JSONDecoder().decode([RenameBatch].self, from: data)
            if batches.allSatisfy({ $0.version == Config.historyVersion }) {
                lock.withLock { _renameHistory = batches }
            } else {
                Console.warning("Rename history version mismatch. History ignored.")
                try? FileManager.default.removeItem(at: historyFileURL)
            }
        } catch {
            Console.warning("Failed to load rename history: \(error.localizedDescription)")
            try? FileManager.default.removeItem(at: historyFileURL)
        }
    }
}
