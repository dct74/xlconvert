# ExcelConverter — 模块化 Swift 项目

## 目录结构

```
ExcelConverter/
├── main.swift                          # 程序入口
│
├── Core/                               # 核心基础设施
│   ├── Lock.swift                      # UnfairLock 线程安全锁
│   ├── Config.swift                    # 全局常量与配置（enum 命名空间）
│   └── Errors.swift                    # 错误类型定义
│
├── Models/                             # 数据模型
│   └── Types.swift                     # MenuOption、FolderRule、RenameOperation 等
│
├── State/                              # 状态管理
│   └── RenameStateManager.swift        # 线程安全的重命名历史与状态协调器
│
├── Utils/                              # 工具函数（enum 命名空间）
│   ├── Console.swift                   # 终端输出与 UI 面板
│   ├── ConsoleIO.swift                 # 用户输入与 Excel 上下文解析
│   ├── ExcelColumns.swift              # Excel 列字母/索引转换
│   └── StringTransform.swift           # 字符串清洗、截断、日期格式化
│
├── Extensions/                         # 扩展
│   └── URL+Helpers.swift               # URL 相对路径与辅助属性
│
├── Services/                           # 服务层
│   ├── FileSystem.swift                # 文件系统操作、备份、硬链接
│   └── ExcelParser.swift               # Excel 读取与网格解析
│
├── Protocols/                          # 协议定义
│   └── FolderProcessor.swift           # FolderProcessor 协议及默认实现
│
├── Processors/                         # 业务处理器
│   ├── IPOTemplateProcessor.swift      # IPO 模板 → 文件夹
│   ├── WPSheetProcessor.swift          # WPSheet → 文件夹
│   ├── ControlSheetProcessor.swift     # 控制表 → 文件夹
│   └── FileRenameProcessor.swift       # 文件重命名（含 Undo）
│
└── Facade/                             # 门面层
    └── ExcelProcessor.swift            # 统一入口，聚合所有处理器
```

## 设计原则

- **enum/struct 命名空间**：所有无状态工具函数均封装在 `enum` 中（如 `Config`、`Console`、`StringTransform`、`FileSystem`、`ExcelParser`），避免全局污染，同时保持调用语义清晰。
- **单一职责**：每个文件只负责一个维度（配置、模型、服务、处理器等）。
- **协议复用**：`FolderProcessor` 协议通过扩展提供 `resolveAndDisplayContext()` 和 `createBaseFolder()` 的默认实现，三个文件夹处理器共享同一份逻辑。
- **Facade 模式**：`ExcelProcessor` 作为统一门面，主循环只需调用门面方法，无需了解底层处理器细节。
- **线程安全**：`RenameStateManager` 使用 `UnfairLock` 保护可变状态。

## 编译说明

将所有 `.swift` 文件加入同一 Target 即可编译（需依赖 `CoreXLSX`）：

```bash
swift build
```

或 Xcode 中新建 Command Line Tool，将所有文件拖入项目。
