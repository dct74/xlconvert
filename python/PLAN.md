# 方案二：Python 移植规划（exconverter-py）

> 目标：用 Python 重写现有 Swift CLI（2198 行），实现**行为对齐**的移植，
> 而非"重做"。成功标准 = 同一份样本 xlsx 上，输出文件夹结构 / 重命名结果与 Swift 版一致。

## 0. 环境事实（已实测）

- Python 3.14.7（Homebrew `/opt/homebrew/bin/python3`），pip 26.2.1
- **openpyxl 3.1.5 已安装**（纯 Python，无编译依赖 → 打包友好）
- uv 可用；pytest 未安装（阶段 0 时装）
- 无现有测试样本 xlsx、无测试 target —— **回归样本需采集**（见 §6）

## 1. 依赖清单

### 运行时（唯一强依赖）
| 包 | 版本 | 用途 | 说明 |
|---|---|---|---|
| `openpyxl` | >= 3.1 | .xlsx 读取 | 已装 3.1.5。纯 Python。 |

不引入 python-calamine（rust 高性能备选）：虽快，但引入平台产物与额外语义差异，移植期弊大于利；若后续大文件性能不足再评估。

### 开发 / 测试
| 包 | 用途 |
|---|---|
| `pytest` | 单测 + 回归 |
| （无） | fixture xlsx 用 openpyxl 的**写入**能力生成，无需额外依赖 |

### 分发（延后决策，阶段 5 再定）
| 方案 | 说明 |
|---|---|
| `uv` + script / `pipx` | 最简单，命令行工具分发友好 |
| Homebrew formula | 现有 `dct74/tap/exconverter` 可加 python + openpyxl 依赖 |
| PyInstaller | 单文件；openpyxl 纯 Python 打包友好，但需处理签名/公证 —— 非必需 |

## 2. Swift → Python 模块映射

| Swift | Python | 移植策略 |
|---|---|---|
| `Core/Config.swift` | `config.py` | 常量直搬（limits/paths/keys/保留名/正则） |
| `Core/Errors.swift` | `errors.py` | `AppError` → `XlError(Exception)`，保留同文案 |
| `Core/Lock.swift` | **删除** | Python 单线程 CLI 无此需要（GIL） |
| `Models/Types.swift` | `models.py` | `FolderRule/SheetControlConfig/RenameOperation/RenameBatch/ExcelContext/FileMeta/ParseResult`；`MenuOption` 简化为常量 |
| `State/RenameStateManager.swift` | `state.py` | 无锁版；历史 JSON 读写逻辑照搬 |
| `Utils/Console.swift` | `console.py` | ANSI 颜色 + CJK 显示宽度 + panel |
| `Utils/ConsoleIO.swift` | `console_io.py` | 交互提示、`resolve_excel_context`、`get_excel_file` |
| `Utils/ExcelColumns.swift` | `excel_columns.py` | 列字母↔索引（26 列上限） |
| `Utils/StringTransform.swift` | `string_transform.py` | sanitize / UTF-8 截断 / 日期格式化 |
| `Extensions/URL+Helpers.swift` | `path_utils.py` | `relative_path` / `assumed_base_folder` |
| `Services/ExcelParser.swift` | `excel_parser.py` | 读网格 + 合并单元格填充 + 日期（见 §3 陷阱） |
| `Services/FileSystem.swift` | `file_system.py` | 目录创建/文件收集/硬链接备份/跨卷检测 |
| `Protocols/FolderProcessor.swift` | `folder_processor.py` | 默认实现改为基类/组合函数 |
| `Processors/WPSheetProcessor.swift` | `processors/wp_sheet.py` | 逐行逻辑直搬（最精细，见 §5） |
| `Processors/ControlSheetProcessor.swift` | `processors/control_sheet.py` | 交互问询改注入 `input_fn` |
| `Processors/IPOTemplateProcessor.swift` | `processors/ipo.py` | 章-节-目三层 + 合并 map |
| `Processors/FileRenameProcessor.swift` | `processors/rename.py` | 文件名解析/排序/备份/撤销 |
| `Facade/ExcelProcessor.swift` | `facade.py` | 门面调度 |
| `main.swift` | `__main__.py` + `cli.py` | 菜单循环 + IPO 自动检测 |

### 目录结构（新目录 `python/`，与 Swift 包同仓共存不冲突）
```
python/
├── PLAN.md
├── pyproject.toml            # [project] exconverter, entry xlconv
├── exconverter/
│   ├── __init__.py
│   ├── __main__.py           # 入口
│   ├── cli.py                # 菜单/主流程
│   ├── config.py errors.py models.py state.py
│   ├── console.py console_io.py excel_columns.py string_transform.py path_utils.py
│   ├── excel_parser.py file_system.py folder_processor.py facade.py
│   └── processors/{__init__,wp_sheet,control_sheet,ipo,rename}.py
└── tests/
    ├── conftest.py           # fixture 生成器（openpyxl 写）
    └── test_*.py
```

## 3. 关键行为对齐点（openpyxl 探针实证，2026-09 验证）

Swift 用 CoreXLSX 读**原始值**，语义链：sharedString 索引 → 文本；日期格式 cell → `"yyyy/M/d"` 字符串；其它 → 原始字符串。
openpyxl 是**类型化读取**，已自动处理 sharedString / 日期。移植时必须复刻 Swift 的**最终字符串形态**：

1. **日期 cell**：openpyxl 自动转 `datetime`（探针：`46037`+`yyyy/m/d` → `datetime(2026,1,15)`）。
   Swift 转成 `yyyy/M/d`（**无前导零**，如 `"2026/1/15"`）→ 移植需 `dt.strftime` 自拼去零；
   后续 rename 用 `format_date_string` 再转 `YYYYMMDD`，文件夹流程用 `sanitize`（`/` 属非法字符被剔除）。
   → 统一入口函数 `_serial_to_string`，保证全流程形态一致。
