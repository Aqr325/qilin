"""
Seed: create tables + data via sync sqlite3 (no ORM).
Column names match the ORM models exactly.
"""
import os, sys, json, random, uuid, sqlite3, bcrypt
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kylin_secops_dev.db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

row = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
has_tables = row[0] > 0

if has_tables:
    row2 = c.execute("SELECT COUNT(*) FROM users").fetchone()
    if row2[0] > 0:
        print(f"Already has {row2[0]} users, skipping")
        conn.close()
        exit(0)

# ═══════════════════════ DROP + CREATE TABLES ═══════════════════════
c.executescript("""
DROP TABLE IF EXISTS policy_targets;
DROP TABLE IF EXISTS policy_versions;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS login_logs;
DROP TABLE IF EXISTS alert_status_history;
DROP TABLE IF EXISTS ai_conversations;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS agent_heartbeats;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS user_roles;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS permissions;

-- Permissions (TimestampMixin → created_at, updated_at)
CREATE TABLE permissions (
    id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    module TEXT NOT NULL, action TEXT NOT NULL,
    description TEXT, created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_permissions_code ON permissions(code);
CREATE INDEX idx_permissions_module ON permissions(module);

-- Roles (TimestampMixin)
CREATE TABLE roles (
    id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
    description TEXT, is_system INTEGER DEFAULT 0,
    created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_roles_name ON roles(name);

-- Role-Permissions (association)
CREATE TABLE role_permissions (
    role_id TEXT REFERENCES roles(id) ON DELETE CASCADE,
    permission_id TEXT REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY(role_id, permission_id));

-- Users (TimestampMixin + SoftDeleteMixin)
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    is_active INTEGER DEFAULT 1,
    is_locked INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    login_attempts INTEGER DEFAULT 0,
    last_login_at TIMESTAMP,
    last_login_ip TEXT,
    mfa_enabled INTEGER DEFAULT 0,
    mfa_secret TEXT,
    password_changed_at TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- User-Roles (association)
CREATE TABLE user_roles (
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    role_id TEXT REFERENCES roles(id) ON DELETE CASCADE,
    granted_by TEXT REFERENCES users(id),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, role_id));

-- Agents (TimestampMixin + SoftDeleteMixin)
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    agent_id TEXT UNIQUE NOT NULL,
    hostname TEXT NOT NULL,
    ip_address TEXT,
    os_version TEXT NOT NULL,
    kernel_version TEXT,
    agent_version TEXT NOT NULL,
    cpu_cores INTEGER NOT NULL,
    total_memory INTEGER NOT NULL,
    disk_total INTEGER,
    status TEXT NOT NULL DEFAULT 'offline',
    last_heartbeat TIMESTAMP,
    last_heartbeat_ip TEXT,
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    config_version INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_agents_agent_id ON agents(agent_id);
CREATE INDEX idx_agents_status ON agents(status);

-- AgentHeartbeats (Base only → no TimestampMixin)
CREATE TABLE agent_heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cpu_usage REAL,
    cpu_cores INTEGER,
    memory_total INTEGER,
    memory_used INTEGER,
    memory_percent REAL,
    disk_json TEXT,
    processes_total INTEGER,
    processes_running INTEGER,
    agent_version TEXT,
    payload TEXT NOT NULL,
    ip_address TEXT);
CREATE INDEX idx_hb_agent_id ON agent_heartbeats(agent_id);
CREATE INDEX idx_hb_received ON agent_heartbeats(received_at);

-- Alerts (TimestampMixin + SoftDeleteMixin)
CREATE TABLE alerts (
    id TEXT PRIMARY KEY,
    alert_seq INTEGER NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    detail TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    status_changed_at TIMESTAMP,
    mitre_technique_id TEXT,
    mitre_tactic TEXT,
    mitre_technique_name TEXT,
    assignee_id TEXT,
    assigned_at TIMESTAMP,
    suppressed INTEGER DEFAULT 0,
    suppressed_until TIMESTAMP,
    suppress_reason TEXT,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    correlation_key TEXT,
    correlation_count INTEGER DEFAULT 1,
    first_detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    alert_count INTEGER DEFAULT 1,
    source_ip VARCHAR(45),
    is_deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_alerts_seq ON alerts(alert_seq);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_agent ON alerts(agent_id);

-- Policies (TimestampMixin + SoftDeleteMixin)
CREATE TABLE policies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    policy_type TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    rules TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    target_type TEXT NOT NULL DEFAULT 'tag',
    target_value TEXT,
    priority INTEGER DEFAULT 5,
    effective_start TIMESTAMP,
    effective_end TIMESTAMP,
    is_template INTEGER DEFAULT 0,
    created_by TEXT,
    updated_by TEXT,
    deployed_version INTEGER DEFAULT 0,
    last_deployed_at TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_policies_type ON policies(policy_type);
CREATE INDEX idx_policies_status ON policies(status);
CREATE INDEX idx_policies_name ON policies(name);

-- LoginLogs (Base only)
CREATE TABLE login_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT REFERENCES users(id),
    username TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_reason TEXT,
    ip_address TEXT NOT NULL,
    user_agent TEXT,
    session_id TEXT,
    auth_method TEXT DEFAULT 'password',
    login_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX idx_login_user ON login_logs(user_id);
CREATE INDEX idx_login_username ON login_logs(username);
CREATE INDEX idx_login_time ON login_logs(login_at);

-- AuditLogs (Base only)
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT REFERENCES users(id),
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    resource_name TEXT,
    detail TEXT,
    ip_address TEXT,
    user_agent TEXT,
    duration_ms INTEGER,
    result TEXT DEFAULT 'success',
    error_message TEXT,
    correlation_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_type ON audit_logs(resource_type);

-- AiConversations (TimestampMixin)
CREATE TABLE ai_conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT,
    messages TEXT NOT NULL,
    context TEXT,
    related_alert_id TEXT,
    feedback_score INTEGER,
    feedback_comment TEXT,
    token_usage INTEGER DEFAULT 0,
    model_name TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE INDEX idx_conv_user ON ai_conversations(user_id);

-- AlertStatusHistory (Base only)
CREATE TABLE alert_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL REFERENCES alerts(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    operator_id TEXT,
    operator_name TEXT,
    operation TEXT NOT NULL,
    comment TEXT,
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP);

-- PolicyVersions (Base only)
CREATE TABLE policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies(id),
    version INTEGER NOT NULL,
    rules TEXT NOT NULL,
    changelog TEXT,
    created_by TEXT,
    created_at TIMESTAMP);

-- PolicyTargets (Base only)
CREATE TABLE policy_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id TEXT NOT NULL REFERENCES policies(id),
    agent_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    deployed_version INTEGER,
    deployed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0);
""")
print("Tables created OK")

