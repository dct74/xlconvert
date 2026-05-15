import Foundation

// MARK: - Namespace: FileSystem
enum FileSystem {
    static func getRelativePath(from baseDir: URL, to fileURL: URL) -> String { fileURL.relativePath(from: baseDir) }

    static func validatePathLength(_ url: URL) -> Bool {
        let pathLength = url.path.utf8.count
        guard pathLength > Config.Paths.maxLength else { return true }
        Console.error("Path length (\(pathLength) bytes) exceeds safe limit (\(Config.Paths.maxLength)): \(url.path)")
        return false
    }

    @discardableResult static func safeCreateDirectory(at url: URL) -> Bool {
        guard validatePathLength(url) else { return false }
        do { try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true); return true }
        catch let error as NSError where error.domain == NSCocoaErrorDomain && error.code == NSFileWriteFileExistsError {
            var isDir: ObjCBool = false
            if FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue {
                return true
            }
            Console.error("Failed to create directory \(url.path): A file already exists at this path.")
            return false
        }
        catch { Console.error("Failed to create directory \(url.path): \(error.localizedDescription)"); return false }
    }

    @discardableResult static func createFolderSafely(at url: URL, count: inout Int) -> Bool {
        guard count < Config.Limits.maxFoldersToCreate else {
            Console.error("Reached safe limit of \(Config.Limits.maxFoldersToCreate) folders. Aborting creation.")
            return false
        }
        guard validatePathLength(url) else { return false }

        if safeCreateDirectory(at: url) {
            count += 1
            return true
        }
        return false
    }

    static func collectFiles(from excelPath: URL) -> [URL] {
        let fm = FileManager.default; let excelDir = excelPath.deletingLastPathComponent()
        let excelFilename = StringTransform.sanitize(excelPath.deletingPathExtension().lastPathComponent)
        let startDir = excelDir.appendingPathComponent(excelFilename)
        let dirToScan = fm.fileExists(atPath: startDir.path) ? startDir : excelDir

        let expectedBackupDir = excelDir.appendingPathComponent("\(excelFilename)\(Config.Paths.backupPrefix)")
        let backupPathPrefix = expectedBackupDir.path + "/"

        guard let enumerator = fm.enumerator(at: dirToScan, includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        var files = [URL]()
        for case let fileURL as URL in enumerator {
            guard let values = try? fileURL.resourceValues(forKeys: [.isRegularFileKey]),
                  values.isRegularFile == true else { continue }

            let name = fileURL.lastPathComponent
            if name == Config.dsStore || name == excelPath.lastPathComponent { continue }

            let filePath = fileURL.path
            if filePath == expectedBackupDir.path || filePath.hasPrefix(backupPathPrefix) { continue }

            files.append(fileURL)
        }
        return files
    }

    static func initBackupDirectory(excelFile: URL, coordinator: RenameStateManager) throws {
        let excelFilename = StringTransform.sanitize(excelFile.deletingPathExtension().lastPathComponent)
        let dirName = "\(excelFilename)\(Config.Paths.backupPrefix)"
        let backupURL = excelFile.deletingLastPathComponent().appendingPathComponent(dirName)

        if FileManager.default.fileExists(atPath: backupURL.path) {
            if let contents = try? FileManager.default.contentsOfDirectory(atPath: backupURL.path), contents.isEmpty {
                try FileManager.default.removeItem(at: backupURL)
                Console.info("Cleaned up empty residual backup directory.")
            } else {
                throw AppError.backupFailed("Backup directory already exists and is not empty: \(dirName). Please remove it manually.")
            }
        }

        do {
            try FileManager.default.createDirectory(at: backupURL, withIntermediateDirectories: true)
            coordinator.backupDirectory = backupURL
            Console.success("Backup directory created: \(backupURL.lastPathComponent)")
        } catch { throw AppError.backupFailed("Cannot create backup directory: \(error.localizedDescription)") }
    }

    static func backupFolderStructure(sourceFolders: [URL], to backupDir: URL, baseDir: URL) -> Bool {
        let fm = FileManager.default
        for folder in sourceFolders {
            let relativePath = getRelativePath(from: baseDir, to: folder)
            let destFolderURL = backupDir.appendingPathComponent(relativePath)
            guard safeCreateDirectory(at: destFolderURL) else { return false }
            guard let enumerator = fm.enumerator(at: folder, includingPropertiesForKeys: [.isRegularFileKey]) else { return false }
            for case let fileURL as URL in enumerator {
                if fileURL.lastPathComponent == Config.dsStore { continue }
                let fileRelPath = getRelativePath(from: folder, to: fileURL)
                let destFileURL = destFolderURL.appendingPathComponent(fileRelPath)
                do {
                    try fm.createDirectory(at: destFileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
                    try fm.linkItem(at: fileURL, to: destFileURL)
                } catch { Console.error("CRITICAL: Failed to hard-link backup \(fileURL.lastPathComponent): \(error.localizedDescription)"); return false }
            }
        }
        return true
    }

    private static func getDeviceID(for url: URL) throws -> dev_t {
        var s = stat()
        guard url.withUnsafeFileSystemRepresentation({ fsRep in lstat(fsRep, &s) == 0 }) else { throw AppError.fileSystemError(NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: "Failed to verify volume for \(url.path)"])) }
        return s.st_dev
    }

    static func ensureSameVolume(sourceDir: URL, backupDir: URL) throws {
        do {
            let srcDev = try getDeviceID(for: sourceDir); let bakDev = try getDeviceID(for: backupDir)
            if srcDev != bakDev { throw AppError.abort("CRITICAL: Source directory and backup directory are on different volumes.\nHard linking is not supported across volumes, and copying large files may fail or cause data loss.\nPlease ensure the Excel file and the target folders are on the same drive.") }
        } catch let error as AppError { throw error }
        catch { throw AppError.abort("Failed to verify volume information: \(error.localizedDescription)") }
    }

    static func getUniqueFilePath(originalURL: URL) -> URL {
        let fm = FileManager.default
        let baseName = originalURL.deletingPathExtension().lastPathComponent
        let ext = originalURL.pathExtension
        var targetURL = originalURL

        if !fm.fileExists(atPath: targetURL.path) { return targetURL }

        for counter in 1...Config.Limits.maxUniquePathAttempts {
            let newName = ext.isEmpty ? "\(baseName)_\(counter)" : "\(baseName)_\(counter).\(ext)"
            targetURL = originalURL.deletingLastPathComponent().appendingPathComponent(newName)
            if !fm.fileExists(atPath: targetURL.path) { return targetURL }
        }

        let uuidName = ext.isEmpty ? "\(baseName)_\(UUID().uuidString)" : "\(baseName)_\(UUID().uuidString).\(ext)"
        return originalURL.deletingLastPathComponent().appendingPathComponent(uuidName)
    }
}
