#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_model_config_e2e.py
真机/开发机对 backend.exe 做"按 id 编辑/删除配置"的无 GUI 冒烟回归。
覆盖：H1 强制改密拦截 -> 改密 -> 按 id 创建/编辑/设默认/删除(均 200)
      -> 已删 id 查询(404 非 500) -> 非法 id 查询(404 非 500)

用法:
  python verify_model_config_e2e.py --exe "路径/backend.exe" --config "路径/config.json"
  python verify_model_config_e2e.py --host 127.0.0.1:8000   # Agent 版(端口 8000)
不传 --exe/--config 时，会在脚本附近及常见位置自动查找。
仅用标准库，无需 pip 安装。
"""
import argparse
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

DEFAULT_SEED = "KylinSecOps@2026"
ADMIN = "admin"
CREATE_BODY = {
    "name": "e2e-test",
    "provider": "openai",
    "model": "gpt-4o",
    "api_url": "http://127.0.0.1:9999",
    "api_key": "sk-e2e-test",
}


def find_exe(arg):
    if arg:
        return arg
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (
        os.path.join(here, "backend.exe"),
        os.path.join(here, "resources", "backend.exe"),
        os.path.join(here, "..", "resources", "backend.exe"),
        os.path.join(os.getcwd(), "backend.exe"),
    ):
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


def find_config(arg, exe_path):
    if arg:
        return arg
    if exe_path:
        c = os.path.join(os.path.dirname(exe_path), "config.json")
        if os.path.isfile(c):
            return c
    here = os.path.dirname(os.path.abspath(__file__))
    c = os.path.join(here, "config.json")
    return c if os.path.isfile(c) else None


def request(host, method, path, token=None, body=None, timeout=15):
    conn = http.client.HTTPConnection(host, timeout=timeout)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body) if body is not None else None
    try:
        conn.request(method, path, body=data, headers=headers)
        r = conn.getresponse()
        raw = r.read().decode("utf-8", "replace")
    finally:
        conn.close()
    try:
        txt = json.loads(raw)
    except Exception:
        txt = raw
    return r.status, txt


def jget(t, *keys):
    cur = t
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def wait_health(host, tries=80):
    for _ in range(tries):
        try:
            s, _ = request(host, "GET", "/health")
            if s == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def login(host, username, password):
    s, t = request(host, "POST", "/api/v1/auth/login",
                   body={"username": username, "password": password})
    if s != 200:
        raise RuntimeError("login 失败 status=%s body=%r" % (s, t))
    token = jget(t, "data", "access_token")
    if not token:
        raise RuntimeError("login 响应缺少 data.access_token: %r" % (t,))
    return token


def main():
    ap = argparse.ArgumentParser(description="backend.exe 按 id 配置 冒烟测试")
    ap.add_argument("--exe")
    ap.add_argument("--config")
    ap.add_argument("--host", default="127.0.0.1:8001")
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--newpass", default="NewPass@2026")
    args = ap.parse_args()

    exe = find_exe(args.exe)
    cfg = find_config(args.config, exe)
    if not exe or not os.path.isfile(exe):
        print("找不到 backend.exe，请用 --exe 指定绝对路径")
        sys.exit(2)
    if not cfg or not os.path.isfile(cfg):
        print("找不到 config.json，请用 --config 指定绝对路径")
        sys.exit(2)

    tmp = tempfile.mkdtemp(prefix="kylin_e2e_")
    try:
        # 复制到隔离临时目录运行，避免污染真实 kylin_secops.db / secret.key
        shutil.copy(exe, os.path.join(tmp, "backend.exe"))
        shutil.copy(cfg, os.path.join(tmp, "config.json"))
        env = dict(os.environ)
        env["JWT_SECRET_KEY"] = os.urandom(24).hex()
        env["KYLIN_SEED_PASSWORD"] = args.seed

        # 端口占用自检：若目标 host:port 已有服务在响应，多半是上一次运行残留的
        # backend.exe（或你真机正在跑的实例），会导致登录/测试打到错误实例。明确报错
        # 退出，避免静默连错后端；不直接杀进程，以免误伤你正在使用的真实服务。
        try:
            s, _ = request(args.host, "GET", "/health", timeout=3)
            print("目标端口 %s 已有服务响应(status=%s)。请先结束占用该端口的 "
                  "backend.exe（如：taskkill /f /im backend.exe），再运行本脚本。" % (args.host, s))
            sys.exit(4)
        except Exception:
            pass

        proc = subprocess.Popen(
            [os.path.join(tmp, "backend.exe")], cwd=tmp, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("[*] 已启动 backend.exe (pid=%d)，等待 /health ..." % proc.pid)
        if not wait_health(args.host):
            print("backend 未在预期时间内就绪（检查 config.json 里 backend.port）")
            proc.kill()
            sys.exit(3)

        results = []

        def check(name, cond, detail=""):
            results.append(cond)
            mark = "PASS" if cond else "FAIL"
            print("  [%s] %s %s" % (mark, name, detail))

        base = "/api/v1/ai/model-configs"
        token = login(args.host, ADMIN, args.seed)

        # H1 强制改密：未改密前业务接口应 403
        s, _ = request(args.host, "GET", base, token=token)
        check("H1 强制改密拦截(未改密 GET->403)", s == 403, "status=%s" % s)

        # 改密
        s, _ = request(args.host, "PUT", "/api/v1/auth/me/password", token=token,
                         body={"old_password": args.seed, "new_password": args.newpass})
        check("改密 PUT /auth/me/password->200", s == 200, "status=%s" % s)

        token = login(args.host, ADMIN, args.newpass)

        # 创建
        s, t = request(args.host, "POST", base, token=token, body=CREATE_BODY)
        check("创建配置 POST->200", s == 200, "status=%s" % s)
        cid = jget(t, "data", "id")
        check("创建返回合法 id", bool(cid), "id=%s" % cid)

        if cid:
            # 编辑
            s, _ = request(args.host, "PUT", base + "/" + cid, token=token,
                             body={"name": "e2e-test-edit"})
            check("编辑配置 PUT->200", s == 200, "status=%s" % s)
            # 设默认
            s, _ = request(args.host, "PUT", base + "/" + cid + "/set-default", token=token)
            check("设默认 PUT set-default->200", s == 200, "status=%s" % s)
            # 查询存在
            s, _ = request(args.host, "GET", base + "/" + cid, token=token)
            check("查询存在 id->200", s == 200, "status=%s" % s)
            # 删除
            s, _ = request(args.host, "DELETE", base + "/" + cid, token=token)
            check("删除配置 DELETE->200", s == 200, "status=%s" % s)
            # 删除后查询 -> 404 (不再是 500)
            s, _ = request(args.host, "GET", base + "/" + cid, token=token)
            check("已删 id 查询->404(非500)", s == 404, "status=%s" % s)
        else:
            check("编辑/设默认/删除 (因无 id 跳过)", False, "前置创建失败")

        # 非法 id -> 404 或 422 (均非 500)
        # 说明：model-configs 路径参数声明为 UUID 类型，非法字符串在 FastAPI 校验层即被拦成 422；
        # 合法但不存在的 id 进 service 后查无 -> 404。二者都是 4xx 客户端错误，证明不再触发 500。
        s, _ = request(args.host, "GET", base + "/not-a-uuid", token=token)
        check("非法 id 查询->404/422(非500)", s in (404, 422), "status=%s" % s)

        # 收尾：同步杀掉子进程，释放文件锁
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

        passed = sum(1 for c in results if c)
        total = len(results)
        print("\n=== 结果: %d/%d 通过 ===" % (passed, total))
        if passed != total:
            print("有用例失败，请检查 backend 日志")
            sys.exit(1)
        print("全部通过：按 id 编辑/删除配置 UUID 修复在真实 backend.exe 上生效")
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
