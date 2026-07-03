# 麒麟OS安全智能运维Agent — AI/LLM智能方案设计

---

- **版本**: v1.0
- **作者**: 艾智深 (AI Engineer)
- **日期**: 2026-06-23

---

## 目录

1. [LLM选型方案](#1-llm选型方案)
2. [自然语言运维Agent架构](#2-自然语言运维agent架构)
3. [安全研判引擎设计](#3-安全研判引擎设计)
4. [策略AI建议引擎](#4-策略ai建议引擎)
5. [Prompt工程方案](#5-prompt工程方案)
6. [离线/低资源环境适配方案](#6-离线低资源环境适配方案)
7. [对话上下文管理设计](#7-对话上下文管理设计)

---

## 1. LLM选型方案

### 1.1 总体策略：三级模型体系

针对麒麟OS环境（可能无公网、200台规模、资源受限）的特点，采用**三级模型分层策略**：

| 层级 | 模型 | 参数量 | 用途 | 推理方式 | 资源需求 |
|------|------|--------|------|----------|----------|
| **L1 - 主推理模型** | Qwen2.5-7B-Instruct | 7B | 对话/研判/策略建议 | GPU推理 | 16GB RAM + 8GB VRAM |
| **L2 - 轻量分类模型** | Qwen2.5-1.5B-Instruct | 1.5B | 意图分类/实体提取 | CPU推理 | 4GB RAM |
| **L3 - Embedding模型** | BAAI/bge-small-zh-v1.5 | 0.1B | 向量化/语义搜索 | CPU推理 | 2GB RAM |

### 1.2 模型选择详解

#### L1: Qwen2.5-7B-Instruct（主模型）

**选型理由**：
- 通义千问Qwen2.5系列在中文理解能力上处于开源模型第一梯队
- 7B参数量在精度和资源消耗之间取得最佳平衡
- Int8量化后仅需约8GB显存，单卡T4即可运行
- 对工具调用(Function Calling)有原生支持，适配Agent架构
- 昆仑OS（同为国产OS）有大量部署案例可供参考
- 支持长达32K的上下文窗口，适合会话管理

**备选方案**：

| 模型 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| **Qwen2.5-7B-Instruct** | 中文最佳、工具调用强 | 需GPU | **首选** |
| **DeepSeek-Coder-6.7B-Instruct** | 逻辑推理强、JSON输出稳定 | 中文对话略逊 | 策略分析场景 |
| **Qwen2.5-14B-Instruct (Int4)** | 更强的推理能力 | 需16GB显存 | 硬件充裕时升级选项 |
| **ChatGLM3-6B** | 对国产硬件适配好 | 工具调用较弱 | 华为昇腾等国产GPU场景 |

#### L2: Qwen2.5-1.5B-Instruct（意图分类/实体提取）

**选型理由**：
- 参数量极小，可在纯CPU环境下实时运行（延迟<500ms）
- 麒麟OS标配服务器（16核CPU、32GB RAM）可轻松承载
- 专门用于意图路由和关键实体提取，减少L1模型的调用频次

#### L3: BAAI/bge-small-zh-v1.5（Embedding）

**选型理由**：
- 384维向量，索引和检索速度极快
- 中文语义搜索效果优秀
- 仅384MB内存占用
- 用于MITRE ATT&CK知识库向量化检索

### 1.3 模型部署方案

#### 方案A（推荐）：Ollama + llama.cpp

```
架构：
┌─────────────────────────────────────────────┐
│              麒麟OS服务器                     │
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Ollama Server   │  │  Ollama Server   │  │
│  │  (L1: Qwen2.5-7B)│  │  (L2: Qwen2.5-   │  │
│  │  端口: 11434     │  │   1.5B)          │  │
│  │  GPU模式(如有)   │  │  端口: 11435     │  │
│  │  或CPU推理       │  │  CPU-only        │  │
│  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │             │
│  ┌────────▼─────────────────────▼─────────┐  │
│  │         FastAPI后端 / AI Service        │  │
│  │  (HTTP 调用 Ollama REST API)           │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  BGE Embedding Service                 │  │
│  │  (Sentence-Transformers, CPU推理)      │  │
│  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**安装步骤**（离线环境）：

```bash
# 在有网络的机器上下载模型和安装包
# 1. 下载 Ollama 二进制（Linux amd64）
wget https://github.com/ollama/ollama/releases/download/v0.3.0/ollama-linux-amd64.tgz

# 2. 下载模型文件（GGUF格式）
# Qwen2.5-7B-Instruct (Int8)
# 从 HuggingFace / ModelScope 下载 GGUF 文件
# 或使用 ollama pull qwen2.5:7b-instruct-q8_0

# 3. 在离线麒麟OS上安装
tar -xzf ollama-linux-amd64.tgz -C /usr/local/
ollama serve &
ollama load qwen2.5:7b-instruct-q8_0
```

#### 方案B（CPU-only）：纯llama.cpp + GGUF

当完全没有GPU时，使用纯CPU推理方案：

```bash
# 下载 llama.cpp 编译版本
# 使用 Q4_K_M 量化级别（更低精度）
./main -m qwen2.5-7b-instruct-q4_k_m.gguf \
       --ctx-size 8192 \
       --threads 16 \
       --n-gpu-layers 0
```

CPU推理性能预估（7B Q4量化）：

| CPU配置 | 生成速度 | 可用性评估 |
|---------|----------|-----------|
| 8核 | 3-5 tokens/s | 可用但稍慢 |
| 16核 | 6-10 tokens/s | 推荐配置 |
| 32核 | 10-15 tokens/s | 流畅体验 |

对于对话场景（用户等待），3-5 tokens/s 是可以接受的（20-30字的回复约5-8秒）。

### 1.4 资源需求汇总

| 组件 | CPU | 内存 | 磁盘 | GPU(可选) |
|------|-----|------|------|-----------|
| L1: Qwen2.5-7B (Q4_ K_M) | 8核 | 8GB | 8GB | 4GB VRAM 或 CPU |
| L1: Qwen2.5-7B (Q8_0) | 8核 | 8GB | 10GB | 8GB VRAM 或 CPU |
| L2: Qwen2.5-1.5B (Q4) | 2核 | 2GB | 2GB | 纯CPU即可 |
| L3: BGE-Small (Embedding) | 2核 | 1GB | 0.5GB | 纯CPU即可 |
| **合计(L1 Q4/L2/L3)** | **12核** | **11GB** | **10.5GB** | **推荐8GB VRAM** |

> **结论**：一台16核CPU、32GB RAM、8GB VRAM（如NVIDIA T4/RTX4060）的服务器即可完整部署三级模型体系。

---

## 2. 自然语言运维Agent架构

### 2.1 整体架构

```
                        用户自然语言查询
                              │
                              ▼
                    ┌──────────────────┐
                    │   Input Guard    │  ← 输入校验、安全过滤、脱敏
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Intent Router   │  ← L2: Qwen2.5-1.5B
                    │  (意图分类器)     │     意图分类 + 置信度评分
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │ 查询类意图   │   │ 操作类意图   │   │ 生成类意图   │
   │ (query)     │   │ (action)    │   │ (generate)  │
   │ - 查状态    │   │ - 更新策略  │   │ - 生成日报  │
   │ - 查告警    │   │ - 远程执行  │   │ - 分析报告  │
   │ - 查统计    │   │ - 下发配置  │   │ - 趋势分析  │
   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
          │                 │                 │
          ▼                 ▼                 ▼
   ┌──────────────────────────────────────────────┐
   │           Entity Extractor (实体提取器)       │
   │  L2: 提取 主机名/时间/指标/告警类型/策略名    │
   │  输出: { "hosts":["kylin-node-03"],          │
   │          "time_range":"last_1h",              │
   │          "intent_type":"query_status" }       │
   └──────────────────────┬───────────────────────┘
                          │
                          ▼
   ┌──────────────────────────────────────────────┐
   │          Tool Executor (工具执行器)           │
   │                                              │
   │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
   │  │ 查询API  │ │ 操作API  │ │ 生成API      │ │
   │  │ - Agent  │ │ - 策略   │ │ - 报表       │ │
   │  │ - 告警   │ │ - 命令   │ │ - 分析       │ │
   │  │ - 统计   │ │ - 配置   │ │              │ │
   │  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
   │       │            │              │          │
   │       ▼            ▼              ▼          │
   │  ┌──────────────────────────────────────┐    │
   │  │      FastAPI Backend (后端API层)      │    │
   │  └──────────────────────────────────────┘    │
   └──────────────────────┬───────────────────────┘
                          │
                   数据返回│
                          ▼
   ┌──────────────────────────────────────────────┐
   │         Response Generator (响应生成器)       │
   │  L1: Qwen2.5-7B 将结构化数据转为自然语言     │
   │  - 格式化输出（表格/文字/列表）              │
   │  - 添加分析结论和建议                        │
   └──────────────────────┬───────────────────────┘
                          │
                          ▼
   ┌──────────────────────────────────────────────┐
   │         Output Guard (输出守卫)               │
   │  - 脱敏检查、合规性验证                       │
   │  - 格式校验                                  │
   └──────────────────────┬───────────────────────┘
                          │
                   返回用户最终响应

                          ┌──────────────────┐
                          │  Context Manager  │
                          │  对话上下文管理    │
                          │  - 会话历史       │
                          │  - 缓存最近N轮    │
                          │  - 摘要压缩       │
                          └──────────────────┘
```

### 2.2 意图分类体系

```
query_status      - 查主机状态/Agent信息
query_alert       - 查告警/安全事件
query_statistics  - 查统计数据/趋势
query_log         - 查日志/审计记录
action_strategy   - 操作策略/规则
action_command    - 远程执行命令
action_upgrade    - 远程升级Agent
generate_report   - 生成运维日报/周报
generate_analysis - 生成安全分析报告
```

### 2.3 工具（Function Calling）定义

每类意图对应一组工具，以OpenAI Function Calling格式定义：

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_agent_status",
        "description": "查询指定Agent的当前状态信息",
        "parameters": {
          "type": "object",
          "properties": {
            "hostname": { "type": "string", "description": "主机名，如 kylin-node-03" },
            "fields": {
              "type": "array",
              "items": { "type": "string", "enum": ["cpu", "memory", "disk", "process", "network", "all"] },
              "description": "需要查询的字段，默认 all"
            }
          },
          "required": ["hostname"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "query_alerts",
        "description": "查询告警列表，支持按时间范围、严重度等筛选",
        "parameters": {
          "type": "object",
          "properties": {
            "time_range": {
              "type": "string",
              "enum": ["last_30m", "last_1h", "last_6h", "last_24h", "last_7d", "custom"],
              "description": "时间范围"
            },
            "severity": {
              "type": "string",
              "enum": ["critical", "high", "medium", "low"],
              "description": "严重度筛选"
            },
            "hostname": { "type": "string", "description": "主机名筛选" },
            "alert_type": { "type": "string", "description": "告警类型" },
            "start_time": { "type": "string", "description": "自定义起始时间 ISO 8601" },
            "end_time": { "type": "string", "description": "自定义结束时间 ISO 8601" },
            "limit": { "type": "integer", "description": "返回条数，默认 20" }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "update_agent_strategy",
        "description": "更新指定Agent的策略配置",
        "parameters": {
          "type": "object",
          "properties": {
            "hostname": { "type": "string", "description": "主机名" },
            "strategy_id": { "type": "string", "description": "策略ID" },
            "action": {
              "type": "string",
              "enum": ["enable", "disable", "update", "rollback"],
              "description": "操作类型"
            },
            "params": { "type": "object", "description": "更新参数" }
          },
          "required": ["hostname", "strategy_id", "action"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "generate_report",
        "description": "生成运维报告",
        "parameters": {
          "type": "object",
          "properties": {
            "report_type": {
              "type": "string",
              "enum": ["daily", "weekly", "custom"],
              "description": "报告类型"
            },
            "time_range": {
              "type": "string",
              "enum": ["yesterday", "this_week", "last_week", "today", "custom"],
              "description": "时间范围"
            },
            "host_filter": { "type": "string", "description": "主机筛选" },
            "start_time": { "type": "string", "description": "自定义起始时间" },
            "end_time": { "type": "string", "description": "自定义结束时间" }
          },
          "required": ["report_type", "time_range"]
        }
      }
    }
  ]
}
```

### 2.4 调用流程（以"帮我查一下kylin-node-03的状态"为例）

```
Step 1: 输入校验
  Input: "帮我查一下kylin-node-03的状态"
  → 安全过滤通过，无敏感词

Step 2: 意图分类 (L2)
  → Intent: query_status, confidence: 0.96
  → Entity: { "hosts": ["kylin-node-03"] }

Step 3: 工具路由
  → 匹配工具: get_agent_status
  → 参数: { "hostname": "kylin-node-03", "fields": ["all"] }

Step 4: API调用
  → GET /api/v1/agents/kylin-node-03
  → 返回数据:
    {
      "agentId": "kylin-node-03",
      "status": "online",
      "cpu": { "usage": 45.2, "cores": 8 },
      "memory": { "total": 16384, "used": 8192, "percent": 50.0 },
      "disk": [{ "mount": "/", "total": 500, "used": 320, "percent": 64.0 }],
      "version": "3.2.0",
      "lastHeartbeat": "2026-06-23T20:05:12Z"
    }

Step 5: 结果生成 (L1)
  → 将结构化数据转为自然语言
  → "kylin-node-03当前状态正常。CPU使用率45.2%，内存使用率50%，根分区使用率64%。Agent版本3.2.0，最近一次心跳在5秒前。"

Step 6: 输出校验
  → 脱敏检查通过
```

### 2.5 执行确认机制

对于操作类意图（更新策略、远程执行等），需要**用户确认**后才执行：

```
用户: "把kylin-node-05的策略更新一下"
  → 意图分类: action_strategy
  → 工具执行前：
    "确认要将策略更新应用于 kylin-node-05 吗？"
    "当前策略版本: v2.1 → 目标版本: v2.2"
  → 用户确认后才执行
  → 执行结果返回
```

---

## 3. 安全研判引擎设计

### 3.1 告警分析流程

```
                    告警事件触发
                        │
                        ▼
        ┌──────────────────────────────┐
        │     Alert Enrichment         │
        │     (告警丰富化)              │
        │  - 补充Agent上下文数据        │
        │  - 关联最近同类告警           │
        │  - 加载主机基线数据           │
        └─────────────┬────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │     MITRE ATT&CK Mapping     │
        │     (技战术映射)              │
        │  - 根据告警类型匹配TTP       │
        │  - 关联攻击阶段(TA)          │
        │  - 知识库向量匹配            │
        └─────────────┬────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │     Alert Aggregation        │
        │     (告警聚合分析)            │
        │  - 同一来源IP聚合            │
        │  - 同一主机时间窗口聚合      │
        │  - 相同TTP聚合               │
        │  - 攻击链构建                │
        └─────────────┬────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │  AI Judgement Engine (L1)    │
        │  (AI研判引擎)                │
        │  - 综合分析告警上下文         │
        │  - 判断攻击类型和严重度      │
        │  - 生成4-5条处置步骤         │
        │  - 置信度评分                │
        └─────────────┬────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │     Playbook Matcher         │
        │     (剧本匹配)               │
        │  - 匹配预定义的处置剧本      │
        │  - 自动处置（可选）          │
        │  - 生成工单/告警更新         │
        └─────────────┬────────────────┘
                      │
                      ▼
              Alert 状态更新
        (new → analyzing → resolved/escalated)
```

### 3.2 MITRE ATT&CK 知识库方案

#### 3.2.1 知识库结构

采用**层次化向量知识库 + 规则映射表**的混合方案：

```
MITRE ATT&CK 知识库
├── Tactic (攻击阶段)  ← 14个阶段
│   ├── TA0001: Initial Access
│   ├── TA0002: Execution
│   ├── TA0003: Persistence
│   ├── TA0004: Privilege Escalation
│   ├── TA0005: Defense Evasion
│   ├── TA0006: Credential Access
│   ├── TA0007: Discovery
│   ├── TA0008: Lateral Movement
│   ├── TA0009: Collection
│   ├── TA0011: Command and Control
│   ├── TA0010: Exfiltration
│   └── TA0040: Impact
│
├── Technique (技战术)  ← 200+个技术
│   ├── T1059: Command and Scripting Interpreter
│   ├── T1055: Process Injection
│   ├── T1566: Phishing
│   ├── T1071: Application Layer Protocol
│   └── ...
│
├── Alert-Type → TTP 映射表  ← 告警类型→技战术映射
│   ├── abnormal_process_creation → T1059
│   ├── suspicious_network_conn → T1071
│   ├── file_integrity_change → T1078
│   └── ...
│
└── Security Playbook (处置剧本)
    ├── playbook_T1059.yaml    ← 命令执行类处置步骤
    ├── playbook_T1071.yaml    ← 网络外联类处置步骤
    └── ...
```

#### 3.2.2 向量化检索流程

```
告警类型 + 告警描述文本
        │
        ▼
  BGE Embedding (L3)
  → 384维向量
        │
        ▼
  向量数据库 (FAISS/Milvus Lite)
  → 检索Top-K相似TTP
  → 返回: [TTP_ID, 置信度, 描述, 处置建议]
        │
        ▼
  规则映射表补充
  → 根据告警类型直接映射TTP
  → 与向量结果合并评分
        │
        ▼
  输出: 最终ATT&CK映射结果
```

#### 3.2.3 知识库构建

```python
# 知识库构建伪代码
mitre_knowledge_base = {
    "techniques": [
        {
            "id": "T1059",
            "name": "Command and Scripting Interpreter",
            "tactic": "Execution",
            "tactic_id": "TA0002",
            "description": "攻击者可能使用命令和脚本解释器执行命令...",
            "detection": "监控进程创建事件，关注cmd.exe、powershell.exe等...",
            "mitigation": "限制脚本执行权限，启用AppLocker...",
            "alert_types": ["abnormal_process_creation", "suspicious_command_exec"],
            "playbook_id": "playbook_T1059"
        },
        # ... 200+ techniques
    ],
    "playbooks": {
        "playbook_T1059": {
            "steps": [
                {"order": 1, "action": "立即隔离主机", "type": "emergency"},
                {"order": 2, "action": "查看进程树，确认父进程", "type": "investigate"},
                {"order": 3, "action": "检查计划任务和服务项", "type": "investigate"},
                {"order": 4, "action": "提取样本进行IOC分析", "type": "forensic"},
                {"order": 5, "action": "评估影响范围，更新IOC规则", "type": "remediate"}
            ]
        }
    }
}

# 离线构建向量索引
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-small-zh-v1.5')

# 将每个technique的描述转为向量
technique_texts = [t["description"] + " " + t["detection"] for t in mitre_knowledge_base["techniques"]]
embeddings = model.encode(technique_texts)

# 保存向量索引 (FAISS)
import faiss
index = faiss.IndexFlatIP(384)  # 内积相似度
index.add(embeddings)
faiss.write_index(index, "mitre_attack.index")
```

### 3.3 AI研判生成逻辑

使用L1模型（Qwen2.5-7B）进行告警研判，核心流程：

```
输入给LLM的上下文：

1. 当前告警信息
   - 类型: abnormal_process_creation
   - 主机: kylin-node-03
   - 时间: 2026-06-23 20:05:12
   - 进程: /tmp/.hidden/malware.bin (PID: 3342)
   - 父进程: /usr/bin/python3 /tmp/exploit.py
   - 严重度: high

2. 主机上下文
   - CPU: 85% (异常高)
   - 内存: 72%
   - 最近登录: root from 10.0.0.45 (非常用IP)
   - 网络连接: 有到 185.xxx.xxx.xxx:8443 的外连

3. 关联告警
   - 5分钟前: 同一主机SSH登录异常 (medium)
   - 15分钟前: 同一主机文件完整性变更 (medium)

4. MITRE ATT&CK 映射
   - T1059 (Command and Scripting Interpreter) — Execution
   - T1055 (Process Injection) — Defense Evasion

LLM输出格式：

{
  "analysis_summary": "主机kylin-node-03疑似遭到远程命令执行攻击...",
  "attack_phase": "Execution → Persistence",
  "mitre_mapping": [
    {"tactic": "TA0002: Execution", "technique": "T1059: Command and Scripting Interpreter"},
    {"tactic": "TA0005: Defense Evasion", "technique": "T1055: Process Injection"}
  ],
  "severity_assessment": "high (评分: 8.5/10)",
  "confidence": "high",
  "remediation_steps": [
    {
      "order": 1,
      "priority": "紧急",
      "action": "立即将kylin-node-03从网络隔离，切断C2通信",
      "type": "emergency"
    },
    {
      "order": 2,
      "priority": "紧急",
      "action": "结束恶意进程 PID 3342 及父进程，删除相关文件",
      "type": "emergency"
    },
    {
      "order": 3,
      "priority": "高",
      "action": "检查 /tmp/.hidden 目录及 /tmp/exploit.py 的来源",
      "type": "investigate"
    },
    {
      "order": 4,
      "priority": "高",
      "action": "排查10.0.0.45的登录来源，检查是否有其他主机受影响",
      "type": "investigate"
    },
    {
      "order": 5,
      "priority": "中",
      "action": "更新入侵检测规则，将185.xxx.xxx.xxx加入黑名单，创建文件完整性监控规则",
      "type": "remediate"
    }
  ],
  "suggested_strategy": "建议创建新策略规则：检测/tmp/目录下的未知ELF文件创建行为"
}
```

### 3.4 告警聚合分析

```
触发条件: 同类型告警在30分钟内出现>=3次，或同一主机出现>=5条告警

聚合分析流程:
1. 时间窗口聚合: 按 [主机, 告警类型] 分组，30分钟窗口
2. 关联分析: 检查是否存在攻击链（如：SSH登录→提权→命令执行→外联）
3. AI分析: 使用L1模型分析聚合后的攻击模式
4. 输出: 聚合告警记录 + 关联分析结果 + 攻击链可视化数据

聚合输出示例:
{
  "aggregation_id": "agg_20260623_001",
  "host_count": 3,
  "alert_count": 12,
  "time_span": "2026-06-23 19:30:00 - 20:00:00",
  "attack_chain": [
    {"host": "kylin-node-03", "time": "19:32", "alert": "SSH异常登录", "tactic": "Initial Access"},
    {"host": "kylin-node-03", "time": "19:35", "alert": "提权尝试", "tactic": "Privilege Escalation"},
    {"host": "kylin-node-03", "time": "19:38", "alert": "异常进程创建", "tactic": "Execution"},
    {"host": "kylin-node-05", "time": "19:42", "alert": "横向移动检测", "tactic": "Lateral Movement"},
    {"host": "kylin-node-05", "time": "19:45", "alert": "数据外传", "tactic": "Exfiltration"}
  ],
  "ai_analysis": "检测到从kylin-node-03到kylin-node-05的横向移动链..."
}
```

---

## 4. 策略AI建议引擎

### 4.1 策略建议生成流程

```
定时触发 (每30分钟)
          │
          ▼
┌──────────────────────────────┐
│   Alert Summary 采集          │
│  - 最近30分钟告警统计         │
│  - 按类型/严重度/主机聚合     │
│  - 获取当前生效策略列表       │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│   Gap Analysis (差距分析)     │
│  - 高频告警是否有对应策略     │
│  - 现有策略命中率统计         │
│  - 策略覆盖缺口识别           │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  AI Strategy Advisor (L1)    │
│  (策略AI建议)                 │
│  - 分析告警模式               │
│  - 生成策略建议               │
│  - 提供参数配置建议           │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│   Human Review (人工审核)     │
│  - 运维人员确认建议           │
│  - 可一键应用/编辑后应用      │
│  - 拒绝并提供反馈             │
└─────────────┬────────────────┘
              │
        ┌─────┴─────┐
        ▼           ▼
   应用策略      记录反馈
    (回馈学习循环)
```

### 4.2 策略建议类型

```
┌────────────────────────────────────────────────────────┐
│ 策略AI建议（三种类型）                                  │
│                                                        │
│ 1. 新增策略建议                                         │
│    ┌─────────────────────────────────────────────────┐  │
│    │ 问题：最近高频出现 /tmp/目录下异常进程创建告警    │  │
│    │ 建议：创建文件监控策略                           │  │
│    │   - 类型: file_integrity_monitoring              │  │
│    │   - 路径: /tmp/**/*.bin, /tmp/**/*.elf           │  │
│    │   - 触发: 新文件创建事件                         │  │
│    │   - 严重度: medium → high                        │  │
│    └─────────────────────────────────────────────────┘  │
│                                                        │
│ 2. 现有策略优化                                         │
│    ┌─────────────────────────────────────────────────┐  │
│    │ 策略：process_whitelist (ID: P001)               │  │
│    │ 当前：命中率 92%，但最近3天有8次误报             │  │
│    │ 建议：更新白名单，添加正则规则                   │  │
│    │   - 添加：nginx, java, python3的特定参数模式      │  │
│    │   - 调整：严重度从 high → medium                   │  │
│    └─────────────────────────────────────────────────┘  │
│                                                        │
│ 3. 策略下放/回收建议                                    │
│    ┌─────────────────────────────────────────────────┐  │
│    │ 策略：port_scan_detection (ID: P003)             │  │
│    │ 当前应用范围：全部200台主机                       │  │
│    │ 分析：kylin-db-* 类主机从未触发，无需监控        │  │
│    │ 建议：从db类主机回收该策略，减少资源消耗          │  │
│    └─────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### 4.3 AI策略建议Prompt输入模板

```json
{
  "alert_statistics": {
    "total_alerts_last_30min": 47,
    "by_severity": {"critical": 3, "high": 12, "medium": 22, "low": 10},
    "top_alert_types": [
      {"type": "abnormal_process_creation", "count": 15, "hosts_affected": 8},
      {"type": "suspicious_network_conn", "count": 10, "hosts_affected": 5},
      {"type": "file_integrity_change", "count": 8, "hosts_affected": 3}
    ]
  },
  "current_policies": [
    {
      "id": "P001",
      "name": "进程白名单",
      "type": "process_whitelist",
      "scope": "all",
      "status": "enabled",
      "hit_count_7d": 145,
      "false_positive_7d": 8
    },
    {
      "id": "P002",
      "name": "端口扫描检测",
      "type": "network_monitor",
      "scope": "all",
      "status": "enabled",
      "hit_count_7d": 23,
      "false_positive_7d": 2
    }
  ],
  "strategy_types_available": [
    "process_whitelist", "file_integrity_monitoring",
    "network_monitor", "login_anomaly_detection",
    "resource_threshold", "custom_script"
  ]
}
```

LLM输出格式：

```json
{
  "suggestions": [
    {
      "type": "new",
      "priority": "high",
      "title": "建议新增文件完整性监控策略",
      "reason": "最近30分钟 /tmp 目录异常进程创建告警 15次，涉及8台主机",
      "suggested_policy": {
        "name": "tmp_dir_monitor",
        "type": "file_integrity_monitoring",
        "config": {
          "paths": ["/tmp/**/*.bin", "/tmp/**/*.elf", "/tmp/**/*.sh"],
          "trigger_on": "create",
          "severity": "high",
          "action": ["alert", "quarantine"]
        },
        "scope": "all_agents"
      }
    },
    {
      "type": "optimize",
      "priority": "medium",
      "title": "P001 进程白名单策略优化建议",
      "reason": "误报率5.5%（7天8次），可优化白名单规则减少误报",
      "optimization": {
        "policy_id": "P001",
        "changes": [
          {"field": "whitelist_rules", "action": "add", "value": "nginx -c /etc/nginx/*.conf"},
          {"field": "severity_overrides", "action": "add", "value": {"process": "cron", "severity": "low"}}
        ],
        "expected_impact": "预计减少60%误报"
      }
    },
    {
      "type": "rescope",
      "priority": "low",
      "title": "P002 端口扫描策略可缩小覆盖范围",
      "reason": "db类主机从未触发，可排除以节省资源",
      "rescope": {
        "policy_id": "P002",
        "exclude_tags": ["database-server"],
        "expected_impact": "减少50台主机的策略计算负载"
      }
    }
  ]
}
```

---

## 5. Prompt工程方案

### 5.1 系统Prompt体系总览

```
┌─────────────────────────────────────────────────────────┐
│                    Prompt 体系                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Level 1: 全局System Prompt (运维助手角色定义)    │   │
│  │  每个对话会话开始时加载                           │   │
│  └─────────────────────┬───────────────────────────┘   │
│                        │                                │
│  ┌─────────────────────▼───────────────────────────┐   │
│  │  Level 2: 领域System Prompt (按需动态注入)       │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────┐  │   │
│  │  │ 安全研判      │ │ 策略建议      │ │ 报表生成 │  │   │
│  │  └──────────────┘ └──────────────┘ └─────────┘  │   │
│  └─────────────────────┬───────────────────────────┘   │
│                        │                                │
│  ┌─────────────────────▼───────────────────────────┐   │
│  │  Level 3: 上下文注入 (运行时动态构建)            │   │
│  │  - 当前告警数据                                  │   │
│  │  - Agent状态数据                                 │   │
│  │  - 历史会话摘要                                  │   │
│  │  - 工具调用结果                                  │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 5.2 全局System Prompt（对话式运维Agent）

```
你是一个部署在麒麟操作系统上的安全智能运维助手，名为"麒麟卫士"。
你通过API与后端系统交互，帮助运维人员管理和监控服务器集群。

## 你的能力
1. 查询服务器状态（CPU/内存/磁盘/进程）
2. 查询告警和安全事件
3. 执行策略更新操作（需用户确认）
4. 生成运维报告和分析
5. 分析和研判安全事件
6. 提供策略优化建议

## 使用规范
1. 所有回复使用中文，保持专业、简洁
2. 数据查询结果优先以结构化方式呈现（表格/列表）
3. 对于操作类请求，必须二次确认后才执行
4. 对于安全事件分析，必须引用MITRE ATT&CK框架
5. 不确定的信息不要编造，表明无法回答
6. 涉及敏感操作（策略变更、命令执行）必须记录审计日志

## 输出风格
- 状态查询：先给出总体结论（正常/异常），再展开详情
- 告警查询：按严重度排序，突出高危和紧急告警
- 安全分析：按 结论→攻击链→处置步骤 的顺序输出
- 报告生成：基于数据事实，客观分析，避免主观臆断

## 限制
- 你只能通过已定义的工具函数访问系统数据
- 无法直接访问文件系统
- 无法执行未授权的远程命令
- 无法修改系统配置
```

### 5.3 安全研判System Prompt

```
你是一位专业的安全分析师（SOC Analyst），负责对麒麟OS集群的安全告警进行分析研判。

## 任务
分析传入的告警事件，完成以下工作：
1. 根据告警数据判断攻击类型和严重度
2. 映射到MITRE ATT&CK框架的战术和技术
3. 分析攻击链（如果有多个关联告警）
4. 提供可执行的处置步骤（4-5条）

## 分析框架
按照以下维度进行分析：
- 攻击入口（Initial Access）：攻击者如何进入系统
- 执行方式（Execution）：恶意代码如何执行
- 持久化（Persistence）：攻击者如何维持访问
- 防御绕过（Defense Evasion）：如何规避检测
- 影响范围（Impact）：受影响的主机和数据

## 处置步骤规范
每条处置步骤包含：
- 优先级：紧急/高/中/低
- 类型：emergency（应急）/investigate（调查）/remediate（修复）/forensic（取证）
- 可执行的具体操作描述

## 输出格式
严格按照JSON格式输出，包含analysis_summary、attack_phase、mitre_mapping、severity_assessment、remediation_steps字段。

## 重要约束
- 只基于提供的数据进行分析，不要臆测未确认的信息
- 处置步骤必须可执行、可操作
- 引用MITRE ATT&CK时提供准确的T编号
```

### 5.4 策略建议System Prompt

```
你是一位安全策略优化专家，负责为麒麟OS集群提供策略规则建议。

## 任务
基于当前的告警统计数据和现有策略配置，提供策略优化建议。

## 评估维度
1. 覆盖度：当前策略是否覆盖了所有高频告警类型
2. 精准度：现有策略的命中率和误报率
3. 效率：策略配置是否最优，是否存在冗余
4. 适应性：策略能否应对当前威胁态势

## 建议类型
请从以下三种类型中输出建议：
1. new - 新增策略（当发现未覆盖的告警类型时）
2. optimize - 优化现有策略（当发现误报或配置不合理时）
3. rescope - 调整策略范围（当发现策略覆盖不必要时）

## 输出要求
- 每条建议必须有明确的数据支撑（引用告警统计数据）
- 提供预期的优化效果预估
- 建议必须符合系统支持的策略类型
- 输出严格遵循JSON格式
```

### 5.5 工具调用System Prompt（Function Calling）

```
你是一个智能运维助手，通过调用API工具来回答用户问题。

## 工具调用规则
1. 分析用户意图，选择最合适的工具
2. 提取关键参数（主机名、时间范围、告警类型等）
3. 一次只调用一个工具，根据返回结果决定下一步
4. 如果用户意图不明确，先询问澄清

## 参数提取规范
- 时间相关：将"最近一小时"转为 last_1h，"今天"转为 today
- 主机名相关：保持原始主机名格式（如 kylin-node-03）
- 模糊查询：如果用户未指定具体参数，使用合理的默认值

## 注意事项
- 如果工具调用返回错误，向用户清晰说明错误原因
- 对于空结果，如实告知用户没有查到数据
- 涉及多个步骤的查询，分步执行并汇总结果
```

### 5.6 Prompt安全防护

```yaml
# prompt_injection_guard.yaml
防护策略:
  输入过滤层:
    - 检测SQL注入模式: "(?i)(SELECT|INSERT|DELETE|DROP|UNION|--)"
    - 检测Prompt注入模式: "(?i)(忽略之前的指令|忽略系统提示|你是|system prompt)"
    - 检测特殊字符注入: 罕见Unicode字符、零宽字符
    
  角色保护:
    - 每次对话开头注入不可见的系统标识token
    - System Prompt中嵌入隐形水印
    
  输出过滤层:
    - 不允许输出系统内部API Key和凭证
    - 不允许输出系统文件路径
    - 不允许执行非定义的函数调用
    
  速率控制:
    - 单用户QPS限制: 10次/秒
    - 操作类请求: 需额外验证
```

---

## 6. 离线/低资源环境适配方案

### 6.1 离线部署策略

```
┌──────────────────────────────────────────────────────────────────┐
│                   离线部署工作流                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Step 1] 联网环境准备（外部PC）                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 下载所需资源：                                            │    │
│  │  - GGUF模型文件（Qwen2.5-7B Q4_K_M / Q8_0）              │    │
│  │  - Ollama 安装包（Linux amd64）                          │    │
│  │  - Python依赖包（pip download）                          │    │
│  │  - FAISS / sentence-transformers whl包                  │    │
│  │  - MITRE ATT&CK 知识库数据（预构建向量索引）               │    │
│  │  - Docker镜像（可选，容器化部署用）                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                          │                                        │
│                          ▼                                        │
│  [Step 2] 离线传输到麒麟OS                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ 传输方式：                                                │    │
│  │  - USB移动硬盘（首选，大文件）                             │    │
│  │  - 内网文件服务器（如NFS/Samba共享）                      │    │
│  │  - 刻录DVD（较小文件）                                    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                          │                                        │
│                          ▼                                        │
│  [Step 3] 麒麟OS安装                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ # 离线安装Ollama                                         │    │
│  │ tar -xzf ollama-linux-amd64.tgz -C /usr/local/            │    │
│  │ chmod +x /usr/local/bin/ollama                            │    │
│  │                                                           │    │
│  │ # 导入模型                                                │    │
│  │ scp qwen2.5-7b-instruct-q4_k_m.gguf user@kylin:/models/  │    │
│  │                                                           │    │
│  │ # 离线安装Python依赖                                      │    │
│  │ pip install --no-index --find-links=./packages/ \         │    │
│  │     fastapi uvicorn sqlalchemy pydantic \                 │    │
│  │     sentence-transformers faiss-cpu \                     │    │
│  │     ollama-python redis                                   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 纯CPU环境适配

当完全无GPU时，采用以下优化策略：

```yaml
cpu_optimization:
  模型量化:
    - 主模型: Qwen2.5-7B Q4_K_M（4-bit量化，模型大小约4.5GB）
    - 意图模型: Qwen2.5-1.5B Q4_K_M（约1GB）
    - Embedding模型: bge-small-zh-v1.5 原生即轻量（约384MB）
  
  推理加速:
    - 使用llama.cpp的CPU优化版本（支持AVX2/NEON指令集）
    - 启用BLAS加速（OpenBLAS/Intel MKL）
    - 多线程推理（线程数 = CPU物理核心数）
    - 批处理推理（合并多个请求提升吞吐）
    
  缓存策略:
    - 对常见查询结果进行缓存（TTL: 30秒）
    - KV Cache：复用已计算的历史attention key/value
    - 预填充(Prefill)：对高频prompt模板预计算
    
  降级策略:
    - 当L1模型响应超时(>30秒)时，使用L2模型提供简化回复
    - 当全部模型不可用时，回退到基于规则的回复模板
```

### 6.3 CPU推理性能基准

| 模型 | 量化 | 硬件 | 生成速度 | 首Token延迟 |
|------|------|------|---------|------------|
| Qwen2.5-7B | Q4_K_M | 16核CPU | 6-8 tok/s | 1.5-3s |
| Qwen2.5-7B | Q4_K_M | 32核CPU | 10-14 tok/s | 0.8-1.5s |
| Qwen2.5-7B | Q8_0 | 16核CPU | 3-5 tok/s | 3-5s |
| Qwen2.5-1.5B | Q4_K_M | 4核CPU | 30-50 tok/s | 0.2-0.5s |
| Qwen2.5-1.5B | Q8_0 | 4核CPU | 20-35 tok/s | 0.3-0.8s |

### 6.4 AI功能降级矩阵

```
┌──────────────────┬────────────────┬─────────────────┬──────────────────┐
│   场景           │ 正常模式        │ 低资源模式       │ 紧急降级模式      │
│                  │ (有GPU/高负载)  │ (纯CPU/中负载)   │ (高负载/异常)     │
├──────────────────┼────────────────┼─────────────────┼──────────────────┤
│ 自然语言对话      │ L1全面应答      │ L2简化应答       │ 规则模板回复      │
│                  │ 3-5秒响应       │ 5-10秒响应       │ <1秒响应          │
├──────────────────┼────────────────┼─────────────────┼──────────────────┤
│ 安全研判          │ L1深度分析      │ 仅规则匹配研判   │ 仅基础分类        │
│                  │ 10-15秒/条      │ <3秒/条          │ <1秒              │
├──────────────────┼────────────────┼─────────────────┼──────────────────┤
│ 策略建议          │ L1分析+建议     │ 预置规则匹配     │ 不提供服务         │
│                  │ 15-20秒/次      │ <5秒/次          │                   │
├──────────────────┼────────────────┼─────────────────┼──────────────────┤
│ 报表生成          │ L1完整报告      │ L2摘要报告       │ 仅数据罗列        │
│                  │ 20-30秒         │ 10-15秒          │ <3秒              │
├──────────────────┼────────────────┼─────────────────┼──────────────────┤
│ 意图识别          │ L2实时分类      │ L2实时分类       │ 正则匹配替代      │
│                  │ <500ms          │ <500ms           │ <100ms            │
└──────────────────┴────────────────┴─────────────────┴──────────────────┘
```

### 6.5 模型冷启动预热

```python
# 模型预热策略
def warmup_models():
    """系统启动时预热模型"""
    # 1. 加载L2意图模型（优先，最常用）
    load_intent_model()
    
    # 2. 加载L3 Embedding模型
    load_embedding_model()
    
    # 3. 预热L1主模型（后台异步）
    # 发送一个预热请求，触发模型加载和KV Cache初始化
    background_task(load_main_model)
    
    # 4. 预热常见Prompt
    # 对高频使用的System Prompt进行预填充
    warmup_common_prompts()

# 模型保活
def keep_alive():
    """每5分钟发送一次保活请求，防止模型被OS swap"""
    while True:
        ollama.keep_alive("qwen2.5:7b")
        time.sleep(300)
```

---

## 7. 对话上下文管理设计

### 7.1 对话状态模型

```python
@dataclass
class ConversationState:
    """对话状态"""
    session_id: str                         # 会话ID (UUID)
    user_id: str                            # 用户ID
    created_at: datetime                    # 创建时间
    updated_at: datetime                    # 最后更新时间
    
    # 消息历史
    messages: List[Message]                 # 完整消息列表（限制大小）
    
    # 上下文
    current_intent: Optional[str]           # 当前意图
    last_action: Optional[str]              # 上一步操作
    pending_confirmation: Optional[Dict]    # 待确认的操作
    referenced_hosts: Set[str]              # 本轮引用过的主机
    extracted_entities: Dict[str, Any]      # 提取的实体缓存
    
    # 状态
    turn_count: int = 0                     # 轮次计数
    is_active: bool = True                  # 是否活跃
    
    # 性能优化
    summary: Optional[str] = None           # 会话摘要（用于超长会话压缩）

@dataclass
class Message:
    role: str                               # "user" | "assistant" | "system" | "tool"
    content: str                            # 消息内容
    timestamp: datetime                     # 时间戳
    metadata: Optional[Dict] = None         # 元数据（如工具调用详情）
```

### 7.2 上下文管理策略

```
┌────────────────────────────────────────────────────────────────┐
│                   上下文管理策略                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. 滑动窗口策略                                                 │
│     ┌────────────────────────────────────────────────────┐     │
│     │ 保留最近N轮完整消息（默认10轮）                      │     │
│     │ 超出部分：丢弃最早的消息                              │     │
│     │ 优点：实现简单，响应快速                              │     │
│     │ 缺点：丢失早期上下文                                  │     │
│     └────────────────────────────────────────────────────┘     │
│                                                                │
│  2. 摘要压缩策略                                                 │
│     ┌────────────────────────────────────────────────────┐     │
│     │ 当消息长度 > 阈值（如4000 tokens）时触发             │     │
│     │ 步骤：                                               │     │
│     │ 1. 保留最近3轮完整消息                                │     │
│     │ 2. 将更早的消息压缩为摘要                             │     │
│     │ 3. 将摘要注入system prompt                           │     │
│     │                                                      │     │
│     │ 压缩Prompt：                                          │     │
│     │ "请将以下对话历史压缩为一段简洁的中文摘要，            │     │
│     │  保留关键信息：查询过的主机、最近的告警、               │     │
│     │  待确认的操作、用户偏好。"                             │     │
│     └────────────────────────────────────────────────────┘     │
│                                                                │
│  3. 分层存储策略                                                 │
│     ┌────────────────────────────────────────────────────┐     │
│     │ Redis内存层：活跃会话（TTL: 30分钟无操作过期）        │     │
│     │ PostgreSQL持久层：所有历史会话（保留30天）           │     │
│     │ 当会话被重新激活时，从PG恢复最近几轮消息              │     │
│     └────────────────────────────────────────────────────┘     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 7.3 上下文窗口管理算法

```python
class ContextManager:
    """对话上下文管理器"""
    
    # Token预算分配
    TOKEN_BUDGET = 8192  # Qwen2.5-7B 可用上下文窗口
    BUDGET_ALLOCATION = {
        "system_prompt": 1500,      # System Prompt
        "context_summary": 500,     # 历史摘要
        "current_turn": 3000,       # 当前轮次（用户输入+工具结果）
        "tool_definitions": 2000,   # 工具定义
        "reserved": 1192            # 预留空间
    }
    
    def prepare_context(self, session: ConversationState, user_input: str) -> List[Dict]:
        """准备完整的LLM输入上下文"""
        
        context = []
        
        # 1. System Prompt
        context.append({"role": "system", "content": self.get_base_system_prompt()})
        
        # 2. 领域特定Prompt（根据意图注入）
        if session.current_intent:
            domain_prompt = self.get_domain_prompt(session.current_intent)
            if domain_prompt:
                context.append({"role": "system", "content": domain_prompt})
        
        # 3. 历史摘要（如果有压缩）
        if session.summary:
            context.append({
                "role": "system",
                "content": f"以下是之前对话的摘要，请注意其中的关键信息：\n{session.summary}"
            })
        
        # 4. 最近N轮消息（滑动窗口）
        recent_messages = self.get_recent_messages(session, window_size=10)
        context.extend(recent_messages)
        
        # 5. 工具定义
        tools = self.get_tools_for_intent(session.current_intent)
        if tools:
            context.append({
                "role": "system",
                "content": f"可用工具：\n{json.dumps(tools, ensure_ascii=False, indent=2)}"
            })
        
        # 6. Token预算校验
        total_tokens = self.estimate_tokens(context)
        if total_tokens > self.TOKEN_BUDGET:
            # 触发压缩
            self.compress_history(session)
            return self.prepare_context(session, user_input)  # 递归重试
        
        return context
    
    def compress_history(self, session: ConversationState):
        """压缩早期对话历史"""
        # 保留最近3轮完整消息
        keep_count = 3
        if len(session.messages) <= keep_count:
            return
        
        # 需要压缩的部分
        compress_messages = session.messages[:-keep_count]
        
        # 调用L2模型生成摘要
        summary_prompt = f"""
        请将以下对话历史压缩为一段简洁的中文摘要，
        保留关键信息：查询过的主机、最近的告警、待确认的操作、用户偏好。
        
        对话历史：
        {json.dumps([{"role": m.role, "content": m.content[:200]} for m in compress_messages], ensure_ascii=False)}
        """
        
        summary = self.light_model.generate(summary_prompt)
        session.summary = summary
        
        # 更新消息列表
        session.messages = session.messages[-keep_count:]
```

### 7.4 会话生命周期管理

```
┌─────────────────────────────────────────────────────┐
│              会话生命周期                             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  CREATED ──→ ACTIVE ──→ IDLE ──→ EXPIRED            │
│     │           │          │         │               │
│     │           │          │         │               │
│     ▼           ▼          ▼         ▼               │
│  用户发起   30秒内    30分钟无    超过24小时          │
│  对话       持续交互   操作       未恢复              │
│                                                     │
│  存储位置：                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐      │
│  │ Redis    │  │ Redis    │  │ PostgreSQL   │      │
│  │ (活跃)   │  │ (活跃)   │  │ (历史归档)   │      │
│  │ TTL:30m  │  │ TTL:30m  │  │ 保留30天     │      │
│  └──────────┘  └──────────┘  └──────────────┘      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 7.5 Redis数据结构设计

```redis
# 活跃会话缓存
# Key: session:{session_id}
# Type: Hash
session:{session_id} = {
    "user_id": "u001",
    "created_at": "2026-06-23T20:00:00Z",
    "updated_at": "2026-06-23T20:05:00Z",
    "current_intent": "query_status",
    "turn_count": "5",
    "summary": "用户查询了kylin-node-03和kylin-node-05的状态..."
}
TTL: 1800 (30分钟)

# 消息队列 (保留最近20条)
# Key: session:{session_id}:messages
# Type: List
session:{session_id}:messages = [
    '{"role": "user", "content": "帮我查kylin-node-03", "ts": "..."}',
    '{"role": "assistant", "content": "...", "ts": "..."}',
    ...
]
LTRIM: 0 19 (保留最近20条)

# 待确认操作
# Key: session:{session_id}:pending
# Type: String (JSON)
session:{session_id}:pending = '{
    "action": "update_strategy",
    "target": "kylin-node-05",
    "params": {...},
    "expires_at": "2026-06-23T20:10:00Z"
}'
TTL: 300 (5分钟)
```

### 7.6 PostgreSQL持久化表设计

```sql
-- 会话表
CREATE TABLE ai_conversations (
    session_id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(16) NOT NULL DEFAULT 'active',  -- active/expired/archived
    turn_count INTEGER DEFAULT 0,
    summary TEXT,
    metadata JSONB,
    
    -- 索引
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),
    -- 查询优化
    INDEX idx_conversations_user (user_id),
    INDEX idx_conversations_updated (updated_at)
);

-- 消息表
CREATE TABLE ai_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    role VARCHAR(16) NOT NULL,  -- user/assistant/system/tool
    content TEXT NOT NULL,
    token_count INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata JSONB,  -- 工具调用详情、模型信息等
    
    -- 索引
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES ai_conversations(session_id),
    INDEX idx_messages_session (session_id, timestamp)
);

-- 告警研判记录表
CREATE TABLE ai_alert_analysis (
    id BIGSERIAL PRIMARY KEY,
    alert_id VARCHAR(64) NOT NULL,
    analysis JSONB NOT NULL,  -- 完整的研判结果JSON
    model_used VARCHAR(64),    -- 使用的模型
    confidence FLOAT,          -- 置信度
    processing_time_ms INTEGER, -- 处理耗时
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_alert_analysis_alert (alert_id)
);

-- 策略建议记录表
CREATE TABLE ai_strategy_suggestions (
    id BIGSERIAL PRIMARY KEY,
    suggestion_type VARCHAR(16),  -- new/optimize/rescope
    title VARCHAR(256),
    reason TEXT,
    suggested_config JSONB,
    status VARCHAR(16) DEFAULT 'pending',  -- pending/applied/rejected
    applied_by VARCHAR(64),
    feedback TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_suggestions_status (status, created_at)
);

-- 自动清理策略（保留30天）
-- 通过pg_cron或外部定时任务执行
-- DELETE FROM ai_messages WHERE timestamp < NOW() - INTERVAL '30 days';
```

---

## 附录

### A. 关键工具/库清单

| 工具 | 版本 | 用途 | 离线安装 |
|------|------|------|---------|
| Ollama | v0.3.x | LLM模型服务 | 支持（二进制） |
| llama.cpp | b3xxx | CPU推理引擎 | 支持（源码编译） |
| sentence-transformers | v3.x | Embedding模型 | pip下载 |
| FAISS (CPU) | v1.7.x | 向量检索 | pip下载 |
| Redis | v7.x | 会话缓存/消息队列 | RPM包离线安装 |
| PostgreSQL | v15+ | 数据持久化 | RPM包离线安装 |
| Python | 3.10+ | 运行环境 | 源码编译/RPM |
| FastAPI | v0.110+ | API框架 | pip下载 |

### B. 模型下载清单（离线准备）

```
models/
├── qwen2.5-7b-instruct-q4_k_m.gguf    # L1主模型 (约4.5GB)
├── qwen2.5-1.5b-instruct-q4_k_m.gguf   # L2意图分类 (约1GB)
├── bge-small-zh-v1.5/                   # L3 Embedding (约384MB)
│   ├── pytorch_model.bin
│   ├── config.json
│   └── tokenizer.json
└── mitre_attack_index/                  # 预构建的ATT&CK向量索引
    ├── faiss.index
    └── technique_metadata.json
```

### C. 系统环境要求（最低/推荐）

| 配置项 | 最低要求 | 推荐配置 |
|--------|---------|---------|
| CPU | 8核x86_64 | 16核x86_64 (支持AVX2) |
| 内存 | 16GB | 32GB |
| 磁盘 | 50GB | 100GB SSD |
| GPU | 可选 | NVIDIA T4/RTX4060 (8GB VRAM) |
| 操作系统 | 麒麟V10 | 麒麟V10 SP1+ |
| 依赖组件 | Python 3.10+, Redis, PostgreSQL | 同上 |

---

> **文档结束** — 本文档为麒麟OS安全智能运维Agent系统的AI/LLM能力设计方案，涵盖了LLM选型、Agent架构、安全研判、策略建议、Prompt工程、离线适配及上下文管理七大模块。