# ═══════════════════════ SEED DATA ═══════════════════════
now = datetime.utcnow()
now_s = now.strftime("%Y-%m-%d %H:%M:%S")

# ── Permissions ──
perm_ids = {}
for code, name, module, action, desc in [
    ("system:user","用户管理","system","manage","用户管理"),
    ("system:role","角色管理","system","manage","角色管理"),
    ("policy:write","策略配置","policy","write","策略配置"),
    ("policy:read","策略查看","policy","read","策略查看"),
    ("agent:write","Agent管理","agent","write","Agent管理"),
    ("agent:read","Agent查看","agent","read","Agent查看"),
    ("alert:write","告警处置","alert","write","告警处置"),
    ("alert:read","告警查看","alert","read","告警查看"),
    ("system:config","系统配置","system","config","系统配置"),
    ("log:read","日志查看","log","read","日志查看"),
    ("audit:read","系统审计","audit","read","系统审计"),
    ("dashboard:read","仪表盘","dashboard","read","仪表盘"),
]:
    pid = str(uuid.uuid4())
    perm_ids[code] = pid
    c.execute("INSERT INTO permissions (id,code,name,module,action,description,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
              (pid,code,name,module,action,desc,now_s,now_s))
print(f"  Permissions: {len(perm_ids)}")

