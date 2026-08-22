---
type: wiki
domain: 01_计算机基础
status: reviewed
source:
  - 10_Sources/工具链/Microsoft_Install_WSL.html
created: 2026-08-15
updated: 2026-08-15
confidence: medium
review_required: true
---

# WSL 安装 Ubuntu

## 概念定义

Windows Subsystem for Linux（WSL）允许在 Windows 上直接运行 Linux 发行版（默认 Ubuntu），无需传统虚拟机或双系统。

## 安装步骤（官方 Microsoft Learn）

1. 以管理员身份打开 PowerShell（右键 → 以管理员身份运行）。
2. 执行安装命令并重启计算机：

   ```text
   wsl --install
   ```

   该命令会启用 WSL 所需功能并安装默认的 Ubuntu 发行版。

3. 首次启动新安装的 Linux 发行版时，会要求等待文件解压并创建 Linux 用户账号与密码。

## 选择其他发行版

- 查看可用的发行版：`wsl --list --online`
- 安装指定发行版：`wsl.exe --install -d <发行版名>`（例如 `wsl --install -d Ubuntu`）
- 查看已安装与版本：`wsl -l -v`
- 设置 WSL 1/2 版本：`wsl --set-version <发行版> <1|2>`

## 注意事项

- 上述命令仅适用于 WSL 尚未安装的情况；若运行后显示帮助文本，改用 `wsl --list --online` + `wsl --install -d <发行版名>`。
- 安装卡在 0.0% 时可尝试 `wsl --install --web-download -d <发行版名>`。

## 资料来源

- 10_Sources/工具链/Microsoft_Install_WSL.html（Microsoft Learn：Install WSL，https://learn.microsoft.com/windows/wsl/install）
