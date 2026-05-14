#!/usr/bin/env python3
"""快照当前状态到 CHECKPOINT.md + SESSION_RECOVERY.md"""
import os, json, sys
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

# 读取当前 checkpoint
cp_path = os.path.join(WORKSPACE, "CHECKPOINT.md")
with open(cp_path) as f:
    cp = f.read()

# 追加到每日日志
daily_path = os.path.join(WORKSPACE, "memory", f"{datetime.now().strftime('%Y-%m-%d')}.md")
entry = f"\n## [{NOW}] 检查点快照\n{cp.split('---')[0]}\n"
with open(daily_path, "a") as f:
    f.write(entry)

print(f"✅ 状态已快照至 {daily_path}")
