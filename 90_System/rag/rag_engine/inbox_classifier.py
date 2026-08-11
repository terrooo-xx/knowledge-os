"""Inbox classification: project vs wiki, new vs update vs duplicate."""
from __future__ import annotations

DOMAIN_KEYWORDS = {
    "01_计算机基础": ["CPU", "寄存器", "进制", "操作系统", "中断"],
    "02_嵌入式基础": ["LED", "电容", "阻抗", "电源", "编码器", "IMU", "MPU-6050", "电机驱动", "LDO", "DC-DC", "AS5600", "锂电池"],
    "03_STM32": ["STM32", "USART", "UART", "DMA", "时钟", "CubeMX", "GPIO", "定时器", "TIM"],
    "04_FreeRTOS": ["FreeRTOS", "任务", "调度", "队列", "信号量", "互斥"],
    "05_通信协议": ["串口", "RS232", "CAN", "SPI", "I2C", "PPM", "S.Bus", "SBUS", "Modbus", "EtherCAT"],
    "06_控制理论": ["PID", "控制", "反馈", "稳定", "传递函数"],
    "07_无人机飞控": ["无人机", "飞控", "四旋翼", "PX4", "Betaflight"],
    "08_移动机器人": ["移动机器人", "底盘", "AGV", "舵轮", "轮式"],
    "09_ROS2": ["ROS2", "ROS 2", "话题", "节点", "Nav2", "SLAM"],
}

PROJECT_RULES = [
    ("无人机飞控", ["无人机", "飞控", "四旋翼", "IMU", "气压计", "磁力计", "ESC"]),
    ("移动底盘控制器", ["移动底盘", "底盘控制器", "舵轮", "AGV", "工控机", "伺服驱动器"]),
]


def detect_project(text: str) -> str | None:
    lowered = text.lower()
    for project, keywords in PROJECT_RULES:
        if any(keyword.lower() in lowered for keyword in keywords):
            return project
    return None


def detect_domain(text: str) -> str:
    lowered = text.lower()
    best_domain = "01_计算机基础"
    best_score = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        if score >= best_score:
            best_score = score
            best_domain = domain
    return best_domain


def classify_text(
    text: str,
    cfg: dict,
    embedder=None,
    store=None,
    source: str = "",
    document_type: str = "",
) -> dict:
    inbox_cfg = cfg.get("inbox", {})
    threshold = float(inbox_cfg.get("similarity_threshold", 0.82))
    update_threshold = float(inbox_cfg.get("update_threshold", 0.65))

    if not text.strip():
        return {
            "source": source,
            "document_type": document_type,
            "topic": "unknown",
            "action": "keep_raw",
            "domain": None,
            "project": None,
            "matched_wiki": None,
            "similarity": 0.0,
            "reason": "无法提取文本，保留为原始资料",
            "target": None,
        }

    project = detect_project(text)
    if project:
        return {
            "source": source,
            "document_type": document_type,
            "topic": project,
            "action": "project_update",
            "domain": None,
            "project": project,
            "matched_wiki": None,
            "similarity": 0.0,
            "reason": "内容属于具体项目知识",
            "target": f"30_Projects/{project}/",
        }

    domain = detect_domain(text)
    if embedder is not None and store is not None and store.count() > 0:
        vector = embedder.embed([text[:1000]])[0]
        hits = store.search(vector, 1)
        if hits:
            best = hits[0]
            score = float(best["score"])
            matched = (best.get("metadata") or {}).get("source", "")
            if score >= threshold:
                return {
                    "source": source,
                    "document_type": document_type,
                    "topic": domain,
                    "action": "no_new_wiki",
                    "domain": domain,
                    "project": None,
                    "matched_wiki": matched,
                    "similarity": round(score, 4),
                    "reason": "已有知识已经覆盖主要内容",
                    "target": matched,
                }
            matched_domain = str((best.get("metadata") or {}).get("domain", ""))
            if score >= update_threshold and (not matched_domain or matched_domain == domain):
                return {
                    "source": source,
                    "document_type": document_type,
                    "topic": domain,
                    "action": "update_wiki",
                    "domain": domain,
                    "project": None,
                    "matched_wiki": matched,
                    "similarity": round(score, 4),
                    "reason": "新资料包含已有 Wiki 可能缺失的内容",
                    "target": matched,
                }
            return {
                "source": source,
                "document_type": document_type,
                "topic": domain,
                "action": "create_wiki",
                "domain": domain,
                "project": None,
                "matched_wiki": matched,
                "similarity": round(score, 4),
                "reason": "知识库不存在完整对应 Wiki",
                "target": f"20_Wiki/{domain}/",
            }

    return {
        "source": source,
        "document_type": document_type,
        "topic": domain,
        "action": "create_wiki",
        "domain": domain,
        "project": None,
        "matched_wiki": None,
        "similarity": 0.0,
        "reason": "知识库不存在完整对应 Wiki",
        "target": f"20_Wiki/{domain}/",
    }