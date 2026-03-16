# AI 桌面宠物

一个具备屏幕理解与语言对话能力的智能桌面宠物应用。

## 功能特性

- **屏幕理解** - 实时监控用户屏幕，分析当前活动内容
- **自然语言对话** - 基于 Ollama 本地大语言模型进行智能对话
- **记忆系统** - 持久化存储对话历史，支持智能压缩
- **用户画像** - 自动学习用户工作习惯、对话偏好
- **桌宠画像** - 虚拟宠物具备独特性格、情绪状态和成长能力
- **主动交互** - 宠物会根据用户活动主动发起对话
- **动画系统** - 支持多种情绪状态的动画展示

## 技术栈

| 组件 | 技术 |
|------|------|
| 开发语言 | Python 3.x |
| UI 框架 | PyQt6 |
| 屏幕捕获 | mss |
| LLM 服务 | Ollama |
| 数据存储 | SQLite |

## 系统要求

- **操作系统**: Windows 10/11
- **显卡**: NVIDIA GPU（推荐 RTX 3060 12GB 或同等显存）
- **内存**: 16GB+
- **Python**: 3.10+

## 快速开始

### 1. 安装 Ollama

从 [ollama.com](https://ollama.com) 下载并安装 Ollama。

### 2. 下载模型

```bash
# 下载视觉模型
ollama pull minicpm-v:latest

# 下载语言模型
ollama pull qwen2.5:3b
```

### 3. 安装 Python 依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 运行程序

```bash
python main.py
```

## 项目结构

```
desktop-pet/
├── main.py              # 程序入口
├── config.yaml          # 配置文件
├── requirements.txt     # Python 依赖
├── src/
│   ├── app.py           # 主应用
│   ├── ui/              # UI 模块
│   ├── vision/          # 视觉模块
│   ├── llm/             # 语言模型模块
│   ├── context/         # 上下文管理
│   └── utils/           # 工具模块
├── assets/pet/          # 宠物动画素材
└── data/                # 数据存储
```

## 配置说明

编辑 `config.yaml` 文件可以自定义：

- Ollama 服务地址
- 模型参数（temperature、num_predict）
- 屏幕捕获间隔和变化检测阈值
- 记忆系统参数
- 宠物预设和初始位置

## 交互操作

| 操作 | 说明 |
|------|------|
| 拖拽 | 按住左键拖动宠物 |
| 单击 | 点击宠物打开对话输入框 |
| 右键 | 打开菜单（历史记录、调节大小、退出等） |

## 宠物预设

项目内置三种宠物预设：

- **好奇企鹅** (`penguin_curious`) - 活泼、好奇、乐于助人
- **慵懒猫咪** (`cat_lazy`) - 淡定、慵懒、偶尔傲娇
- **机器人助手** (`robot_assistant`) - 专业、高效、逻辑清晰

在 `config.yaml` 中修改 `context.pet_profile.preset` 即可切换。

## 常见问题

**Q: 宠物不响应屏幕变化？**

A: 检查 Ollama 服务是否正常运行，确认视觉模型已安装。

**Q: 对话回复很慢？**

A: 可尝试更换更小的语言模型，或降低 `num_predict` 参数。

**Q: 记忆没有保存？**

A: 检查 `data/context.db` 文件权限，确保程序有写入权限。

## 隐私说明

- 所有数据本地处理，不上传云端
- 对话历史存储在本地 SQLite 数据库
- 可配置忽略特定应用/窗口

## 许可证

MIT License
