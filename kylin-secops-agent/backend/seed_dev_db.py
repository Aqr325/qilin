"""Standalone seed script for SQLite dev database (sync, no ORM dependency)."""
import sqlite3
import json
import hashlib
import os
import random
import bcrypt as _bcrypt
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "kylin_secops_dev.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.executescript("""
CREATE TABLE IF NOT EXISTS roles (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, is_system INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS permissions (id TEXT PRIMARY KEY, name TEXT NOT NULL, code TEXT UNIQUE NOT NULL, description TEXT);
CREATE TABLE IF NOT EXISTS role_permissions (role_id TEXT, permission_id TEXT, PRIMARY KEY(role_id, permission_id));
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT, hashed_password TEXT NOT NULL, display_name TEXT, status TEXT DEFAULT 'active', mfa_enabled INTEGER DEFAULT 0, mfa_secret TEXT, failed_login_attempts INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS user_roles (user_id TEXT, role_id TEXT, PRIMARY KEY(user_id, role_id));
CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, hostname TEXT, ip_address TEXT, os_version TEXT, agent_version TEXT, status TEXT DEFAULT 'pending', cpu_usage REAL DEFAULT 0, memory_usage REAL DEFAULT 0, disk_usage REAL DEFAULT 0, process_count INTEGER DEFAULT 0, tags TEXT DEFAULT '[]', last_heartbeat TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS agent_heartbeats (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, cpu REAL, memory REAL, disk TEXT, processes INTEGER, load_avg REAL, reported_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, alert_id TEXT UNIQUE, agent_id TEXT, event_type TEXT, severity TEXT, status TEXT DEFAULT 'new', source_ip TEXT, dest_ip TEXT, port INTEGER, protocol TEXT, mitre_tactic TEXT, mitre_technique TEXT, mitre_technique_name TEXT, description TEXT, raw_data TEXT, created_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS alert_status_history (id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT, from_status TEXT, to_status TEXT, operator_id TEXT, remark TEXT, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS policies (id TEXT PRIMARY KEY, name TEXT, type TEXT, version INTEGER DEFAULT 1, content_yaml TEXT, target_scope TEXT, enabled INTEGER DEFAULT 1, hit_count INTEGER DEFAULT 0, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS policy_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, policy_id TEXT, version INTEGER, content_yaml TEXT, checksum TEXT, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS policy_targets (id INTEGER PRIMARY KEY AUTOINCREMENT, policy_id TEXT, agent_id TEXT);
CREATE TABLE IF NOT EXISTS login_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT, ip_address TEXT, user_agent TEXT, success INTEGER, failure_reason TEXT, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, user_id TEXT, username TEXT, action TEXT, resource_type TEXT, resource_id TEXT, detail TEXT, ip_address TEXT, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS ai_conversations (id TEXT PRIMARY KEY, user_id TEXT, title TEXT, messages TEXT, context_data TEXT, created_at TIMESTAMP, updated_at TIMESTAMP);
""")
print("Tables created OK")

# Check if already seeded
row = c.execute("SELECT COUNT(*) FROM users").fetchone()
if row and row[0] > 0:
    print(f"Already has {row[0]} users, skipping seed")
    conn.close()
    exit(0)

# Generate bcrypt password hash (backend uses passlib/CryptContext which wraps bcrypt)
pwd = _bcrypt.hashpw(b"admin123", _bcrypt.gensalt(4)).decode()

# Roles
roles = [
    ("admin", "管理员", "系统管理员，拥有全部权限"),
    ("operator", "运维员", "运维操作员"),
    ("auditor", "审计员", "审计员"),
    ("readonly", "只读", "只读用户"),
]
c.executemany("INSERT OR REPLACE INTO roles VALUES (?,?,?,1)", [(r[0], r[1], r[2]) for r in roles])

# Permissions
perms = [
    ("p1","用户管理","system:user"), ("p2","角色管理","system:role"),
    ("p3","策略配置","policy:write"),("p4","策略查看","policy:read"),
    ("p5","Agent管理","agent:write"),("p6","Agent查看","agent:read"),
    ("p7","告警处置","alert:write"), ("p8","告警查看","alert:read"),
    ("p9","系统配置","system:config"),("p10","日志查看","log:read"),
    ("p11","系统审计","audit:read"), ("p12","仪表盘","dashboard:read"),
]
c.executemany("INSERT OR REPLACE INTO permissions VALUES (?,?,?,'')", perms)

# Role-Permissions
rp = {
    "admin": {f"p{i}" for i in range(1,13)},
    "operator": {f"p{i}" for i in range(3,9)},
    "auditor": {"p10","p11","p12"},
    "readonly": {"p12"},
}
for rid, pids in rp.items():
    for pid in pids:
        c.execute("INSERT OR IGNORE INTO role_permissions VALUES (?,?)", (rid, pid))

# Users
users = [
    ("u1","admin","admin@kylin.local",pwd,"系统管理员","active"),
    ("u2","zhangsan","zhangsan@kylin.local",pwd,"张三","active"),
    ("u3","lisi","lisi@kylin.local",pwd,"李四","locked"),
    ("u4","wangwu","wangwu@kylin.local",pwd,"王五","active"),
    ("u5","zhaoliu","zhaoliu@kylin.local",pwd,"赵六","active"),
    ("u6","security-ops","secops@kylin.local",pwd,"安全运维","disabled"),
]
c.executemany("INSERT OR IGNORE INTO users (id,username,email,hashed_password,display_name,status) VALUES (?,?,?,?,?,?)", users)
c.executemany("INSERT OR IGNORE INTO user_roles VALUES (?,?)", [("u1","admin"),("u2","operator"),("u3","operator"),("u4","auditor"),("u5","readonly"),("u6","operator")])

# Agents
agents = [
    ("kylin-node-01","kylin-node-01","10.0.1.101","麒麟V10 SP1","3.2.0","online",45.2,62.1,68.0,312,'["production","web"]'),
    ("kylin-node-02","kylin-node-02","10.0.1.102","麒麟V10","3.2.0","online",23.8,41.5,55.0,189,'["production","db"]'),
    ("kylin-node-03","kylin-node-03","10.0.1.103","银河麒麟V10","3.2.0","online",78.5,85.2,72.0,445,'["production","web"]'),
    ("kylin-node-04","kylin-node-04","10.0.1.104","麒麟V10 SP1","3.2.1","online",12.3,28.0,45.0,156,'["staging","web"]'),
    ("kylin-node-05","kylin-node-05","10.0.1.105","麒麟V10","3.2.0","offline",0,0,0,0,'["production","web"]'),
    ("kylin-node-06","kylin-node-06","10.0.1.106","银河麒麟V10","3.2.0","error",92.1,95.3,88.0,512,'["production","db"]'),
    ("kylin-node-07","kylin-node-07","10.0.1.107","麒麟V10 SP1","3.2.0","online",35.6,52.0,60.0,234,'["production","app"]'),
    ("kylin-node-08","kylin-node-08","10.0.1.108","麒麟V10","3.2.0","pending",0,0,0,0,'["staging"]'),
]
c.executemany("INSERT OR IGNORE INTO agents (id,hostname,ip_address,os_version,agent_version,status,cpu_usage,memory_usage,disk_usage,process_count,tags) VALUES (?,?,?,?,?,?,?,?,?,?,?)", agents)

# Heartbeats (5 agents x 24 hours)
for aid in ["kylin-node-01","kylin-node-02","kylin-node-03","kylin-node-04","kylin-node-07"]:
    for h in range(24):
        ts = (datetime.now() - timedelta(hours=h)).isoformat()
        cpu = round(random.uniform(10,90), 1)
        mem = round(random.uniform(20,90), 1)
        disk = json.dumps({"/": {"total": 500, "used": round(200+cpu*2), "percent": round(40+cpu*0.3,1)}})
        procs = random.randint(150,500)
        load = round(random.uniform(0.5,8.0), 2)
        c.execute("INSERT INTO agent_heartbeats (agent_id,cpu,memory,disk,processes,load_avg,reported_at) VALUES (?,?,?,?,?,?,?)", (aid,cpu,mem,disk,procs,load,ts))

# Alerts (12)
alerts_data = [
    ("a1","ALT-20260623-001","kylin-node-03","ransomware","critical","new","10.0.1.200","10.0.1.103",4444,"TCP","Impact","T1486","Data Encrypted for Impact","勒索软件行为：大量文件被加密修改（.kylin后缀），涉及 /data/db/ 目录2847个文件"),
    ("a2","ALT-20260623-002","kylin-node-01","lateral_movement","critical","new","10.0.1.101","10.0.1.103",445,"TCP","Lateral Movement","T1021.002","Remote Services","横向移动：从节点01到03的SMB连接异常，使用非标准凭据"),
    ("a3","ALT-20260623-003","kylin-node-06","webshell","critical","new","10.0.1.106","10.0.2.50",80,"TCP","Persistence","T1505.003","Web Shell","检测到WebShell文件：/var/www/html/uploads/shell.php"),
    ("a4","ALT-20260623-004","kylin-node-02","brute_force","high","acknowledged","10.0.3.15","10.0.1.102",22,"TCP","Credential Access","T1110","Brute Force","SSH暴力破解检测：来自10.0.3.15在5分钟内尝试了156次登录"),
    ("a5","ALT-20260623-005","kylin-node-07","privilege_escalation","high","investigating","10.0.1.107","10.0.1.107",0,"N/A","Privilege Escalation","T1068","Exploitation for Privilege Escalation","权限提升：普通用户john通过CVE-2024-21887获取了root权限"),
    ("a6","ALT-20260623-006","kylin-node-01","data_exfil","high","new","10.0.1.101","203.0.113.45",443,"TCP","Exfiltration","T1048.003","Exfiltration Over Alternative Protocol","数据外泄：kylin-node-01向外部IP发送了2.3GB数据"),
    ("a7","ALT-20260623-007","kylin-node-04","malware","medium","acknowledged","10.0.1.104","10.0.1.104",0,"N/A","Execution","T1204.002","Malicious File","恶意软件：/tmp/.cache/d64a3f匹配已知恶意软件库"),
    ("a8","ALT-20260623-008","kylin-node-03","c2_communication","high","new","10.0.1.103","198.51.100.23",8080,"TCP","Command and Control","T1071.001","Web Protocols","C2通信：每30秒向198.51.100.23:8080发送心跳包，符合已知C2模式"),
    ("a9","ALT-20260623-009","kylin-node-05","reconnaissance","medium","new","10.0.1.105","10.0.2.1",0,"TCP","Discovery","T1046","Network Service Discovery","侦察行为：对内网10.0.2.0/24段进行全端口扫描"),
    ("a10","ALT-20260623-010","kylin-node-06","file_integrity","low","resolved","10.0.1.106","10.0.1.106",0,"N/A","Persistence","T1098","Account Manipulation","文件完整性：/etc/passwd变更，新增用户temp_admin"),
    ("a11","ALT-20260623-011","kylin-node-02","anomalous_login","high","acknowledged","61.144.0.0","10.0.1.102",22,"TCP","Defense Evasion","T1078","Valid Accounts","异常登录：管理员用户在03:47AM从异地IP登录"),
    ("a12","ALT-20260623-012","kylin-node-08","container_escape","medium","new","10.0.1.108","10.0.1.108",0,"N/A","Privilege Escalation","T1611","Escape to Host","容器逃逸：Docker容器尝试挂载宿主机/proc文件系统"),
]
for a in alerts_data:
    ts = (datetime.now() - timedelta(hours=random.randint(1,12))).isoformat()
    c.execute("INSERT OR IGNORE INTO alerts (id,alert_id,agent_id,event_type,severity,status,source_ip,dest_ip,port,protocol,mitre_tactic,mitre_technique,mitre_technique_name,description,raw_data,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", a + (f'{{"detection_source":"agent_v3.2.0"}}', ts))

# Policies (6)
policies_data = [
    ("p1","全局入侵检测规则集","intrusion_detection",3,"rules:\n  - name: ssh_brute_force\n    match: Failed password\n    threshold: 5\n    window: 60s",'["all"]',1,2847,"全局入侵检测规则"),
    ("p2","WebShell检测规则","webshell_detection",2,"rules:\n  - name: php_webshell\n    match: eval|base64_decode|system\n    paths: ['/var/www/html']",'["tag:web"]',1,156,"WebShell文件检测"),
    ("p3","基线合规检查","baseline_compliance",1,"checks:\n  - name: password_policy\n    min_length: 12\n    require_mfa: true",'["all"]',0,89,"系统基线合规检查"),
    ("p4","异常网络行为检测","network_anomaly",4,"rules:\n  - name: data_exfil\n    threshold_bytes: 1073741824\n    window: 300s",'["all"]',1,423,"异常网络连接检测"),
    ("p5","恶意软件查杀","malware_scan",2,"scan:\n  - paths: ['/tmp','/var/tmp']\n    interval: 3600s",'["tag:production"]',1,892,"定期扫描恶意软件"),
    ("p6","容器安全策略","container_security",1,"rules:\n  - name: container_escape\n    match: privileged|host_pid|host_network",'["tag:container"]',1,67,"容器运行时安全检测"),
]
c.executemany("INSERT OR IGNORE INTO policies (id,name,type,version,content_yaml,target_scope,enabled,hit_count,description) VALUES (?,?,?,?,?,?,?,?,?)", policies_data)

# Audit logs (12)
actions = ["login","policy.update","alert.resolve","agent.upgrade","strategy.deploy","user.create","user.lock","alert.acknowledge","policy.create","system.config","agent.restart","logout"]
users_audit = ["admin","zhangsan","wangwu"]
for i in range(12):
    aid = f"LOG-20260623-{i+1:04d}"
    ts = (datetime.now() - timedelta(hours=i)).isoformat()
    c.execute("INSERT OR IGNORE INTO audit_logs (id,user_id,username,action,resource_type,resource_id,detail,created_at) VALUES (?,?,?,?,?,?,?,?)",
              (aid, users_audit[i%3], users_audit[i%3], actions[i], "system", f"res-{i}", f'{{"detail":"操作#{i+1}"}}', ts))

conn.commit()
conn.close()
sz = os.path.getsize(DB_PATH)
print(f"Seed complete! DB: {DB_PATH} ({sz} bytes)")
print("Seeded: 6 users, 4 roles, 8 agents, 120 heartbeats, 12 alerts, 6 policies, 12 audit logs")
