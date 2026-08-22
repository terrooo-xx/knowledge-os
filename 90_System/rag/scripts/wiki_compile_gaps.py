"""Wiki Compilation CLI (Phase 17, stage 1 audit).

Reads gaps.yaml + source_acquisition.yaml + benchmark records, builds the
Gap -> Knowledge Requirements -> Source Traceability -> NEW/EXPAND decision ->
Query Coverage Matrix -> likely_recoverable plan, and writes:

    - 90_System/rag/evaluation/wiki_compilation.yaml
    - 40_Outputs/RAG Evaluation/wiki_compilation/audit_report.md

Read-only wrt the knowledge base (no Wiki writes here).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAG_DIR))

import yaml  # noqa: E402
from rag_engine.wiki_compilation import (  # noqa: E402
    ACTION_EXPAND, ACTION_NEW,
    decide_wiki_action, render_wiki_compilation_audit, save_compilation,
    validate_coverage_matrix, validate_requirements,
)

DEFAULT_GAPS = RAG_DIR / "evaluation" / "gaps.yaml"
DEFAULT_OUT = RAG_DIR / "evaluation" / "wiki_compilation.yaml"
EVAL_ROOT = VAULT_ROOT / "40_Outputs" / "RAG Evaluation"


# ---------------------------------------------------------------- audit data
# Knowledge Requirements 由人工/审计判定，逐条带 source_location（可追溯）。
# covered=true 仅当 Source 中确有依据。

WIKI_TASKS = {
    "gap_freertos_config_debug": [
        {
            "task_id": "wt_freertos_stack_overflow",
            "title": "FreeRTOS 栈溢出检查",
            "wiki_action": ACTION_NEW,
            "wiki_target_path": "20_Wiki/04_FreeRTOS/FreeRTOS栈溢出检查.md",
            "source": {
                "title": "FreeRTOS Reference Manual V8.2.1",
                "local_path": "10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf",
                "page": "274-275", "section": "Stack overflow checking",
                "url": "https://www.freertos.org/media/2025/FreeRTOS_Reference_Manual_V8.2.1.pdf",
            },
            "query_ids": ["q_freertos_stack_overflow"],
            "requirements": [
                {"requirement_id": "so_req_1", "query": "q_freertos_stack_overflow",
                 "required_fact": "configCHECK_FOR_STACK_OVERFLOW 配置常量选择是否启用检测",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "274"},
                 "covered": True, "notes": "Which (if any) option is used is configured by configCHECK_FOR_STACK_OVERFLOW"},
                {"requirement_id": "so_req_2", "query": "q_freertos_stack_overflow",
                 "required_fact": "启用时必须提供栈溢出钩子 vApplicationStackOverflowHook(TaskHandle_t*, signed char*)",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "274"},
                 "covered": True, "notes": "Hook 原型 Listing 201"},
                {"requirement_id": "so_req_3", "query": "q_freertos_stack_overflow",
                 "required_fact": "方法1（=1）快但可能漏检；方法2（=2）额外校验栈尾 n 字节模式",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "275"},
                 "covered": True, "notes": "Method one/two 区别"},
                {"requirement_id": "so_req_4", "query": "q_freertos_stack_overflow",
                 "required_fact": "检测到溢出时内核调用 hook，传入任务句柄与任务名",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "274"},
                 "covered": True, "notes": "pxTask / pcTaskName 参数"},
                {"requirement_id": "so_req_5", "query": "q_freertos_stack_overflow",
                 "required_fact": "CubeMX 中该配置项的具体位置/验证方法",
                 "source_location": {},
                 "covered": False, "notes": "Source 未明确 CubeMX 界面位置；需 CubeMX 文档/人工确认"},
            ],
        },
        {
            "task_id": "wt_freertos_task_notification",
            "title": "FreeRTOS 任务通知",
            "wiki_action": ACTION_EXPAND,
            "wiki_target_path": "20_Wiki/04_FreeRTOS/FreeRTOS任务通知.md",
            "source": {
                "title": "FreeRTOS Reference Manual V8.2.1",
                "local_path": "10_Sources/FreeRTOS/FreeRTOS_Reference_Manual_V8.2.1.pdf",
                "page": "82-86", "section": "RTOS task notifications",
                "url": "https://www.freertos.org/media/2025/FreeRTOS_Reference_Manual_V8.2.1.pdf",
            },
            "query_ids": ["q_freertos_task_notification"],
            "requirements": [
                {"requirement_id": "tn_req_1", "query": "q_freertos_task_notification",
                 "required_fact": "任务通知是轻量级任务间通信，比信号量高效；可替代部分信号量/事件组",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "82"},
                 "covered": True, "notes": "eSetBits 可用作更快的事件组替代"},
                {"requirement_id": "tn_req_2", "query": "q_freertos_task_notification",
                 "required_fact": "启用条件 configUSE_TASK_NOTIFICATIONS（默认启用，设 0 每任务省 8B）",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "82"},
                 "covered": True, "notes": "FreeRTOSConfig.h 中设置"},
                {"requirement_id": "tn_req_3", "query": "q_freertos_task_notification",
                 "required_fact": "发送 API xTaskNotify/xTaskNotifyAndQuery + eAction 五种动作 + 返回值 pdPASS/pdFAIL",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "82,85"},
                 "covered": True, "notes": "eSetBits/eIncrement/eSetValueWithOverwrite/eSetValueWithoutOverwrite/eNoAction"},
                {"requirement_id": "tn_req_4", "query": "q_freertos_task_notification",
                 "required_fact": "简单场景用 xTaskNotifyGive 替代二进制/计数信号量",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "82"},
                 "covered": True, "notes": "simpler xTaskNotifyGive()"},
                {"requirement_id": "tn_req_5", "query": "q_freertos_task_notification",
                 "required_fact": "接收 API xTaskNotifyWait / ulTaskNotifyTake",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "86"},
                 "covered": True, "notes": "example 中提及读取方式"},
                {"requirement_id": "tn_req_6", "query": "q_freertos_task_notification",
                 "required_fact": "典型调用示例（Listing 54：eSetBits/eNoAction/eSetValueWithOverwrite/WithoutOverwrite）",
                 "source_location": {"title": "FreeRTOS Reference Manual V8.2.1", "page": "86"},
                 "covered": True, "notes": "Example use of xTaskNotify()"},
            ],
        },
    ],
    "gap_stm32_cubemx_pwm": [
        {
            "task_id": "wt_stm32_pwm",
            "title": "STM32 定时器 PWM 输出",
            "wiki_action": ACTION_NEW,
            "wiki_target_path": "20_Wiki/03_STM32/STM32定时器PWM输出.md",
            "source": {
                "title": "STM32 cross-series timer overview (AN4013 Rev 14)",
                "local_path": "10_Sources/STM32/STM32_CrossSeries_Timer_Overview_AN4776.pdf",
                "page": "16-17", "section": "2.5 Timer in PWM mode",
                "url": "https://www.st.com/resource/en/application_note/dm00042534-stm32-cross-series-timer-overview-stmicroelectronics.pdf",
            },
            "query_ids": ["q_stm32_timer_pwm"],
            "requirements": [
                {"requirement_id": "pwm_req_1", "query": "q_stm32_timer_pwm",
                 "required_fact": "PWM 输出配置步骤（引脚 CCS/CCxP → OCxM 选 PWM1/2 → ARR/CCRx → 预装载 → 计数模式 → CCxE → CEN）",
                 "source_location": {"title": "STM32 cross-series timer overview", "page": "17"},
                 "covered": True, "notes": "AN4013 §2.5 配置步骤 1-7"},
                {"requirement_id": "pwm_req_2", "query": "q_stm32_timer_pwm",
                 "required_fact": "频率/占空比关系：CK_CNT=CK_PSC/(PSC+1)；CCx update rate=CK_CNT/ARR；CCRx 决定脉冲宽度",
                 "source_location": {"title": "STM32 cross-series timer overview", "page": "16"},
                 "covered": True, "notes": "output compare timing 公式"},
                {"requirement_id": "pwm_req_3", "query": "q_stm32_timer_pwm",
                 "required_fact": "边沿对齐（up/down）与中心对齐（CMS!=00）计数模式",
                 "source_location": {"title": "STM32 cross-series timer overview", "page": "17"},
                 "covered": True, "notes": "PWM edge/center aligned"},
                {"requirement_id": "pwm_req_4", "query": "q_stm32_timer_pwm",
                 "required_fact": "CubeMX 界面配置项（Channel=PWM Generation 等）",
                 "source_location": {},
                 "covered": False, "notes": "AN4013 为寄存器级；CubeMX 界面配置见现有 reviewed Wiki（不可 AI 修改），需人工合并确认"},
            ],
        },
    ],
    "gap_git_config": [
        {
            "task_id": "wt_git_config",
            "title": "Obsidian Git 配置",
            "wiki_action": ACTION_EXPAND,
            "wiki_target_path": "20_Wiki/01_计算机基础/Git基础配置.md",
            "source": {
                "title": "Obsidian-Git Getting Started（官方插件文档）",
                "local_path": "10_Sources/工具链/Obsidian-Git_GettingStarted.md",
                "page": None, "section": "Create new local repository / For existing remote repository",
                "url": "https://publish.obsidian.md/git-doc/Start+here",
            },
            "query_ids": ["q_git_config"],
            "requirements": [
                {"requirement_id": "git_req_1", "query": "q_git_config",
                 "required_fact": "git user.name / user.email 身份配置",
                 "source_location": {"title": "Git 配置.note.pdf"},
                 "covered": True, "notes": "本地 PDF 唯一实质内容；Getting Started 移动端 Commit Author 亦涉及"},
                {"requirement_id": "git_req_2", "query": "q_git_config",
                 "required_fact": "识别仓库（.git 文件夹、显示隐藏文件）",
                 "source_location": {"title": "Git 配置.note.pdf"},
                 "covered": True, "notes": "Windows/Mac 显示隐藏文件；Getting Started 提示克隆时保留 .git"},
                {"requirement_id": "git_req_3", "query": "q_git_config",
                 "required_fact": "Obsidian-Git 插件安装与启用（社区插件 → Browse → Git → Enable）",
                 "source_location": {"title": "Obsidian-Git Getting Started（官方插件文档）",
                                     "section": "Start with existing remote repository"},
                 "covered": True, "notes": "Enable community plugins. Browse plugins to install Git. Enable Git"},
                {"requirement_id": "git_req_4", "query": "q_git_config",
                 "required_fact": "仓库初始化与远程配置：Initialize a new repo → Push 添加 origin；或 Clone existing remote repo（https/ssh URL 带 .git 后缀）；Edit remotes",
                 "source_location": {"title": "Obsidian-Git Getting Started（官方插件文档）",
                                     "section": "Create new local repository / For existing remote repository"},
                 "covered": True, "notes": "origin 名称 + push URL；克隆 URL https://github.com/<user>/<repo>.git 或 git@github.com:<user>/<repo>.git"},
                {"requirement_id": "git_req_5", "query": "q_git_config",
                 "required_fact": "自动同步：Commit-and-sync（commit all + pull + push）；自动定时同步与启动自动 pull；常用命令",
                 "source_location": {"title": "Obsidian-Git plugin README（官方仓库）",
                                     "section": "Key Features / Available Commands"},
                 "covered": True, "notes": "README：Automatic commit-and-sync、Auto-pull on Obsidian startup；Commit-and-sync 命令"},
                {"requirement_id": "git_req_6", "query": "q_git_config",
                 "required_fact": "认证：桌面 HTTPS/SSH（指向 Authentication Guide）；GitHub 个人访问令牌最小权限（metadata 读 + contents/commit status 读写）",
                 "source_location": {"title": "Obsidian-Git Getting Started（官方插件文档）",
                                     "section": "Start with existing remote repository / Authentication"},
                 "covered": True, "notes": "移动端必须用 PAT；桌面端 HTTPS/SSH 详见官方 Authentication 指南"},
            ],
            "coverage_note": "Source 已补齐（官方 Getting Started + README），覆盖插件安装/仓库初始化/远程/认证/自动同步；Wiki 保持 draft + review_required，不自动 approve",
        },
    ],
    "gap_wsl_ubuntu": [
        {
            "task_id": "wt_wsl_ubuntu",
            "title": "WSL 安装 Ubuntu",
            "wiki_action": ACTION_NEW,
            "wiki_target_path": "20_Wiki/01_计算机基础/WSL安装Ubuntu.md",
            "source": {
                "title": "Install WSL - Microsoft Learn",
                "local_path": "10_Sources/工具链/Microsoft_Install_WSL.html",
                "page": None, "section": "Install WSL command",
                "url": "https://learn.microsoft.com/windows/wsl/install",
            },
            "query_ids": ["q_wsl_ubuntu"],
            "requirements": [
                {"requirement_id": "wsl_req_1", "query": "q_wsl_ubuntu",
                 "required_fact": "wsl --install 安装 WSL + 默认 Ubuntu，需管理员 PowerShell + 重启",
                 "source_location": {"title": "Install WSL - Microsoft Learn"},
                 "covered": True, "notes": "wsl --install"},
                {"requirement_id": "wsl_req_2", "query": "q_wsl_ubuntu",
                 "required_fact": "选择发行版 wsl --install -d <Distro> / wsl --list --online",
                 "source_location": {"title": "Install WSL - Microsoft Learn"},
                 "covered": True, "notes": "wsl.exe --install -d"},
                {"requirement_id": "wsl_req_3", "query": "q_wsl_ubuntu",
                 "required_fact": "首次启动创建 Linux 用户账号与密码；wsl -l -v 查看版本",
                 "source_location": {"title": "Install WSL - Microsoft Learn"},
                 "covered": True, "notes": "Set up your Linux user info"},
            ],
        },
    ],
}


def _load_latest_records() -> dict:
    runs = sorted([d for d in (EVAL_ROOT / "runs").iterdir()
                   if d.is_dir() and (d / "meta.json").exists()])
    if not runs:
        return {}
    meta = json.loads((runs[-1] / "meta.json").read_text(encoding="utf-8"))
    records = {}
    for line in (runs[-1] / "evaluation_records.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            records[r["query_id"]] = r
    return records


def build_compilation(gaps: list, wiki_status: dict) -> list:
    records = _load_latest_records()
    out = []
    for g in gaps:
        if g.get("priority") not in ("P0", "P1"):
            continue
        tasks = WIKI_TASKS.get(g["id"]) or []
        entries = []
        for t in tasks:
            reqs = t["requirements"]
            missing = [r["required_fact"] for r in reqs if not r["covered"]]
            cm_rows = []
            for qid in t["query_ids"]:
                before = records.get(qid) or {}
                req_for_q = [r for r in reqs if r["query"] == qid]
                covered = sum(1 for r in req_for_q if r["covered"])
                likely = "true" if missing == [] else ("unknown" if len(missing) <= len(req_for_q) // 2 else "false")
                cm_rows.append({
                    "query_id": qid,
                    "before": {"final_status": (before.get("final") or {}).get("status"),
                               "source": (before.get("execution") or {}).get("source"),
                               "failure": before.get("failure_type")},
                    "wiki_version": "draft",
                    "requirements": {r["requirement_id"]: ("covered" if r["covered"] else "missing")
                                     for r in req_for_q},
                    "expected_after": {"likely_recoverable": likely},
                })
            entries.append({
                "task_id": t["task_id"], "title": t["title"],
                "wiki_action": t["wiki_action"], "wiki_target_path": t["wiki_target_path"],
                "source": t["source"], "query_ids": t["query_ids"],
                "requirements": reqs, "coverage_matrix": cm_rows,
                "missing_knowledge": missing,
                "coverage_note": t.get("coverage_note", ""),
            })
        if not entries:
            continue
        out.append({"gap_id": g["id"], "priority": g["priority"], "title": g["title"],
                    "wiki_tasks": entries})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki Compilation audit CLI")
    parser.add_argument("--gaps", default=str(DEFAULT_GAPS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--audit-out", default=str(EVAL_ROOT / "wiki_compilation"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    gaps = yaml.safe_load(Path(args.gaps).read_text(encoding="utf-8")) or []
    wiki_status = {}
    for p in (VAULT_ROOT / "20_Wiki").rglob("*.md"):
        wiki_status[p.relative_to(VAULT_ROOT).as_posix()] = "draft"

    comp = build_compilation(gaps, wiki_status)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    payload = {"created": now, "gaps": comp}
    save_compilation(args.out, payload)

    audit_dir = Path(args.audit_out)
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "wiki_compilation.yaml").write_text(
        Path(args.out).read_text(encoding="utf-8"), encoding="utf-8")
    audit_md = render_wiki_compilation_audit(comp, {"generated_at": now})
    (audit_dir / "audit_report.md").write_text(audit_md, encoding="utf-8")

    problems = []
    for g in comp:
        for t in g["wiki_tasks"]:
            problems += validate_requirements(t["requirements"])
            problems += validate_coverage_matrix(t["coverage_matrix"])

    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems,
                          "gaps": [{"gap_id": g["gap_id"], "tasks": len(g["wiki_tasks"]),
                                    "likely": [t["coverage_matrix"][0]["expected_after"]["likely_recoverable"]
                                               for t in g["wiki_tasks"] if t["coverage_matrix"]]}
                                   for g in comp]}, ensure_ascii=False, indent=2))
    else:
        print(f"compilation: {args.out}")
        print(f"audit: {audit_dir / 'audit_report.md'}")
        print(f"P0/P1 gaps planned: {len(comp)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
