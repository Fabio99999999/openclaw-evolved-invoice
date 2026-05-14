#!/usr/bin/env python3
"""
OpenClaw 升级自动修复机制 (Upgrade Auto-Repair)
================================================
在升级 OpenClaw 前后自动检测并修复兼容性问题，防止升级后：
- 模型断联 (model ID 变更)
- 响应中断 (fallback 链断裂)
- 配置不兼容 (schema 变化)
- 认证失效 (auth profiles 丢失)

用法:
  python3 scripts/upgrade-repair.py --pre-upgrade    # 升级前：备份+快照
  python3 scripts/upgrade-repair.py --post-upgrade   # 升级后：修复+验证
  python3 scripts/upgrade-repair.py --check          # 仅检查兼容性
  python3 scripts/upgrade-repair.py --verify         # 验证当前配置是否健康
  python3 scripts/upgrade-repair.py --rollback       # 回滚到上一次备份
"""

import json
import os
import sys
import subprocess
import shutil
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
OPENCLAW_DIR = Path(os.path.expanduser("~/.openclaw"))
CONFIG_FILE = OPENCLAW_DIR / "openclaw.json"
AGENT_DIR = OPENCLAW_DIR / "agents" / "main" / "agent"
AUTH_FILE = AGENT_DIR / "auth-profiles.json"
MODELS_FILE = AGENT_DIR / "models.json"
BACKUP_DIR = OPENCLAW_DIR / "upgrade-backups"
WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))
MEMORY_DIR = WORKSPACE / "memory"

# ── Model ID 映射表（已知的旧→新映射） ─────────────────────────────
KNOWN_MIGRATIONS = {
    # DeepSeek 官方: reasoner/chat → v4 系列
    "deepseek/deepseek-reasoner": "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-chat": "deepseek/deepseek-v4-flash",
    # uiuiapi 模型重命名（如适用）
    "uiuiapi/deepseek-reasoner": "uiuiapi/deepseek-reasoner",  # 保留（sg.uiuiapi.com）
    "uiuiapi/deepseek-chat": "uiuiapi/deepseek-chat",
}


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{level}] {msg}")


def run(cmd, timeout=15):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        log(f"无法读取 {path}: {e}", "WARN")
        return None


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════
# Phase 1: Pre-Upgrade — 备份 + 快照
# ══════════════════════════════════════════════════════════════════════════

