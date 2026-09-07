# Windows 运行说明（源码直跑，不打包）

exconverter 是普通 Python 包，**不打包 exe 也完全够用**。在 Windows 上从源码直接运行即可，
好处是改动 `.py` 后下次运行自动生效，无需重新安装。

## 1. 一次性准备（目标 Windows 机器）

```powershell
# 安装 Python 3.10+（官网 python.org，勾选 "Add Python to PATH"）
python --version

# 安装唯一依赖（openpyxl 是纯 Python，跨平台）
pip install openpyxl
```

## 2. 运行

把本 `python/` 目录拷到 Windows，进入该目录后：

```powershell
cd python
python -m exconverter
```

随后按提示拖入 Excel 文件 / 按回车搜索当前目录 .xlsx。

### 想少打字？加个 `xlconv.bat`

在 `python/` 目录放一个 `xlconv.bat`，内容一行：

```bat
@python -m exconverter %*
```

之后双击或用 `xlconv` 即可进入菜单。

## 3. 平台注意点

| 事项 | 说明 |
|---|---|
| **路径** | 全用 `os.path` / `os.sep`，无 POSIX 分支，Windows 盘符、反斜杠均正常 |
| **硬链接备份** | 重命名前会 `os.link` 硬链接备份。**仅 NTFS 且同一卷可用**。若输入/输出在 U 盘(exFAT/FAT32)、网络盘等，备份会失败并中止（打印 CRITICAL）—— 这是设计行为，避免数据丢失 |
| **跨卷检测** | 备份目录默认建在 Excel 同目录，天然同卷；若被搬走会因 `st_dev` 不同而拒绝 |
| **拖拽路径** | `get_excel_file` 会剥引号、`\ `（macOS 遗留），Windows 输入普通路径不受影响 |

## 4. 为什么"改源码不用重装"

只有当你把包 `pip install`（拷进 site-packages）后，`xlconv` 入口点才读**已安装副本**，此时改源码需重装。
而 `python -m exconverter` 是从当前目录读源码 —— 改完即生效。所以：

- **日常开发**：用 `python -m exconverter`（推荐）
- **想全局调用命令**：才需要 `pip install .` + `xlconv`，且每次改码重装

## 5. 测试（可选）

```powershell
pip install pytest
cd python
python -m pytest
```
