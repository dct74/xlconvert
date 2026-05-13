import Foundation

// MARK: - Core Processor (Facade)
struct ExcelProcessor {
    let excelFile: URL
    let coordinator: RenameStateManager
    let readLine: () -> String?

    init(excelFile: URL, coordinator: RenameStateManager, readLine: @escaping () -> String? = { Swift.readLine() }) {
        self.excelFile = excelFile
        self.coordinator = coordinator
        self.readLine = readLine
    }

    func processIPOTemplate() throws { try IPOTemplateProcessor(excelFile: excelFile, coordinator: coordinator, readLine: readLine).process() }
    func processWPSheet() throws { try WPSheetProcessor(excelFile: excelFile, coordinator: coordinator, readLine: readLine).process() }
    func processControlSheet() throws { try ControlSheetProcessor(excelFile: excelFile, coordinator: coordinator, readLine: readLine).process() }
    func processRenameFiles() throws { try FileRenameProcessor(excelFile: excelFile, coordinator: coordinator, readLine: readLine).process() }
    func undoLastBatch() { FileRenameProcessor(excelFile: excelFile, coordinator: coordinator, readLine: readLine).undoLastBatch() }
}
