# ExcelConverter

一个基于 Swift 的命令行工具，用于解析 Excel（.xlsx）文件并自动创建层级文件夹结构或批量重命名文件。

## 项目介绍

xlconvert用于处理国内律所常见的 IPO 项目表，底稿，控制表等结构化 Excel 表格数据。它能自动识别 IPO 项目模板文件并执行对应流程，也支持通过交互菜单选择不同的处理模式（WPSheet、ControlSheet、文件重命名等）。所有文件重命名操作均内置备份与撤销机制，确保数据安全。

## 功能特性

- **WPSheet → 文件夹** — 自动解析底稿格式的 Excel，识别章节（第X部分）、条目（一、二、三…）和数据行，生成最多6级层级文件夹
- **ControlSheet → 文件夹** — 按工作表名称创建文件夹，支持按用户指定的列规则（整列或指定单元格）创建子文件夹
- **IPO 模板自动处理** — 自动检测文件名包含"IPO项目模板"的 Excel 文件，按章-节-目三级结构创建文件夹
- **Excel 批量重命名** — 根据 Excel 单元格内容批量重命名文件，支持自定义排序、列映射和自动日期格式化
- **撤销重命名** — 通过备份目录和历史记录文件，支持完全撤销最近一次重命名操作
- **多 sheet 支持** — 自动处理 Excel 文件中的所有工作表
- **合并单元格处理** — 正确解析合并单元格的值并填充到整个区域
- **日期格式识别** — 自动识别多种日期格式（中文日期、分隔符格式、8位数字等）并统一为 YYYYMMDD
- **路径安全处理** — 自动清理文件名中的非法字符，处理 Windows 保留名称，截断超长路径
- **备份保障** — 重命名前通过硬链接备份完整目录结构，确保数据可恢复
- **跨卷检测** — 自动检测源目录与备份目录是否在同一卷，避免硬链接失败导致数据丢失

## 环境要求

