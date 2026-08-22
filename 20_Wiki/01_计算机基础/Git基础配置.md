---
type: wiki
domain: 01_计算机基础
status: reviewed
confidence: medium
review_required: true
source:
  - 00_Inbox/待处理文件/个人笔记/个人数据库Obsidian/Git 配置.note.pdf
  - 10_Sources/工具链/Obsidian-Git_GettingStarted.md
  - 10_Sources/工具链/Obsidian-Git_README.md
created: 2026-08-15
updated: 2026-08-17
---

# Git 基础配置

## 概念定义

Git 是版本管理工具，使用前需要先配置用户身份，并通过仓库内的 `.git` 隐藏文件夹识别仓库。在 Obsidian 中，可以通过社区插件 Obsidian-Git 把整个 Vault 变成一个 Git 仓库，在 Obsidian 内完成提交、拉取、推送与自动同步。

## 解决的问题

- 为本地笔记提供版本历史，可回看每次改动。
- 配合 GitHub 等远程仓库实现多设备同步，替代手动拷贝或仅靠网盘同步（网盘无法提供版本管理）。
- 通过自动 commit-and-sync 减少手工备份操作。

## 身份配置

执行以下命令配置 Git 用户身份：

```text
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

Windows 下配置文件位于 `C:\Users\<用户名>\.gitconfig`。Obsidian-Git 插件也提供 Commit Author 设置，移动端在插件设置的 “Authentication/Commit Author” 中填写用户名与密码/个人访问令牌。

## 识别仓库

- 手动识别仓库：文件夹内存在 `.git` 隐藏文件夹。
- Windows 默认隐藏 `.git`：文件管理器 → 查看 → 勾选【隐藏的项目】。
- Mac：`Command + Shift + .` 显示隐藏文件。
- 克隆已有远程仓库时，必须把 `.git` 一并带入 Vault 根目录，否则无法识别为仓库。

## 安装 Obsidian-Git 插件

在 Obsidian 设置中启用社区插件，浏览插件列表搜索 Git 并安装，然后在同一页面启用该插件。

## 仓库初始化

使用命令面板调用 `Initialize a new repo` 命令初始化一个新仓库；首次创建文件后，用 `Commit all changes with specific message` 命令创建第一次提交。

## 配置远程仓库

- 新建仓库推送到远程：先按官方认证指南配置认证，确保远程仓库为空，然后调用 `Push` 命令。插件会询问远程名称与 URL，远程名称填 `origin`，URL 从远程 Git 服务复制。
- 已存在远程仓库：使用 `Clone an existing remote repo` 命令克隆。克隆 URL 不是浏览器里的仓库页面地址，必须带 `.git` 后缀：
  - HTTPS：`https://github.com/<用户名>/<仓库>.git`
  - SSH：`git@github.com:<用户名>/<仓库>.git`
- 管理远程：`Edit remotes` 添加或编辑远程，`Remove remote` 删除远程，`Push` / `Pull` 手动推送与拉取。

## 自动 commit-and-sync

插件提供 `Commit-and-sync` 命令：默认设置下会提交全部改动、拉取并推送（commit all + pull + push）。插件还支持定时自动 commit-and-sync，以及 Obsidian 启动时自动拉取（auto-pull），实现接近全自动的同步。

## 认证配置

- 桌面端：HTTPS 或 SSH 认证按官方认证指南（Authentication Guide）配置。
- GitHub：需要个人访问令牌（Personal Access Token），最小权限为 metadata 读权限、contents 与 commit status 的读写权限。

## 常见误区

- 把浏览器里的仓库页面地址当作克隆 URL：克隆必须使用带 `.git` 后缀的地址。
- 移动端使用体验不稳定：Obsidian-Git 在 Android/iOS 上基于 isomorphic-git 重实现，官方明确标注“非常不稳定”，不建议在移动端使用，可考虑其他同步服务。
- 克隆时遗漏 `.git` 文件夹：会导致新目录不被识别为仓库。

## 当前覆盖边界（coverage = partial）

- 本 Wiki 当前覆盖：Git 身份配置、仓库识别、Obsidian-Git 插件安装、仓库初始化、远程仓库配置、自动 commit-and-sync 与认证。
- 不覆盖：完整 Git 教程（分支、合并、变基、子模块等）；Obsidian-Git 全部高级设置。边界以原始查询“Obsidian 的 Git 怎么配置”为准，不扩展为巨型 Git 教程。

## 资料来源

- 00_Inbox/待处理文件/个人笔记/个人数据库Obsidian/Git 配置.note.pdf
- 10_Sources/工具链/Obsidian-Git_GettingStarted.md（Obsidian-Git 官方插件文档 Getting Started）
- 10_Sources/工具链/Obsidian-Git_README.md（Obsidian-Git 官方仓库 README）