# ── Roles ──
role_ids = {}
for rname, dname, desc in [
    ("admin","管理员","系统管理员，拥有全部权限"),
    ("operator","运维员","运维操作员"),
    ("auditor","审计员","审计员"),
    ("readonly","只读","只读用户"),
]:
    rid = str(uuid.uuid4())
    role_ids[rname] = rid
    c.execute("INSERT INTO roles (id,name,display_name,description,is_system,created_at,updated_at) VALUES (?,?,?,?,1,?,?)",
              (rid,rname,dname,desc,now_s,now_s))
print(f"  Roles: {len(role_ids)}")

rp_map = {
    "admin": list(perm_ids.values()),
    "operator": [perm_ids[x] for x in ["policy:write","policy:read","agent:write","agent:read","alert:write","alert:read"]],
    "auditor": [perm_ids[x] for x in ["log:read","audit:read","dashboard:read"]],
    "readonly": [perm_ids["dashboard:read"]],
}
rp_count = 0
for rname, pids in rp_map.items():
    for pid in pids:
        c.execute("INSERT INTO role_permissions (role_id,permission_id) VALUES (?,?)", (role_ids[rname], pid))
        rp_count += 1
print(f"  Role-Permissions: {rp_count}")

# ── Users ──
pwd = bcrypt.hashpw(b"admin123", bcrypt.gensalt(4)).decode()
user_ids = {}
for uname, email, dname, role_name, active, locked, attempts in [
    ("admin","admin@kylin.local","系统管理员","admin",1,0,0),
    ("zhangsan","zhangsan@kylin.local","张三","operator",1,0,0),
    ("lisi","lisi@kylin.local","李四","operator",1,1,3),
    ("wangwu","wangwu@kylin.local","王五","auditor",1,0,0),
    ("zhaoliu","zhaoliu@kylin.local","赵六","readonly",1,0,0),
    ("security-ops","secops@kylin.local","安全运维","operator",0,0,0),
]:
    uid = str(uuid.uuid4())
    user_ids[uname] = uid
    c.execute("INSERT INTO users (id,username,password_hash,display_name,email,is_active,is_locked,login_attempts,mfa_enabled,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,0,?,?)",
              (uid,uname,pwd,dname,email,active,locked,attempts,now_s,now_s))
    c.execute("INSERT INTO user_roles (user_id,role_id) VALUES (?,?)", (uid, role_ids[role_name]))
print(f"  Users: {len(user_ids)}")

