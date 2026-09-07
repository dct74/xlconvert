# exconverter (Python)

Python 移植版 —— 解析 Excel（IPO 模板、底稿、控制表）自动创建层级文件夹结构，或批量重命名文件。
对 Swift 原版（本仓库根目录）做**行为对齐**移植。

## 快速开始

### 开发 / 日常运行（推荐，改源码即生效，无需重装）

本项目是普通 Python 包，**从源码目录直接运行即可**，改完 `.py` 下次运行自动生效：

```bash
cd python
python -m exconverter          # 需要 Python 3.10+ 和 openpyxl
```

只需安装一个依赖（纯 Python，跨平台）：

```bash
pip install openpyxl
```

若没有命令行入口习惯，也可以加一个 `xlconv.bat`（Windows）/ `xlconv` 脚本（macOS），
内容就是 `python -m exconverter`，省去记忆命令。

### 仅当想装成可全局调用的 `xlconv` 命令时

这会把代码**复制**到 site-packages，之后改动源码需重新安装才会同步：

```bash
cd python
uv pip install --python .venv/bin/python .
.venv/bin/xlconv
```

> 日常开发建议用上一种（`python -m exconverter`），避免反复重装。

## 测试

```bash
cd python
python -m pytest                # 57 用例全绿
ruff check .                    # lint
```

## 功能（与 Swift 版一致）

| 模式 | 说明 |
|---|---|
| WPSheet → 文件夹 | 识别「第X部分」章节 /「X、」条目，A-E 五列最多 6 级层级 |
| ControlSheet → 文件夹 | 每工作表名建文件夹，按列规则（整列 `B` 或 `3-B`）建子文件夹 |
| IPO 自动处理 | 文件名含 `ipo项目模板` 自动走章-节-目三层 |
| 重命名文件 | 按 Excel 单元格批量重命名 + 硬链接备份 + 撤销 |

## 重要移植注意

- **测试 fixture 必须用共享字符串 xlsx**（`tests/xlsx_util.py`）：openpyxl 默认写
  `inlineStr`，而 Swift 的 CoreXLSX 读不了 inlineStr；真实 Excel/WPS 用共享字符串表。
  因此 openpyxl 直接生成的 xlsx 不能作为对标 Swift 的 oracle。
- **rename 历史**持久化在系统 temp，按 Excel 文件名键控——复用同名 Excel 会载入陈旧历史；
  测试应使用唯一文件名。

## 结构

```
exconverter/
├── cli.py __main__.py        # 入口：菜单 + IPO 自动检测
├── config.py errors.py       # 常量 / 错误
├── console.py console_io.py  # 终端样式 / 交互
├── excel_parser.py           # openpyxl 读取层
├── file_system.py            # 目录/硬链接备份/跨卷
├── models.py state.py        # 数据模型 / 历史状态
├── string_transform.py       # 清洗/截断/日期归一
├── excel_columns.py path_utils.py
├── folder_processor.py
└── processors/               # wp_sheet control_sheet ipo rename
```

对标 Swift 源文件映射见 `PLAN.md` §2。
