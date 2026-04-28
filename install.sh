#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# OpenClaw 进化版 — 一键安装脚本
# 适用: macOS / Linux
# 用途: 发票自动化及其他办公自动化任务
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🦞 OpenClaw 进化版 — 一键安装${NC}"
echo -e "${CYAN}  发票自动化专用版${NC}"
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
    echo "安装完成后重新运行此脚本。"
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

# ---- 第1步: 安装 OpenClaw ----
echo -e "${CYAN}[1/5] 安装 OpenClaw...${NC}"
npm install -g openclaw 2>&1 | tail -3
echo -e "${GREEN}✓ OpenClaw 安装完成${NC}"

# ---- 第2步: 停止已运行的 gateway ----
echo -e "${CYAN}[2/5] 停止已有服务...${NC}"
openclaw gateway stop 2>/dev/null || true
sleep 1
echo -e "${GREEN}✓ 服务已停止${NC}"

# ---- 第3步: 复制 workspace ----
echo -e "${CYAN}[3/5] 部署 workspace（身份、技能、行为规则）...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${HOME}/.openclaw/workspace"

# 创建目录
mkdir -p "${WORKSPACE_DIR}"
mkdir -p "${WORKSPACE_DIR}/memory"
mkdir -p "${WORKSPACE_DIR}/skills"

# 复制核心身份文件
cp "${SCRIPT_DIR}/workspace/SOUL.md" "${WORKSPACE_DIR}/SOUL.md"
cp "${SCRIPT_DIR}/workspace/AGENTS.md" "${WORKSPACE_DIR}/AGENTS.md"
cp "${SCRIPT_DIR}/workspace/IDENTITY.md" "${WORKSPACE_DIR}/IDENTITY.md"
cp "${SCRIPT_DIR}/workspace/TOOLS.md" "${WORKSPACE_DIR}/TOOLS.md"
cp "${SCRIPT_DIR}/workspace/HEARTBEAT.md" "${WORKSPACE_DIR}/HEARTBEAT.md"

# 复制 USER.md 模板（用户自行编辑）
if [ ! -f "${WORKSPACE_DIR}/USER.md" ]; then
    cp "${SCRIPT_DIR}/workspace/USER.md" "${WORKSPACE_DIR}/USER.md"
    echo -e "${YELLOW}⚠ 请编辑 ~/.openclaw/workspace/USER.md 填入你的信息${NC}"
fi

# 复制 MEMORY.md（不含交易系统相关内容）
cp "${SCRIPT_DIR}/workspace/MEMORY.md" "${WORKSPACE_DIR}/MEMORY.md"

# 复制技能（不含交易系统）
if [ -d "${SCRIPT_DIR}/skills" ]; then
    for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
        skill_name="$(basename "$skill_dir")"
        if [ -d "${WORKSPACE_DIR}/skills/${skill_name}" ]; then
            echo -e "  ${YELLOW}↻${NC} 技能已存在，跳过: ${skill_name}"
        else
            cp -r "$skill_dir" "${WORKSPACE_DIR}/skills/${skill_name}"
            echo -e "  ${GREEN}✓${NC} 安装技能: ${skill_name}"
        fi
    done
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

read -r -p "DeepSeek API Key (可选): " DEEPSEEK_KEY
read -r -p "UIUI API Key (可选): " UIUI_KEY

# 生成 openclaw.json
OPENCLAW_CONFIG_DIR="${HOME}/.openclaw"
mkdir -p "${OPENCLAW_CONFIG_DIR}"

