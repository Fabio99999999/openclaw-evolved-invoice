#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# OpenClaw 进化版 v0.2 — 一键安装脚本
# 适用: macOS / Linux
# 用途: 发票自动化 + 全能办公助手
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🦞 OpenClaw 进化版 v0.2${NC}"
echo -e "${CYAN}  发票自动化 + 全能办公助手${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---- 检测系统 ----
OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "${GREEN}✓${NC} 系统: $OS $ARCH"

# ---- 检查 Node.js ----
if command -v node &>/dev/null; then
    NODE_VER=$(node -v)
    echo -e "${GREEN}✓${NC} Node.js: $NODE_VER"
else
    echo -e "${YELLOW}⚠ Node.js 未安装，需要 v18+${NC}"
    echo "请先安装 Node.js: https://nodejs.org (推荐 v22+)"
    exit 1
fi

# ---- 检查 npm ----
if command -v npm &>/dev/null; then
    NPM_VER=$(npm -v)
    echo -e "${GREEN}✓${NC} npm: $NPM_VER"
else
    echo -e "${RED}✗ npm 未安装${NC}"
    exit 1
fi

echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${HOME}/.openclaw/workspace"

# ---- 第1步: 安装/更新 OpenClaw ----
echo -e "${CYAN}[1/5] 安装 OpenClaw...${NC}"
npm install -g openclaw 2>&1 | tail -3
echo -e "${GREEN}✓ OpenClaw 安装完成 ($(openclaw --version 2>/dev/null || echo 'ok'))${NC}"

# ---- 第2步: 停止已有服务 ----
echo -e "${CYAN}[2/5] 停止已有服务...${NC}"
openclaw gateway stop 2>/dev/null || true
sleep 1
echo -e "${GREEN}✓ 服务已停止${NC}"

# ---- 第3步: 部署 workspace ----
echo -e "${CYAN}[3/5] 部署 workspace（身份、技能、行为规则）...${NC}"

mkdir -p "${WORKSPACE_DIR}"
mkdir -p "${WORKSPACE_DIR}/memory"

# 复制核心身份文件
cp "${SCRIPT_DIR}/workspace/SOUL.md" "${WORKSPACE_DIR}/SOUL.md"
cp "${SCRIPT_DIR}/workspace/AGENTS.md" "${WORKSPACE_DIR}/AGENTS.md"
cp "${SCRIPT_DIR}/workspace/SEARCH_RULES.md" "${WORKSPACE_DIR}/SEARCH_RULES.md"
cp "${SCRIPT_DIR}/workspace/IDENTITY.md" "${WORKSPACE_DIR}/IDENTITY.md"
cp "${SCRIPT_DIR}/workspace/TOOLS.md" "${WORKSPACE_DIR}/TOOLS.md"
cp "${SCRIPT_DIR}/workspace/HEARTBEAT.md" "${WORKSPACE_DIR}/HEARTBEAT.md"
cp "${SCRIPT_DIR}/workspace/CHECKPOINT.md" "${WORKSPACE_DIR}/CHECKPOINT.md"

# 复制 USER.md 模板（不覆盖已有）
if [ ! -f "${WORKSPACE_DIR}/USER.md" ]; then
    cp "${SCRIPT_DIR}/workspace/USER.md" "${WORKSPACE_DIR}/USER.md"
    echo -e "${YELLOW}⚠ 请编辑 ~/.openclaw/workspace/USER.md 填入你的信息${NC}"
fi

# 复制 MEMORY.md（不覆盖已有）
if [ ! -f "${WORKSPACE_DIR}/MEMORY.md" ]; then
    cp "${SCRIPT_DIR}/workspace/MEMORY.md" "${WORKSPACE_DIR}/MEMORY.md"
fi

# 复制技能
mkdir -p "${WORKSPACE_DIR}/skills"
if [ -d "${SCRIPT_DIR}/skills" ]; then
    INSTALLED=0
    SKIPPED=0
    for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
        skill_name="$(basename "$skill_dir")"
        if [ -d "${WORKSPACE_DIR}/skills/${skill_name}" ]; then
            SKIPPED=$((SKIPPED + 1))
        else
            cp -r "$skill_dir" "${WORKSPACE_DIR}/skills/${skill_name}"
            echo -e "  ${GREEN}✓${NC} 安装技能: ${skill_name}"
            INSTALLED=$((INSTALLED + 1))
        fi
    done
    echo -e "  ${GREEN}✓${NC} 安装 $INSTALLED 个新技能，跳过 $SKIPPED 个已有技能"
fi

echo -e "${GREEN}✓ workspace 部署完成${NC}"

# ---- 第4步: 配置 openclaw.json ----
echo -e "${CYAN}[4/5] 生成配置文件...${NC}"

if [ -f "${SCRIPT_DIR}/.env" ]; then
    source "${SCRIPT_DIR}/.env"
fi

# 询问 API Key
echo ""
echo -e "${YELLOW}需要配置 LLM API Key（用于 AI 对话）${NC}"
echo -e "  支持: DeepSeek / OpenAI / GLM / 本地模型"
echo -e "  留空则跳过，之后可以手动配置。"
echo ""