- **Apple Silicon 版 macOS 14.0 (Sonoma)** 或更高版本
- **Swift 5.9** 或更高版本
- 依赖 [CoreXLSX](https://github.com/CoreOffice/CoreXLSX) (`>=0.14.0`)

## 安装步骤

### 使用 Homebrew 安装

```bash
brew install --formula dct74/tap/exconverter
```

## 使用方法

### 基本流程

1. 终端输入xlconv，根据提示 **拖拽 Excel 文件到终端**（或按回车搜索当前目录下的 `.xlsx` 文件）
2. 程序自动判断是否为 IPO 模板文件：
   - 文件名包含 `IPO项目模板` → 自动进入 IPO 处理流程
   - 否则 → 显示功能菜单
3. 在以下功能中选择：

```
┌─ Excel to Folders ────────────────────────────┐
│                                               │
│  [1] WPSheet to folders                       │
│  [2] ControlSheet to folders                  │
│  [3] Rename files using Excel                 │
│  [4] Undo rename                              │
│  [Q] Exit                                     │
└───────────────────────────────────────────────┘
```

### 各功能说明

#### 1. WPSheet → 文件夹
自动解析每一张工作表，按以下层级创建文件夹：
```
Excel文件名/
└── 工作表名/
    ├── 第一部分（章节）/
    │   ├── 一、XXX（条目）/
    │   │   ├── A列值（4级）
    │   │   │   ├── B列值 C列值（5级）
    │   │   │   │   └── D列值 E列值（6级）
    │   │   └── ...
    │   └── ...
    └── 第二部分/
        └── ...
```

固定使用 A~E 五列，自动识别"第X部分"章节头和"X、"条目。

#### 2. ControlSheet → 文件夹
为每个工作表名称创建一个文件夹，可选按列规则创建子文件夹：
- 输入列字母（如 `B`）→ 整列每个非空单元格创建一个文件夹，命名格式为 `行号-列值`
- 输入行列组合（如 `3-B`）→ 指定单元格值作为文件夹名
- 多个规则用逗号分隔（如 `B, D`）
- 直接回车 → 不创建子文件夹

```
Excel文件名/
├── Sheet1/
│   ├── 1-项目A/
│   ├── 2-项目B/
│   └── ...
├── Sheet2/
└── ...
```

#### 3. 重命名文件
- 根据 Excel 单元格内容批量重命名文件
- 文件需位于 Excel 文件同级目录或 `{Excel文件名}/` 目录下
- 文件名格式：`行号-列字母...`（如 `3-AB` 表示用第3行的 A、B 列值拼接新文件名）
- 支持交互式排序选择
- 自动备份原始文件

#### 4. 撤销重命名
- 恢复最近一次重命名操作
- 删除备份目录或保留备查

### 文件命名格式

重命名时支持的文件名格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| `行号-列字母...` | `3-AB` | 用第3行A列和B列的值拼接 |
| `纯数字` | `3` | 视为行号，扫描所有非空列 |
| `纯字母` | `AB` | 使用解析结果中的行号，读取对应列值 |

## 项目结构

```
ExcelConverter/
├── main.swift                          # 程序入口：交互菜单与流程控制
├── Package.swift                       # SPM 配置与依赖声明
│
├── Core/                               # 核心基础设施
│   ├── Config.swift                    # 全局常量、正则表达式、各限制参数
│   ├── Errors.swift                    # 错误类型（AppError）
│   └── Lock.swift                      # 基于 os_unfair_lock 的线程安全锁
│
├── Models/                             # 数据模型
│   └── Types.swift                     # MenuOption, FolderRule, RenameOperation,
│                                       # ExcelContext, ParseResult 等
│
├── State/                              # 状态管理
│   └── RenameStateManager.swift        # 线程安全的重命名历史记录与状态协调器
│
├── Utils/                              # 工具函数（enum 命名空间）
│   ├── Console.swift                   # 终端格式化输出（面板、颜色、图标）
│   ├── ConsoleIO.swift                 # 用户输入处理、Excel 上下文交互
│   ├── ExcelColumns.swift              # Excel 列字母 ↔ 列索引双向转换
│   └── StringTransform.swift           # 字符串清洗、UTF-8 截断、日期格式化
│
├── Extensions/                         # 系统类型扩展
│   └── URL+Helpers.swift               # URL 相对路径计算与 assumedBaseFolder 属性
│
├── Services/                           # 服务层
│   ├── FileSystem.swift                # 文件系统操作：目录创建、文件收集、硬链接备份
│   └── ExcelParser.swift               # Excel 读取、合并单元格解析、日期格式识别
│
├── Protocols/                          # 协议定义
│   └── FolderProcessor.swift           # FolderProcessor 协议及默认实现
│
├── Processors/                         # 业务处理器
│   ├── IPOTemplateProcessor.swift      # IPO 模板 → 章/节/目 文件夹
│   ├── WPSheetProcessor.swift          # WPSheet → 6级层级文件夹
│   ├── ControlSheetProcessor.swift     # 控制表 → 按规则创建子文件夹
│   └── FileRenameProcessor.swift       # 文件重命名与 Undo 逻辑
│
└── Facade/                             # 门面层
    └── ExcelProcessor.swift            # 统一入口，聚合所有处理器
```

### 设计原则

- **enum 命名空间** — 所有无状态工具函数均封装在 `enum` 中，避免全局污染
- **单一职责** — 每个文件聚焦一个维度（配置、模型、服务、处理器）
- **协议复用** — `FolderProcessor` 提供默认实现，三个文件夹处理器共享模板方法
- **Facade 模式** — `ExcelProcessor` 作为统一门面，主循环无需了解底层细节
- **线程安全** — `RenameStateManager` 使用 `UnfairLock` 保护所有可变状态
- **幂等备份** — 重命名前检查备份目录是否已存在且非空，防止覆盖
- **跨卷安全** — 在硬链接备份前验证源目录和备份目录在同一设备卷
