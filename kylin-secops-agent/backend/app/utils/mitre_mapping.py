"""MITRE ATT&CK mapping utilities."""

from typing import Any, Dict, List, Optional

# MITRE ATT&CK v14 Tactics
MITRE_TACTICS = {
    "TA0001": "初始访问",
    "TA0002": "执行",
    "TA0003": "持久化",
    "TA0004": "权限提升",
    "TA0005": "防御规避",
    "TA0006": "凭据访问",
    "TA0007": "发现",
    "TA0008": "横向移动",
    "TA0009": "收集",
    "TA0010": "命令与控制",
    "TA0011": "数据渗出",
    "TA0040": "影响",
    "TA0043": "侦察",
}

# Common alert type -> MITRE mapping
ALERT_TYPE_MITRE_MAP: Dict[str, Dict[str, Any]] = {
    "file_monitor": {
        "tactic_id": "TA0003",
        "tactic": "持久化",
        "technique_id": "T1547",
        "technique_name": "启动或登录自动启动执行",
    },
    "process_monitor": {
        "tactic_id": "TA0002",
        "tactic": "执行",
        "technique_id": "T1059",
        "technique_name": "命令和脚本解释器",
    },
    "network_monitor": {
        "tactic_id": "TA0011",
        "tactic": "命令与控制",
        "technique_id": "T1071",
        "technique_name": "应用层协议",
    },
    "login_monitor": {
        "tactic_id": "TA0001",
        "tactic": "初始访问",
        "technique_id": "T1078",
        "technique_name": "有效账户",
    },
    "user_monitor": {
        "tactic_id": "TA0004",
        "tactic": "权限提升",
        "technique_id": "T1548",
        "technique_name": "滥用提升控制机制",
    },
    "vulnerability": {
        "tactic_id": "TA0007",
        "tactic": "发现",
        "technique_id": "T1518",
        "technique_name": "软件发现",
    },
    "malware": {
        "tactic_id": "TA0002",
        "tactic": "执行",
        "technique_id": "T1204",
        "technique_name": "用户执行",
    },
    "privilege_escalation": {
        "tactic_id": "TA0004",
        "tactic": "权限提升",
        "technique_id": "T1548.003",
        "technique_name": "Sudo和Sudo缓存",
    },
    "lateral_movement": {
        "tactic_id": "TA0008",
        "tactic": "横向移动",
        "technique_id": "T1021",
        "technique_name": "远程服务",
    },
    "persistence": {
        "tactic_id": "TA0003",
        "tactic": "持久化",
        "technique_id": "T1098",
        "technique_name": "账户操纵",
    },
    "defense_evasion": {
        "tactic_id": "TA0005",
        "tactic": "防御规避",
        "technique_id": "T1562",
        "technique_name": "防御工具削弱",
    },
    "anomaly": {
        "tactic_id": "TA0043",
        "tactic": "侦察",
        "technique_id": "T1592",
        "technique_name": "收集受害者主机信息",
    },
}


def map_alert_to_mitre(alert_type: str) -> Dict[str, Optional[str]]:
    """Map an alert type to MITRE ATT&CK fields."""
    mapping = ALERT_TYPE_MITRE_MAP.get(alert_type, {})
    return {
        "mitre_tactic": mapping.get("tactic"),
        "mitre_tactic_id": mapping.get("tactic_id"),
        "mitre_technique_id": mapping.get("technique_id"),
        "mitre_technique_name": mapping.get("technique_name"),
    }


def get_mitre_tactic_name(tactic_id: str) -> Optional[str]:
    """Get Chinese tactic name by ID."""
    return MITRE_TACTICS.get(tactic_id)


def get_all_mitre_tactics() -> List[Dict[str, Any]]:
    """Get all MITRE tactics."""
    return [
        {"id": tid, "name": name}
        for tid, name in MITRE_TACTICS.items()
    ]


def get_mitre_matrix() -> List[Dict[str, Any]]:
    """Get the full MITRE ATT&CK matrix with techniques."""
    return [
        {
            "tactic_id": data["tactic_id"],
            "tactic_name": data["tactic"],
            "techniques": [{
                "technique_id": data["technique_id"],
                "technique_name": data["technique_name"],
            }],
        }
        for data in ALERT_TYPE_MITRE_MAP.values()
    ]