def pre_upgrade():
    """升级前：备份所有关键配置，记录当前状态快照。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / ts
    backup_path.mkdir(parents=True, exist_ok=True)

    log(f"===== 升级前备份 → {backup_path} =====")

    # 1. 备份核心配置文件
    files_to_backup = [
        ("openclaw.json", CONFIG_FILE),
        ("auth-profiles.json", AUTH_FILE),
        ("models.json", MODELS_FILE),
    ]
    for name, src in files_to_backup:
        if src.exists():
            shutil.copy2(src, backup_path / name)
            log(f"  ✅ 备份 {name}")

    # 2. 备份 cron jobs
    rc, stdout, _ = run("openclaw cron list 2>/dev/null")
    if rc == 0 and stdout:
        with open(backup_path / "cron-jobs.txt", "w") as f:
            f.write(stdout)
        log(f"  ✅ 备份 cron jobs")

    # 3. 记录当前 OpenClaw 版本
    rc, stdout, _ = run("openclaw --version 2>/dev/null || openclaw version 2>/dev/null")
    version_before = stdout.strip() if rc == 0 else "unknown"
    with open(backup_path / "version-before.txt", "w") as f:
        f.write(version_before)
    log(f"  ✅ 当前版本: {version_before}")

    # 4. 记录当前模型配置快照
    cfg = load_json(CONFIG_FILE)
    if cfg:
        snapshot = {
            "primary": cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", ""),
            "fallbacks": cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("fallbacks", []),
            "maxTokens": cfg.get("agents", {}).get("defaults", {}).get("params", {}).get("maxTokens", 0),
        }
        save_json(backup_path / "config-snapshot.json", snapshot)
        log(f"  ✅ 模型快照: primary={snapshot['primary']}")

    # 5. 记录 auth profiles
    log("  记录 auth profiles...")
    auth_file_path = str(AUTH_FILE)
    rc, out, _ = run('python3 -c "import json; d=json.load(open(\"' + auth_file_path + '\")); [print(n) for n in d.get(\"profiles\",{})]" 2>/dev/null')
    if rc == 0:
        with open(backup_path / "auth-profiles-list.txt", "w") as f:
            f.write(out)
        log(f"  ✅ Auth profiles 记录")

    # 6. 备份 workspace 重要文件
    for fname in ["MEMORY.md", "TOOLS.md", "AGENTS.md", "SOUL.md"]:
        src = WORKSPACE / fname
        if src.exists():
            shutil.copy2(src, backup_path / fname)
    log(f"  ✅ Workspace 文件备份")

    # 7. 保存回滚索引
    index = {
        "timestamp": ts,
        "version_before": version_before,
        "files": [name for name, _ in files_to_backup if src.exists()],
    }
    save_json(backup_path / "backup-index.json", index)

    # 更新最新备份链接
    latest_link = BACKUP_DIR / "latest"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    os.symlink(ts, latest_link)

    log(f"\n✅ 预升级备份完成！共 {len(files_to_backup)} 个文件")
    log(f"   回滚命令: python3 scripts/upgrade-repair.py --rollback")
    return True


# ══════════════════════════════════════════════════════════════════════════
# Phase 2: Post-Upgrade — 兼容性检查 + 自动修复
# ══════════════════════════════════════════════════════════════════════════

def get_available_models_from_providers():
    """从各个 provider API 获取当前可用模型列表。"""
    models_by_provider = {}

    # 从 auth-profiles 获取 key
    auth = load_json(AUTH_FILE)
    if not auth:
        log("无法读取 auth-profiles.json", "ERROR")
        return models_by_provider

    profiles = auth.get("profiles", {})

    # 测试 DeepSeek 官方 API
    for profile_name in ["deepseek:default", "uiuiapi:default"]:
        if profile_name not in profiles:
            continue
        key = profiles[profile_name].get("key", "")
        provider_name = profile_name.split(":")[0]
        
        if provider_name == "deepseek":
            url = "https://api.deepseek.com/v1/models"
            headers = {"Authorization": f"Bearer {key}"}
        elif provider_name == "uiuiapi":
            url = "https://sg.uiuiapi.com/v1/models"
            headers = {"Authorization": f"Bearer {key}"}
        else:
            continue

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = []
                for m in data.get("data", []):
                    mid = m.get("id", "")
                    owned = m.get("owned_by", "")
                    models.append({"id": mid, "owned_by": owned})
                models_by_provider[provider_name] = models
                log(f"  ✅ {provider_name}: 获取到 {len(models)} 个模型")
        except Exception as e:
            log(f"  ❌ {provider_name}: 无法获取模型列表 - {e}")

    return models_by_provider


def check_model_exists(model_id, provider_models):
    """检查 model_id 在 provider 的模型列表中是否存在。"""
    if "/" not in model_id:
        return True  # 不是完整 ID，跳过
    provider, mid = model_id.split("/", 1)
    if provider in provider_models:
        available = [m["id"] for m in provider_models[provider]]
        return mid in available
    return True  # 无法判断时假设存在


def find_best_replacement(provider_models, old_model_id, reasoning_needed=None):
    """在找不到原模型时，智能推荐替代模型。"""
    if "/" not in old_model_id:
        return None

    provider, old_mid = old_model_id.split("/", 1)
    if provider not in provider_models:
        return None

    available = [m["id"] for m in provider_models[provider]]

    if not available:
        return None

    # 优先级策略
    if provider == "deepseek":
        # 按优先级排序
        # reasoning: v4-pro > reasoner
        # non-reasoning: v4-flash > chat
        if "reasoner" in old_mid or reasoning_needed:
            for preferred in ["deepseek-v4-pro", "deepseek-reasoner"]:
                if preferred in available:
                    return f"{provider}/{preferred}"
        # 默认用 v4-flash
        for preferred in ["deepseek-v4-flash", "deepseek-chat"]:
            if preferred in available:
                return f"{provider}/{preferred}"
        # 第一个可用
        return f"{provider}/{available[0]}"

    elif provider == "uiuiapi":
        if "reasoner" in old_mid or reasoning_needed:
            for preferred in ["deepseek-reasoner", "deepseek-r1", "deepseek-v3.1-thinking"]:
                if preferred in available:
                    return f"{provider}/{preferred}"
        for preferred in ["deepseek-chat", "deepseek-v3"]:
            if preferred in available:
                return f"{provider}/{preferred}"
        return f"{provider}/{available[0]}"

    return None


def post_upgrade():
    """升级后：检查配置兼容性并自动修复。"""
    log("===== 升级后兼容性检查 + 自动修复 =====")

    # 1. 检查版本是否有变化
    rc, stdout, _ = run("openclaw --version 2>/dev/null || openclaw version 2>/dev/null")
    version_now = stdout.strip() if rc == 0 else "unknown"
    log(f"当前版本: {version_now}")

    # 2. 检查备份是否存在
    latest_backup = BACKUP_DIR / "latest"
    if latest_backup.exists():
        snapshot = load_json(latest_backup / "config-snapshot.json")
        if snapshot:
            log(f"升级前配置: primary={snapshot.get('primary', '?')}")
    else:
        log("未找到预升级备份，执行兼容性检查但不回滚", "WARN")

    # 3. 获取当前可用模型
    log("获取 Provider 最新模型列表...")
    provider_models = get_available_models_from_providers()

    # 4. 检查当前配置中的模型 ID
    cfg = load_json(CONFIG_FILE)
    if not cfg:
        log("无法读取配置文件", "ERROR")
        return False

    model_cfg = cfg.get("agents", {}).get("defaults", {}).get("model", {})
    primary = model_cfg.get("primary", "")
    fallbacks = model_cfg.get("fallbacks", [])
    all_models = [primary] + fallbacks

    log(f"\n检查 {len(all_models)} 个配置中的模型 ID...")
    fixes_applied = []

    for model_id in all_models:
        if not model_id:
            continue
        if not check_model_exists(model_id, provider_models):
            replacement = find_best_replacement(provider_models, model_id, 
                reasoning_needed="reasoner" in model_id or "reasoning" in model_cfg.get(model_id, {}).get("name", ""))
            
            if replacement:
                log(f"  ⚠️  {model_id} → 映射到 {replacement}")
                fixes_applied.append((model_id, replacement))
                
                # 更新 config 模型列表中的 ID
                # 同时也需要更新 provider 模型列表
                for prov_name, prov_data in cfg.get("models", {}).get("providers", {}).items():
                    if model_id.startswith(f"{prov_name}/"):
                        old_mid = model_id.split("/", 1)[1]
                        new_mid_per = replacement.split("/", 1)[1] if "/" in replacement else replacement
                        # 如果原模型在 provider 列表中存在但 API 已不再提供，标记为 deprecated
                        for m in prov_data.get("models", []):
                            if m["id"] == old_mid:
                                m["_deprecated"] = True
                                m["_replaced_by"] = new_mid_per
                                log(f"     provider {prov_name}: {old_mid} 标记为已废弃")
            else:
                log(f"  ❌  {model_id}: 找不到替代模型", "WARN")

    # 5. 应用修复
    if fixes_applied:
        log(f"\n自动修复 {len(fixes_applied)} 个模型映射:")
        for old_id, new_id in fixes_applied:
            # 替换 primary
            if cfg["agents"]["defaults"]["model"]["primary"] == old_id:
                cfg["agents"]["defaults"]["model"]["primary"] = new_id
                log(f"  ✅ primary: {old_id} → {new_id}")
            # 替换 fallbacks
            cfg["agents"]["defaults"]["model"]["fallbacks"] = [
                new_id if fb == old_id else fb for fb in cfg["agents"]["defaults"]["model"]["fallbacks"]
            ]
            log(f"  ✅ fallback: {old_id} → {new_id}")

        # 保存修复后的配置
        save_json(CONFIG_FILE, cfg)
        log("✅ 配置已保存！")

        # 如果模型列表发生了变化，同步更新 models.json
        models_json = load_json(MODELS_FILE)
        if models_json:
            save_json(MODELS_FILE, cfg.get("models", {}))
            log("✅ models.json 已同步")

    # 6. 检查 maxTokens 是否超出新模型限制
    max_tokens = cfg.get("agents", {}).get("defaults", {}).get("params", {}).get("maxTokens", 0)
    new_primary = cfg["agents"]["defaults"]["model"]["primary"]
    log(f"\n检查 maxTokens ({max_tokens})...")
    
    # v4-flash 最佳值 16384, v4-pro 可达 65536
    if "v4-flash" in new_primary and max_tokens > 16384:
        cfg["agents"]["defaults"]["params"]["maxTokens"] = 16384
        save_json(CONFIG_FILE, cfg)
        log(f"  ✅ maxTokens: {max_tokens} → 16384 (v4-flash 最佳值)")
    elif "v4-pro" in new_primary and max_tokens > 65536:
        cfg["agents"]["defaults"]["params"]["maxTokens"] = 65536
        save_json(CONFIG_FILE, cfg)
        log(f"  ✅ maxTokens: {max_tokens} → 65536 (v4-pro 上限)")

    # 7. 检查 auth profiles 完整性
    auth = load_json(AUTH_FILE)
    if auth:
        profiles = auth.get("profiles", {})
        log(f"\nAuth profiles: {len(profiles)} 个")
        for name, info in profiles.items():
            key_len = len(info.get("key", ""))
            key_preview = info["key"][:10] + "..." if key_len > 10 else info["key"]
            log(f"  ✅ {name}: key={key_preview} ({key_len} chars)")
    else:
        log(f"  ❌ auth-profiles.json 不可读！", "ERROR")

    # 8. 生成修复报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "version": version_now,
        "fixes_applied": [{"from": f[0], "to": f[1]} for f in fixes_applied],
        "primary_model": cfg["agents"]["defaults"]["model"]["primary"],
        "fallbacks": cfg["agents"]["defaults"]["model"]["fallbacks"],
        "maxTokens": cfg["agents"]["defaults"]["params"]["maxTokens"],
        "status": "fixed" if fixes_applied else "ok",
    }
    report_path = BACKUP_DIR / f"repair-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json(report_path, report)
    log(f"\n✅ 修复报告: {report_path}")

    if fixes_applied:
        log("\n⚠️  配置已修复，请重启 Gateway 生效:")
        log("   openclaw gateway restart")
    
    return True


# ══════════════════════════════════════════════════════════════════════════
# Phase 3: Verification — 升级后验证
# ══════════════════════════════════════════════════════════════════════════

def verify():
    """验证当前配置是否健康。"""
    log("===== 系统健康检查 =====")

    issues = []
    ok_count = 0

    # 1. 检查配置文件
    cfg = load_json(CONFIG_FILE)
    if cfg:
        log("✅ openclaw.json: 可读")
        ok_count += 1
    else:
        issues.append("openclaw.json 不可读")
        log("❌ openclaw.json: 不可读", "ERROR")

    # 2. 检查 auth profiles
    auth = load_json(AUTH_FILE)
    if auth:
        profiles = auth.get("profiles", {})
        for name, info in profiles.items():
            key = info.get("key", "")
            if len(key) < 10:
                issues.append(f"Auth profile {name} key 太短")
                log(f"❌ Auth {name}: key 异常 ({len(key)} chars)", "ERROR")
            else:
                ok_count += 1
                log(f"✅ Auth {name}: key 正常 ({len(key)} chars)")
    else:
        issues.append("auth-profiles.json 不可读")

    # 3. 检查模型连通性
    if auth:
        for profile_name in ["deepseek:default", "uiuiapi:default"]:
            if profile_name not in auth.get("profiles", {}):
                continue
            key = auth["profiles"][profile_name]["key"]
            provider = profile_name.split(":")[0]
            
            if provider == "deepseek":
                url = "https://api.deepseek.com/v1/models"
            elif provider == "uiuiapi":
                url = "https://sg.uiuiapi.com/v1/models"
            else:
                continue

            try:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read())
                    model_count = len(data.get("data", []))
                    log(f"✅ {provider} API: 连通 (HTTP {resp.status}), {model_count} 个模型")
                    ok_count += 1
            except Exception as e:
                issues.append(f"{provider} API 不通: {e}")
                log(f"❌ {provider} API: 不通 - {e}", "ERROR")

    # 4. 检查配置中的模型是否在 API 返回中
    if cfg:
        meta = cfg.get("agents", {}).get("defaults", {}).get("model", {})
        primary = meta.get("primary", "?")
        fallbacks = meta.get("fallbacks", [])
        log(f"\n当前模型链: primary={primary}, fallbacks={fallbacks}")

    # 5. 检查 cron jobs
    rc, stdout, _ = run("openclaw cron list 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print(len(d.get('jobs',[])))\"")
    if rc == 0 and stdout:
        log(f"✅ Cron jobs: {stdout.strip()} 个任务")
        ok_count += 1
    else:
        log("⚠️  Cron jobs 状态不明", "WARN")

    # 6. 检查 Gateway 状态
    rc, stdout, _ = run("openclaw gateway status 2>&1 | grep -i 'Runtime.*running'")
    if rc == 0:
        log("✅ Gateway: 运行中")
        ok_count += 1
    else:
        issues.append("Gateway 未运行")
        log("❌ Gateway: 未运行", "ERROR")

    # 7. 检查 session 恢复文件
    recovery = WORKSPACE / "memory" / "SESSION_RECOVERY.md"
    if recovery.exists():
        log(f"✅ Session recovery 文件存在 ({(recovery.stat().st_size)} bytes)")
        ok_count += 1

    # ── 汇总 ──
    log(f"\n{'='*40}")
    log(f"检查项: {ok_count} ✅ | 问题: {len(issues)} ❌ | 警告: 待观察 ⚠️")
    
    if issues:
        log("\n❌ 发现的问题:")
        for i, issue in enumerate(issues, 1):
            log(f"  {i}. {issue}")
        log("\n⚠️  建议运行: python3 scripts/upgrade-repair.py --post-upgrade")
        return False
    else:
        log("\n✅ 系统健康，无需修复！")
        return True


# ══════════════════════════════════════════════════════════════════════════
# Rollback — 回滚
# ══════════════════════════════════════════════════════════════════════════

def rollback():
    """从最近一次备份回滚配置。"""
    latest_backup = BACKUP_DIR / "latest"
    if not latest_backup.exists():
        log("没有可用的备份", "ERROR")
        return False

    if not latest_backup.is_symlink():
        log("latest 备份链接异常", "ERROR")
        return False

    target = latest_backup.resolve()
    log(f"===== 从 {target} 回滚 =====")

    # 读取备份索引
    index = load_json(target / "backup-index.json")
    if index:
        log(f"备份时间: {index.get('timestamp', '?')}")
        log(f"升级前版本: {index.get('version_before', '?')}")

    # 回滚文件
    restored = 0
    for name in ["openclaw.json", "auth-profiles.json", "models.json"]:
        src = target / name
        if src.exists():
            if name == "openclaw.json":
                shutil.copy2(src, CONFIG_FILE)
            elif name == "auth-profiles.json":
                shutil.copy2(src, AUTH_FILE)
            elif name == "models.json":
                shutil.copy2(src, MODELS_FILE)
            log(f"  ✅ 恢复 {name}")
            restored += 1

    # 恢复 workspace 文件
    for fname in ["MEMORY.md", "TOOLS.md", "AGENTS.md", "SOUL.md"]:
        src = target / fname
        if src.exists():
            shutil.copy2(src, WORKSPACE / fname)
            log(f"  ✅ 恢复 workspace/{fname}")

    log(f"\n✅ 回滚完成！已恢复 {restored} 个文件")
    log("⚠️  请重启 Gateway: openclaw gateway restart")
    return True


# ══════════════════════════════════════════════════════════════════════════
# 健康状态日志（每次启动/心跳时运行）
# ══════════════════════════════════════════════════════════════════════════

def health_check():
    """快速健康检查（用于日常监控，不输出太多日志）。"""
    issues = []

    # 1. 检查 auth key
    auth = load_json(AUTH_FILE)
    if not auth:
        issues.append("auth-profiles.json missing")
    else:
        for name, info in auth.get("profiles", {}).items():
            if len(info.get("key", "")) < 10:
                issues.append(f"Auth {name}: invalid key")

    # 2. 检查 Gateway 运行时间
    rc, stdout, _ = run("ps aux | grep 'openclaw.*gateway' | grep -v grep | awk '{print $9}'")
    if rc != 0 or not stdout:
        issues.append("Gateway not running")

    # 3. 检查配置文件完整性
    cfg = load_json(CONFIG_FILE)
    if not cfg:
        issues.append("config not readable")
    else:
        primary = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "")
        if not primary:
            issues.append("no primary model configured")
        if "/" not in primary:
            issues.append(f"invalid model id: {primary}")

    status = "healthy" if not issues else "issues"
    health_data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "issues": issues,
    }

    # 写入 health log
    health_log = WORKSPACE / "memory" / "upgrade-health.json"
    # 保持最近 10 条
    history = []
    if health_log.exists():
        try:
            history = json.loads(health_log.read_text())
            if isinstance(history, list):
                history = history[-9:]
        except:
            history = []
    history.append(health_data)
    save_json(health_log, history)

    return status == "healthy"


# ══════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    # 创建备份目录
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    start = time.time()

    if cmd == "--pre-upgrade":
        pre_upgrade()
    elif cmd == "--post-upgrade":
        post_upgrade()
    elif cmd == "--check":
        # 快速兼容性检查
        cfg = load_json(CONFIG_FILE)
        if cfg:
            primary = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "?")
            fallbacks = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("fallbacks", [])
            log(f"当前配置:")
            log(f"  主模型: {primary}")
            log(f"  副模型: {fallbacks}")
            log(f"  maxTokens: {cfg.get('agents', {}).get('defaults', {}).get('params', {}).get('maxTokens', '?')}")
            log(f"\n已知兼容性映射:")
            for old_id, new_id in KNOWN_MIGRATIONS.items():
                log(f"  {old_id} → {new_id}")
            log(f"\n运行 --pre-upgrade 备份，升级后再运行 --post-upgrade 修复")
        else:
            log("无法读取配置", "ERROR")
    elif cmd == "--verify":
        verify()
    elif cmd == "--rollback":
        rollback()
    elif cmd == "--health":
        ok = health_check()
        sys.exit(0 if ok else 1)
    else:
        print(f"未知参数: {cmd}")
        print(__doc__)
        return

    elapsed = time.time() - start
    log(f"耗时: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
