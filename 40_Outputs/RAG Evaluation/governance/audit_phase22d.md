# Phase 22-D：Control Center 固定布局实施报告

- 日期：2026-08-18
- 范围：只改 Control Center 布局与 CSS（+必要的滚动复位）；不修改 RAG / Retrieval / Reranker / Judge / Evidence / Evaluation / Governance / Wiki / Source / Baseline / API

## 1. 审计结果
- 当前 DOM：`<body> <header>(.row + .statusbar + #flash) <div class="layout"> <nav> <main id="main"> </div> </body>`（无 #app 包装，但结构天然是 header + body 两段）
- 当前滚动容器：**body**（`.layout { min-height: calc(100vh - 110px) }`，main `overflow:auto` 但无固定高度 → 不独立滚动，整个页面随 body 滚动）
- Header / nav 无固定，随页面滚动

## 2. Layout 改造（App Shell，纯 CSS，无 DOM 重构）
```css
html, body { height: 100%; }
body { display: flex; flex-direction: column; overflow: hidden; }
header { flex: 0 0 auto; }
.layout { flex: 1 1 auto; min-height: 0; display: flex; }
nav { flex: 0 0 170px; overflow-y: auto; }
main { flex: 1 1 auto; min-width: 0; min-height: 0; overflow-y: auto; overflow-x: auto; }
main::after { content: ''; display: block; height: 28px; }   /* 底部留白 */
```
- 真正的滚动容器只有 main；body 不滚动（无浏览器级滚动条 → 无双滚动）
- 未硬编码 margin-top / height；未来 Header 高度变化不影响布局

## 3. Header 固定
- 作为 App Shell 第一行（flex:0 0 auto），始终可见；实测 headerTop=0（滚动任意深度）

## 4. Sidebar 固定
- 左侧 nav 固定宽度（flex:0 0 170px），主内容滚动不动；导航过长时可独立滚动（overflow-y:auto）；实测 navTop=83=headerHeight

## 5. Main 独立滚动
- main 为唯一滚动容器（overflow-y:auto + min-height:0）；切换视图时 main.scrollTop 归零（render 包装内一行复位）

## 6. 双滚动处理
- body overflow:hidden → 浏览器滚动条消失；只有 main 垂直滚动条；实测 document.scrollingElement.scrollHeight == clientHeight（body 不可滚动）

## 7. Guide 兼容
- Guide Section Routing / 后退前进 / 刷新 / 深链 / 搜索全部未动；Guide 内容在 main 内独立滚动（sticky 目录仍在 main 滚动容器内工作）

## 8. RAG Evaluation 兼容
- RAG Evaluation 长页面在 main 内正常滚动到底（mainScrollTop=2037px），Header/Sidebar 固定

## 9. Responsive
- 桌面优先；1440×900 与 1920×1080 实测：main 填满剩余高度、headerTop=0、sidebar top=header 高、body 不滚动；窄屏既有响应式（Guide 目录抽屉）保留

## 10. 浏览器验证（真实 headless Chrome CDP，live 8765）
| 场景 | 结果 |
|---|---|
| Dashboard 滚动到底 | windowScrollY=0、body 不可滚动、main.scrollTop=177、headerTop=0、navTop=83 | PASS |
| Activity 大量内容滚动 | main.scrollTop=955、header/sidebar 固定 | PASS |
| RAG Evaluation 滚动到底 | main.scrollTop=2037、header/sidebar 固定 | PASS |
| Guide → Workflow → Wiki Review | main 独立滚动（workflow=710px）；wiki-review 内容短无需滚动 | PASS |
| 深滚后 Header 按钮 | 同步知识库按钮 visible + clickable | PASS |
| Resize 1440×900 → 1920×1080 | mainH 自适应、headerTop=0、navTop=83、body 不滚动 | PASS |
| JS 异常 | 0 | PASS |

## 11. 测试
- 新增 `test_control_center_layout.py`（11 条：body/app-shell 高度 / header 固定 / sidebar 固定+独立滚动 / main overflow / body overflow（无双滚动）/ 无高度硬编码 / Guide 路由 / RAG Evaluation / Sidebar 导航 / resize flex 自适应 / node 语法）
- **412/412 全部通过**（401 + 11 新增）

## 12. 最终状态
```text
Header 固定：PASS
Sidebar 固定：PASS
Main 独立滚动：PASS
Body 不滚动：PASS
无双滚动：PASS
Guide：PASS
RAG Evaluation：PASS
Browser：PASS
Regression：412/412
RAG 修改：NO
Governance 修改：NO
```