# 构建 providers
PROVIDERS_JSON="{}"
if [ -n "$DEEPSEEK_KEY" ]; then
    PROVIDERS_JSON=$(echo "$PROVIDERS_JSON" | python3 -c "
import json, sys
p = json.load(sys.stdin)
p['deepseek'] = {
    'baseUrl': 'https://api.deepseek.com',
    'apiKey': '$DEEPSEEK_KEY'
}
print(json.dumps(p, indent=2))
" 2>/dev/null || echo '{"deepseek":{"baseUrl":"https://api.deepseek.com","apiKey":"'$DEEPSEEK_KEY'"}}')
fi
if [ -n "$UIUI_KEY" ]; then
    PROVIDERS_JSON=$(echo "$PROVIDERS_JSON" | python3 -c "
import json, sys
p = json.load(sys.stdin)
p['uiuiapi'] = {
    'baseUrl': 'https://api.uiui.ai/v1',
    'apiKey': '$UIUI_KEY'
}
print(json.dumps(p, indent=2))
" 2>/dev/null || echo '{"uiuiapi":{"baseUrl":"https://api.uiui.ai/v1","apiKey":"'$UIUI_KEY'"}}')
fi

cat > "${OPENCLAW_CONFIG_DIR}/openclaw.json" << 'CONFIGEOF'
{
  "agents": {
    "defaults": {
      "workspace": "${HOME}/.openclaw/workspace",
      "model": {
        "primary": "${PRIMARY_MODEL:-deepseek/deepseek-chat}",
        "fallbacks": [
          "deepseek/deepseek-chat",
          "uiuiapi/deepseek-chat"
        ]
      },
      "models": {
        "deepseek/deepseek-chat": {
          "alias": "DeepSeek"
        },
        "deepseek/deepseek-reasoner": {
          "alias": "DeepSeek-R1"
        },
        "uiuiapi/deepseek-chat": {
          "alias": "Chat-UIUI"
        },
        "uiuiapi/deepseek-reasoner": {
          "alias": "Reasoner-UIUI"
        }
      },
      "params": {
        "maxTokens": 8192
      },
      "memorySearch": {
        "enabled": true
      }
    }
  }
}
CONFIGEOF

# 替换占位符（用 python3 处理 JSON 更安全）
python3 << 'PYEOF' 2>/dev/null || true
import json, os, re

config_path = os.path.expanduser("~/.openclaw/openclaw.json")
with open(config_path, 'r') as f:
    content = f.read()

# 替换环境变量占位符
primary = os.environ.get('PRIMARY_MODEL', 'deepseek/deepseek-chat')
content = content.replace('${PRIMARY_MODEL:-deepseek/deepseek-chat}', primary)

# 解析并重写
config = json.loads(content)

# 写入 providers
providers = {}
if os.environ.get('DEEPSEEK_KEY'):
    providers['deepseek'] = {
        'baseUrl': 'https://api.deepseek.com',
        'apiKey': os.environ['DEEPSEEK_KEY']
    }
if os.environ.get('UIUI_KEY'):
    providers['uiuiapi'] = {
        'baseUrl': 'https://api.uiui.ai/v1',
        'apiKey': os.environ['UIUI_KEY']
    }
if providers:
    config['providers'] = providers

# 固定 workspace 路径
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
echo -e "${GREEN}  🎉 OpenClaw 进化版已安装完成！${NC}"
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
echo -e "   openclaw configure      重新配置"
echo ""

# ---- 发票自动化向导 ----
echo -e "${CYAN}是否需要安装发票自动化相关工具？${NC}"
echo -e "  1) PDF 处理 (pdf2image, OCR)"
echo -e "  2) 浏览器自动化 (网页端税控系统)"
echo -e "  3) 邮件发票抓取"
echo -e "  4) 全部安装"
echo -e "  0) 跳过"
echo ""
read -r -p "选择 [0-4]: " SETUP_CHOICE

case "$SETUP_CHOICE" in
    1|4)
        echo -e "${GREEN}安装 PDF/OCR 工具...${NC}"
        pip3 install pdf2image pytesseract pillow 2>/dev/null || true
        if command -v brew &>/dev/null; then
            brew install tesseract tesseract-lang 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ PDF/OCR 工具就绪${NC}"
        ;;&
    2|4)
        echo -e "${GREEN}安装浏览器自动化...${NC}"
        npm install -g @anthropic-ai/claude-code 2>/dev/null || true
        openclaw config skill install agent-browser 2>/dev/null || true
        echo -e "${GREEN}✓ 浏览器自动化就绪${NC}"
        ;;&
    3|4)
        echo -e "${GREEN}安装邮件抓取...${NC}"
        pip3 install imaplib2 2>/dev/null || true
        echo -e "${GREEN}✓ 邮件抓取就绪${NC}"
        echo -e "${YELLOW}  需要配置邮箱账号，安装完成后可在 WebChat 中配置${NC}"
        ;;&
esac

echo ""
echo -e "${GREEN}安装完成！开始使用吧 🚀${NC}"
