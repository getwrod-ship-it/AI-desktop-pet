#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 桌面宠物 - 入口文件

一个具备屏幕理解与语言对话能力的桌面宠物
"""

import sys
import os
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

# 切换工作目录到项目根目录
os.chdir(project_root)

from src.app import main

if __name__ == "__main__":
    main()