read -r -p "DeepSeek API Key (推荐): " DEEPSEEK_KEY
read -r -p "备选 API Key (可选): " SECONDARY_KEY

OPENCLAW_CONFIG_DIR="${HOME}/.openclaw"
mkdir -p "${OPENCLAW_CONFIG_DIR}"

# 构建 providers JSON
PROVIDERS="{}"
[ -n "$DEEPSEEK_KEY" ] && PROVIDERS=$(python3 -c "
import json
p = json.loads('$PROVIDERS')
p['deepseek'] = {'baseUrl': 'https://api.deepseek.com', 'apiKey': '$DEEPSEEK_KEY'}
print(json.dumps(p))
" 2>/dev/null) || PROVIDERS='{"deepseek":{"baseUrl":"https://api.deepseek.com","apiKey":"'$DEEPSEEK_KEY'"}}'

[ -n "$SECONDARY_KEY" ] && PROVIDERS=$(python3 -c "
import json
p = json.loads('$PROVIDERS')
p['fallback'] = {'baseUrl': 'https://api.openai.com/v1', 'apiKey': '$SECONDARY_KEY'}
print(json.dumps(p))
" 2>/dev/null) || true

cat > "${OPENCLAWS_CONFIG_DIR}/openclaw.json" << 'CONFIGEOF'
{
  "agents": {
    "defaults": {
      "workspace": "${HOME}/.openclaw/workspace",
      "model": {
        "primary": "${PRIMARY_MODEL:-deepseek/deepseek-chat}",
        "fallbacks": [
          "deepseek/deepseek-chat",
          "fallback/deepseek-chat"
        ]
      },
      "models": {
        "deepseek/deepseek-chat": {
          "alias": "DeepSeek"
        },
        "deepseek/deepseek-reasoner": {
          "alias": "DeepSeek-R1"
        },
        "fallback/deepseek-chat": {
          "alias": "Fallback"
        },
        "fallback/deepseek-reasoner": {
          "alias": "Fallback-R1"
        }
      },
      "params": {
        "maxTokens": 8192
      },
      "memorySearch": {
        "enabled": true
      }
    }
  },
  "nativeSkills": "auto",
  "bundledDiscovery": "compat",
  "skills": {
    "entries": {
      "clawhub": { "enabled": true },
      "peekaboo": { "enabled": true },
      "skill-finder-cn": { "enabled": true }
    }
  }
}
CONFIGEOF

# 写入 providers 和修正路径
python3 << 'PYEOF' 2>/dev/null || true
import json, os, re

config_path = os.path.expanduser("~/.openclaw/openclaw.json")
with open(config_path, 'r') as f:
    content = f.read()

# 替换环境变量占位符
primary = os.environ.get('PRIMARY_MODEL', 'deepseek/deepseek-chat')
content = content.replace('${PRIMARY_MODEL:-deepseek/deepseek-chat}', primary)

config = json.loads(content)

# 写入 providers
providers = {}
if os.environ.get('DEEPSEEK_KEY'):
    providers['deepseek'] = {
        'baseUrl': 'https://api.deepseek.com',
        'apiKey': os.environ['DEEPSEEK_KEY']
    }
if os.environ.get('SECONDARY_KEY'):
    providers['fallback'] = {
        'baseUrl': 'https://api.openai.com/v1',
        'apiKey': os.environ['SECONDARY_KEY']
    }
if providers:
    config['providers'] = providers

config['agents']['defaults']['workspace'] = os.path.expanduser("~/.openclaw/workspace")

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print("配置写入完成")
PYEOF

echo -e "${GREEN}✓ 配置文件生成完成${NC}"

# ---- 第5步: 启动 OpenClaw ----
echo -e "${CYAN}[5/5] 启动 OpenClaw Gateway...${NC}"
openclaw gateway start 2>&1 | tail -3 || {
    echo -e "${RED}启动失败，尝试查看日志...${NC}"
    openclaw gateway status
    exit 1
}

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  🎉 OpenClaw 进化版 v0.2 已安装完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "   ${CYAN}➜${NC} 打开 WebChat:  ${CYAN}http://localhost:3100${NC}"
echo -e "   ${CYAN}➜${NC} 编辑身份:     ${CYAN}~/.openclaw/workspace/USER.md${NC}"
echo -e "   ${CYAN}➜${NC} 查看状态:     ${CYAN}openclaw status${NC}"
echo ""
echo -e "${YELLOW}📌 发票自动化快速开始:${NC}"
echo -e "   在 WebChat 中直接说:"
echo -e "   \"帮我设置发票自动识别\""
echo -e "   \"扫描这张发票图片\""
echo -e "   \"创建发票归档任务\""
echo ""
echo -e "${YELLOW}📌 常用命令:${NC}"
echo -e "   openclaw status         查看运行状态"
echo -e "   openclaw gateway status  Gateway 状态"
echo -e "   openclaw gateway logs   查看日志"
echo ""

echo -e "${GREEN}安装完成！开始使用吧 🚀${NC}"
