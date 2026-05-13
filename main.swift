import Foundation

// MARK: - IPO auto-detection (matches Python is_ipo_template)
private func isIPOTemplate(_ url: URL) -> Bool {
    let filename = url.lastPathComponent.lowercased()
    return filename.contains("ipo项目模板")
}

// MARK: - Main menu (matches Python show_menu, without IPO option since it's auto-detected)
private func showMenu(readLine: @escaping () -> String?) -> String {
    print()
    Console.panel("Excel to Folders", """
    [1] WPSheet to folders
    [2] ControlSheet to folders
    [3] Rename files using Excel
    [4] Undo rename
    [Q] Exit
    """)
    while true {
        print("Select option: ", terminator: "")
        guard let rawInput = readLine() else {
            Console.info("EOF detected, exiting.")
            return MenuOption.exit.rawValue
        }
        let choice = rawInput.trimmingCharacters(in: .whitespaces).lowercased()
        guard MenuOption.isValid(choice) else {
            Console.error("Invalid option. Please try again.")
            continue
        }
        return choice
    }
}

// MARK: - Main entry (matches Python main.py flow)
if let excelFile = ConsoleIO.getExcelFile() {
    do {
        // IPO auto-detection (matches Python: if is_ipo_template(excel_file) → process and exit)
        if isIPOTemplate(excelFile) {
            Console.info("\nIPO template file detected: \(excelFile.lastPathComponent)")
            Console.rule()
            Console.info("\nProcessing IPO template: \(excelFile.lastPathComponent)")
            let coordinator = RenameStateManager(excelFile: excelFile)
            let processor = IPOTemplateProcessor(excelFile: excelFile, coordinator: coordinator, readLine: { Swift.readLine() })
            try processor.process()
            exit(0)
        }

        // Not IPO template — show menu (matches Python else branch)
        let coordinator = RenameStateManager(excelFile: excelFile)
        let mainReadLine: () -> String? = { Swift.readLine() }
        let processor = ExcelProcessor(excelFile: excelFile, coordinator: coordinator, readLine: mainReadLine)
        var shouldExit = false
        while !shouldExit {
            let choice = showMenu(readLine: mainReadLine)
            switch choice {
            case MenuOption.wpSheet.rawValue:
                try processor.processWPSheet()
                Console.success("WPSheet processing completed successfully.")
                Console.info("\nExiting program...")
                shouldExit = true
            case MenuOption.controlSheet.rawValue:
                try processor.processControlSheet()
            case MenuOption.renameFiles.rawValue:
                try processor.processRenameFiles()
            case MenuOption.undo.rawValue:
                processor.undoLastBatch()
            case MenuOption.exit.rawValue:
                // Prompt to delete backup directory if it exists
                let excelName = StringTransform.sanitize(excelFile.deletingPathExtension().lastPathComponent)
                let backupDir = excelFile.deletingLastPathComponent().appendingPathComponent("\(excelName)\(Config.Paths.backupPrefix)")
                if FileManager.default.fileExists(atPath: backupDir.path) {
                    print("Delete backup directory? (y/n, default: n): ", terminator: "")
                    if readLine()?.trimmingCharacters(in: .whitespaces).lowercased() == Config.InputKeys.yes {
                        try? FileManager.default.removeItem(at: backupDir)
                        Console.info("Backup directory deleted.")
                    } else {
                        Console.info("Backup directory preserved: \(backupDir.lastPathComponent)")
                    }
                }
                shouldExit = true
            default:
                break
            }
        }
    } catch {
        Console.error("Error: \(error.localizedDescription)")
        exit(1)
    }
}