# ── Agents ──
agent_ids = {}
for aid, ip, osv, ver, status, cores, mem, disk, tags in [
    ("kylin-node-01","10.0.1.101","麒麟V10 SP1","3.2.0","online",8,16384,500,'["production","web"]'),
    ("kylin-node-02","10.0.1.102","麒麟V10","3.2.0","online",8,32768,1000,'["production","db"]'),
    ("kylin-node-03","10.0.1.103","银河麒麟V10","3.2.0","online",16,65536,2000,'["production","web"]'),
    ("kylin-node-04","10.0.1.104","麒麟V10 SP1","3.2.1","online",4,8192,250,'["staging","web"]'),
    ("kylin-node-05","10.0.1.105","麒麟V10","3.2.0","offline",8,16384,500,'["production","web"]'),
    ("kylin-node-06","10.0.1.106","银河麒麟V10","3.2.0","error",16,65536,2000,'["production","db"]'),
    ("kylin-node-07","10.0.1.107","麒麟V10 SP1","3.2.0","online",8,16384,1000,'["production","app"]'),
    ("kylin-node-08","10.0.1.108","麒麟V10","3.2.0","pending",4,4096,120,'["staging"]'),
]:
    agid = str(uuid.uuid4())
    agent_ids[aid] = agid
    c.execute("INSERT INTO agents (id,agent_id,hostname,ip_address,os_version,cpu_cores,total_memory,disk_total,agent_version,status,tags,first_seen_at,registered_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (agid,aid,aid,ip,osv,cores,mem,disk,ver,status,json.dumps(json.loads(tags)),now_s,now_s,now_s,now_s))
print(f"  Agents: {len(agent_ids)}")

# ── Heartbeats ──
hb_count = 0
for aid_key in ["kylin-node-01","kylin-node-02","kylin-node-03","kylin-node-04","kylin-node-07"]:
    ag_uid = agent_ids[aid_key]
    for h in range(24):
        ts = (now - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")
        cpu = round(random.uniform(10,90),1)
        mp = round(random.uniform(20,90),1)
        c.execute("INSERT INTO agent_heartbeats (agent_id,received_at,cpu_usage,cpu_cores,memory_total,memory_used,memory_percent,disk_json,processes_total,payload,ip_address) VALUES (?,?,?,8,16384,?,?,?,?,?,'10.0.1.1')",
                  (ag_uid,ts,cpu,int(16384*mp/100),mp,
                   json.dumps({"/":{"total":500,"used":round(200+cpu*2),"percent":round(40+cpu*0.3,1)}}),
                   random.randint(150,500),json.dumps({"source":"agent_v3.2.0"})))
        hb_count += 1
print(f"  Heartbeats: {hb_count}")

# ── Alerts ──
alert_data = [
    ("kylin-node-03","ransomware","critical","new","勒索软件行为","T1486","Impact","Data Encrypted for Impact"),
    ("kylin-node-01","lateral_movement","critical","acknowledged","横向移动检测","T1021.002","Lateral Movement","Remote Services"),
    ("kylin-node-06","webshell","critical","investigating","WebShell文件检测","T1505.003","Persistence","Web Shell"),
    ("kylin-node-02","brute_force","high","new","SSH暴力破解","T1110","Credential Access","Brute Force"),
    ("kylin-node-07","privilege_escalation","high","new","权限提升检测","T1068","Privilege Escalation","Exploitation for Privilege Escalation"),
    ("kylin-node-01","data_exfil","high","acknowledged","数据外泄检测","T1048.003","Exfiltration","Exfiltration Over Alternative Protocol"),
    ("kylin-node-04","malware","medium","new","恶意软件检测","T1204.002","Execution","Malicious File"),
    ("kylin-node-03","c2_communication","high","investigating","C2通信检测","T1071.001","Command and Control","Web Protocols"),
    ("kylin-node-05","reconnaissance","medium","new","侦察行为检测","T1046","Discovery","Network Service Discovery"),
    ("kylin-node-06","file_integrity","low","resolved","文件完整性变更","T1098","Persistence","Account Manipulation"),
    ("kylin-node-02","anomalous_login","high","acknowledged","异常登录告警","T1078","Defense Evasion","Valid Accounts"),
    ("kylin-node-08","container_escape","medium","new","容器逃逸检测","T1611","Privilege Escalation","Escape to Host"),
]
for seq, (aid_name, atype, severity, status, title, tech_id, tactic, tech_name) in enumerate(alert_data, 1):
    alert_id = str(uuid.uuid4())
    ag_uid = agent_ids[aid_name]
    ts = (now - timedelta(hours=random.randint(1,12))).strftime("%Y-%m-%d %H:%M:%S")
    src_ip = f"10.0.{random.randint(0,255)}.{random.randint(1,254)}"
    c.execute("INSERT INTO alerts (id,alert_seq,agent_id,alert_type,severity,title,description,source,status,mitre_technique_id,mitre_tactic,mitre_technique_name,first_detected_at,last_detected_at,alert_count,source_ip,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'agent',?,?,?,?,?,?,1,?,?,?)",
              (alert_id,seq,ag_uid,atype,severity,title,f"{title}检测事件",
               status,tech_id,tactic,tech_name,ts,ts,src_ip,ts,ts))
print(f"  Alerts: {len(alert_data)}")

# ── Policies ──
policy_count = 0
for pname, ptype, enabled, ver, rules_json in [
    ("全局入侵检测规则集","intrusion_detection",1,3,'{"rules":[{"name":"ssh_brute_force","match":"Failed password","threshold":5,"window":"60s"}]}'),
    ("WebShell检测规则","webshell_detection",1,2,'{"rules":[{"name":"php_webshell","match":"eval|base64_decode","paths":["/var/www/html"]}]}'),
    ("基线合规检查","baseline_compliance",0,1,'{"checks":[{"name":"password_policy","min_length":12,"require_mfa":true}]}'),
    ("异常网络行为检测","network_anomaly",1,4,'{"rules":[{"name":"data_exfil","threshold_bytes":1073741824,"window":"300s"}]}'),
    ("恶意软件查杀","malware_scan",1,2,'{"scan":{"paths":["/tmp","/var/tmp"],"interval":"3600s"}}'),
    ("容器安全策略","container_security",1,1,'{"rules":[{"name":"container_escape","match":"privileged|host_pid"}]}'),
]:
    pid = str(uuid.uuid4())
    c.execute("INSERT INTO policies (id,name,policy_type,enabled,status,version,rules,target_type,target_value,priority,created_at,updated_at) VALUES (?,?,?,?,'active',?,?,'tag','[]',5,?,?)",
              (pid,pname,ptype,enabled,ver,rules_json,now_s,now_s))
    policy_count += 1
print(f"  Policies: {policy_count}")

# ── LoginLogs ──
ll_count = 0
for i, (uname, status, reason) in enumerate([
    ("admin","success",None),("admin","success",None),
    ("zhangsan","success",None),("lisi","failed","wrong_password"),
    ("lisi","failed","wrong_password"),("lisi","failed","wrong_password"),
    ("admin","success",None),
]):
    lt = (now - timedelta(hours=i*3)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO login_logs (user_id,username,status,failure_reason,ip_address,user_agent,auth_method,login_at) VALUES (?,?,?,?,'10.0.1.1','Mozilla/5.0','password',?)",
              (user_ids.get(uname),uname,status,reason,lt))
    ll_count += 1
print(f"  LoginLogs: {ll_count}")

# ── AuditLogs ──
al_count = 0
for i, (uname, action, rtype, rid, rname) in enumerate([
    ("admin","login","system","",""),("admin","policy.update","policy","p1","全局入侵检测规则集"),
    ("zhangsan","alert.resolve","alert","a4",""),("admin","agent.upgrade","agent","kylin-node-01",""),
    ("zhangsan","strategy.deploy","policy","",""),("admin","user.create","user","u6",""),
    ("admin","user.lock","user","u3",""),("zhangsan","alert.acknowledge","alert","a7",""),
    ("wangwu","policy.create","policy","",""),("admin","system.config","system","",""),
    ("zhangsan","agent.restart","agent","kylin-node-06",""),("admin","logout","system","",""),
]):
    at = (now - timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_logs (user_id,username,action,resource_type,resource_id,resource_name,detail,ip_address,result,created_at) VALUES (?,?,?,?,?,?,?,'10.0.1.1','success',?)",
              (user_ids[uname],uname,action,rtype,rid,rname,json.dumps({"detail":f"操作#{i+1}"}),at))
    al_count += 1
print(f"  AuditLogs: {al_count}")

conn.commit()
conn.close()
print()
print(f"Seed complete! DB: {DB_PATH}")
print(f"Summary: {len(user_ids)} users, {len(role_ids)} roles, {len(perm_ids)} permissions, {len(agent_ids)} agents, {hb_count} heartbeats, {len(alert_data)} alerts, {policy_count} policies, {ll_count} login_logs, {al_count} audit_logs")