2. **MergedCell**：openpyxl 合并区域仅左上角有值，其余为 `MergedCell`（无 `is_date`，访问 `number_format`/`value` 受限）。
   → 用 `ws.merged_cells.ranges` 复刻 Swift 的左上值填充逻辑；读取时对 MergedCell 跳过属性访问。
3. **数字 cell**：openpyxl 数值是 `int/float`；CoreXLSX 是原始字符串（如 `"46037"`）。
   → 数值转字符串需复刻 XML 原始形态：整数值不带 `.0`（`repr(int)` 语义），避免 `"46037.0"` 污染文件名。
4. **RichText**：Swift 拼接 `<r><t>` runs；openpyxl 已合并为纯文本 → 语义等价，无需处理。
5. **read_only 大文件**：openpyxl `read_only=True` 时合并单元格/样式支持受限 → 默认常规模式，文件超大（>50MB 警告阈值沿用）时再评估。

## 4. 逻辑直搬注意点

- **枚举上限都沿用** `config.py`：列 26、行 10000、文件夹 5000、合并区 10000、路径 1024、组件 255、唯一名 9999、排序尝试 3。
- **正则用 Python 语法重写**，但**语义不变**（`#/.../#` → 编译 raw string）。
- **交互全部走 `input_fn` 注入**（默认 `builtins.input`），与 Swift `readLine` 注入同思路 → 可测试。
- **硬链接备份**：`os.link`；跨卷检测用 `os.stat().st_dev` 比较，与 Swift `lstat st_dev` 等价。
- **撤销逻辑**：temp-restore 三步 move + 批记录 JSON 更新，逐行照搬。
- **排序**：Swift `sorted` + 显式行号 tie-break；Python `sorted` 稳定 + 行号 key，结果等价（注意统一 `.lower()` 比较键）。

## 5. WPSheet 移植注意（行为最精细处）

`process_sheet_hierarchy` 状态机逐行照搬：section/number 正则识别、`processingNumber` 门控、
A 逻辑 vs 无-A 逻辑分叉、合并单元格值延续（`currentAValue/currentBValue`）、level4 去重（`lastCreatedAValue`）、
`row.count < 3` / blank 行 / 各 guard 的跳过与 warning 文案 —— **每处 `continue` 条件都要保留**。

## 6. 回归验证策略（最大风险源）

- 从实际使用采集 **1-2 个脱敏样本 xlsx**（IPO 模板 + 普通底稿各一）；没有就用 openpyxl 构造覆盖以下特征的 fixture：
  合并单元格、日期序列号/中文日期/8 位日期、共享字符串、richText、Windows 保留名、超长路径、多 sheet。
- **并行验证法**：同一输入分别跑 Swift 版与 Python 版，比对 `find` 输出的目录树 / 重命名后文件名清单。
- pytest 用 fixture 固化关键用例（去重、no-A 分叉、撤销恢复等）。

## 7. 实施阶段与验证标准

| 阶段 | 内容 | 验证标准 |
|---|---|---|
| **0 骨架** | pyproject、包结构、config/errors/console/excel_columns/path_utils/string_transform 纯搬移 | `pytest` 冒烟 + 模块可导入 |
| **1 读取层** | `excel_parser` + `file_system`（不含备份）| fixture 读入网格与 Swift `readExcelToGrid` 输出一致 |
| **2 文件夹处理器** | WPSheet / ControlSheet / IPO | 与 Swift 版在样本上产出相同目录树 |
| **3 重命名+备份撤销** | rename + state + 硬链接备份 + undo | 重命名清单一致；undo 后目录恢复原状 |
| **4 CLI 入口** | `__main__` + 菜单 + IPO 自动检测 + 端到端 | 全交互流可跑通，错误分支文案对齐 |
| **5 分发**（可选） | pyproject entry + README | 安装后可执行 |

> **实施状态（2026-09）**：阶段 0-4 已完成。34 个 pytest 用例全绿、ruff 0.16.6 全绿。
> 阶段 2/3 的关键功能已与 Swift 二进制（`.build/debug/exconverter`）在共享字符串 fixture 上做差分验证，目录树 / 重命名结果逐字节一致。
> 遗留：阶段 5 分发（已可通过 `uv pip install .` + `xlconv` 使用）；真实 IPO/底稿脱敏样本回归尚未采集。

## 8. Token / 费用预算（参照实测校准：本会话读全项目+小改 ≈ 5-7 万 token）

| 阶段 | 合计 token 预估 | 说明 |
|---|---|---|
| 0 骨架 | 0.05–0.09M | 纯搬移，少往返 |
| 1 读取层 | 0.11–0.20M | 含探针式调测、fixture |
| 2 文件夹处理器 | 0.16–0.26M | 与 Swift 逐行对照，最费读取 |
| 3 重命名+撤销 | 0.20–0.33M | 最复杂模块 |
| 4 CLI + 端到端 | 0.11–0.20M | 回归比对轮次多 |
| **合计** | **~0.6–1.1M** | 中位约 0.8M |

费用（V4-Flash，空闲时段、缓存全未命中的上界 ≈ 输入 80% + 输出 20%）：约 **1.5–3.5 元**；
若输入缓存部分命中更低；高峰时段翻倍。墙钟约 **2–4 小时**（顺利）。

**执行策略建议**：按阶段推进，每阶段结束看一次实际 token 用量外推，避免一次性盲跑。
