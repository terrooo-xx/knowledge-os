# Phase 22-D：Control Center 固定布局（App Shell）

- 日期：2026-08-18
- 类型：Control Center 布局 / CSS 改造
- 约束：不修改 RAG / Retrieval / Reranker / Judge / Evidence / Evaluation / Governance / Wiki / Source / Baseline / API

## 一、问题
顶部 Header 和左侧导航随整个页面滚动；滚动容器是 body，main 未独立滚动。

## 二、改造（纯 CSS App Shell，无 DOM 重构）
- html,body height:100%；body flex column + overflow:hidden
- header flex:0 0 auto（固定顶部）；.layout flex:1 min-height:0（占满剩余）
- nav flex:0 0 170px + overflow-y:auto（固定左侧，可独立滚动）
- main flex:1 min-width/min-height:0 + overflow-y:auto（唯一滚动容器）+ ::after 底部留白
- render() 包装内 main.scrollTop=0（切换视图回顶部）

## 三、真实验证（live 8765）
Dashboard / Activity / RAG Evaluation / Guide 均：windowScrollY=0、body 不可滚动、main 独立滚动、headerTop=0、navTop=83；深滚后 Header 按钮可用；1440×900 与 1920×1080 自适应；无 JS 异常。

## 四、测试
- 新增 test_control_center_layout.py（11 条）
- **412/412 通过**

## 五、学习记录
- 测试 CSS 规则时，selector 必须锚定到规则行首（`(?<=\n)\s*selector\s*{`），否则会误匹配 `html, body` / `header .row` 等组合选择器
- 断言「无 height 硬编码」时注意 min-height/max-height 包含子串 "height:"，要用负向断言排除

## 六、最终状态
- Header/Sidebar 固定、Main 独立滚动、Body 不滚动、无双滚动、Guide/RAG Evaluation 兼容、Resize 正常：全部 PASS
- Regression：412/412；RAG 修改：NO；Governance 修改：NO
