// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "exconverter",
    defaultLocalization: "en",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/CoreOffice/CoreXLSX.git", from: "0.14.0"),
    ],
    targets: [
        .executableTarget(
            name: "exconverter",
            dependencies: ["CoreXLSX"],
            path: ".",
            exclude: ["README.md"],
            sources: [
                "main.swift",
                "Core/Config.swift",
                "Core/Errors.swift",
                "Core/Lock.swift",
                "Extensions/URL+Helpers.swift",
                "Facade/ExcelProcessor.swift",
                "Models/Types.swift",
                "Processors/ControlSheetProcessor.swift",
                "Processors/FileRenameProcessor.swift",
                "Processors/IPOTemplateProcessor.swift",
                "Processors/WPSheetProcessor.swift",
                "Protocols/FolderProcessor.swift",
                "Services/ExcelParser.swift",
                "Services/FileSystem.swift",
                "State/RenameStateManager.swift",
                "Utils/Console.swift",
                "Utils/ConsoleIO.swift",
                "Utils/ExcelColumns.swift",
                "Utils/StringTransform.swift",
            ]
        )
    ]
)
