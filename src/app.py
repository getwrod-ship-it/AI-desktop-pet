# -*- coding: utf-8 -*-
"""主应用模块"""
import sys
import time
import threading
import re
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from src.utils.config import Config
from src.ui.pet_window import PetWindow
from src.vision.screen_capture import ScreenCapture, ScreenConfig
from src.vision.vision_model import VisionModel, VisionModelConfig
from src.llm.language_model import LanguageModel, LanguageModelConfig
from src.context.manager import ContextManager


class AppSignals(QObject):
    """跨线程信号"""
    show_bubble = pyqtSignal(str, bool)
    update_state = pyqtSignal(str)
    log_message = pyqtSignal(str)


class DesktopPetApp:
    """桌面宠物应用主类"""

    def __init__(self, config_path: str = "config.yaml"):
        # 加载配置
        self.config = Config.from_yaml(config_path)

        # 初始化 Qt 应用
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(True)

        # 初始化信号
        self.signals = AppSignals()

        # 初始化模块
        self._init_modules()

        # 连接信号
        self._connect_signals()

        # 后台任务控制
        self._running = False
        self._capture_thread = None
        self._analyze_thread = None
        self._pending_screenshot = None
        self._pending_lock = threading.Lock()

        # 主动交互计时
        self._last_interaction_time = time.time()
        self._proactive_interval = 30

        # 压缩定时器
        self._compress_timer = None
        # 情绪衰减定时器
        self._mood_decay_timer = None

    def _init_modules(self):
        """初始化各个模块"""
        # 宠物 UI
        self.pet_window = PetWindow(
            pet_name=self.config.pet.name,
            bubble_duration=self.config.pet.bubble_duration
        )

        # 屏幕捕获
        screen_config = self.config.screen
        self.screen_capture = ScreenCapture(ScreenConfig(
            monitor=screen_config.monitor,
            capture_interval=screen_config.capture_interval,
            change_threshold=screen_config.change_threshold
        ))

        # 视觉模型
        vision_config = self.config.models.vision
        self.vision_model = VisionModel(VisionModelConfig(
            name=vision_config.name,
            base_url=self.config.ollama.base_url,
            num_predict=vision_config.options.num_predict,
            temperature=vision_config.options.temperature
        ))

        # 语言模型
        language_config = self.config.models.language
        self.language_model = LanguageModel(LanguageModelConfig(
            name=language_config.name,
            base_url=self.config.ollama.base_url,
            num_predict=language_config.options.num_predict,
            temperature=language_config.options.temperature
        ))

        # 上下文管理器（使用新配置）
        context_config = self.config.context

        # 构建记忆系统配置
        memory_config = {
            "recent_window_minutes": context_config.memory.recent_window_minutes,
            "compress_interval_minutes": context_config.memory.compress_interval_minutes,
            "keep_recent_dialogs": context_config.memory.keep_recent_dialogs,
            "keep_recent_screens": context_config.memory.keep_recent_screens,
            "max_recent_dialogs": context_config.memory.max_recent_dialogs,
            "max_recent_screens": context_config.memory.max_recent_screens,
            "max_history_slots": context_config.memory.max_history_slots,
            "compress_trigger_count": context_config.memory.compress_trigger_count
        }

        user_profile_config = {
            "work_pattern_min_samples": context_config.user_profile.work_pattern_min_samples,
            "app_importance_threshold": context_config.user_profile.app_importance_threshold,
            "dialog_style_update_rate": context_config.user_profile.dialog_style_update_rate,
            "topic_interest_decay": context_config.user_profile.topic_interest_decay
        }

        pet_profile_config = {
            "preset": context_config.pet_profile.preset,
            "familiarity_increment": context_config.pet_profile.familiarity_increment,
            "familiarity_max": context_config.pet_profile.familiarity_max,
            "topic_expertise_increment": context_config.pet_profile.topic_expertise_increment,
            "topic_expertise_max": context_config.pet_profile.topic_expertise_max,
            "mood_decay_rate": context_config.pet_profile.mood_decay_rate,
            "mood_min_level": context_config.pet_profile.mood_min_level
        }

        self.context_manager = ContextManager(
            db_path=context_config.db_path,
            max_screen_history=context_config.max_screen_history,
            max_dialog_history=context_config.max_dialog_history,
            memory_config=memory_config,
            user_profile_config=user_profile_config,
            pet_profile_config=pet_profile_config,
            llm_compress_func=self._llm_compress
        )

        # 设置压缩完成回调
        self.context_manager.set_compress_callback(self._on_compress_complete)

        # 设置画像更新回调
        self.context_manager.set_profile_update_callback(self._log_profile_update)

        # 打印桌宠画像信息
        pet_profile = self.context_manager.pet_profile
        self._log(f"桌宠画像: {pet_profile.name}, 熟悉度: {pet_profile.familiarity_level:.2f}")

    def _llm_compress(self, prompt_type: str, content: str) -> str:
        """使用LLM进行压缩"""
        if prompt_type == "dialog":
            prompt = f"""请将以下对话内容压缩成简短摘要，保留关键信息：
{content}

要求：
1. 用2-3句话概括对话内容
2. 提取讨论的主要话题
3. 标注情绪变化（如果有）

直接输出摘要："""
        else:
            prompt = f"""请将以下屏幕活动压缩成简短摘要，保留关键信息：
{content}

要求：
1. 用1-2句话概括用户活动
2. 列出主要使用的应用程序
3. 识别活动类型（工作/学习/娱乐）

直接输出摘要："""

        try:
            result = self.language_model.simple_chat(prompt)
            return result if result else ""
        except Exception as e:
            self._log(f"LLM压缩失败: {e}")
            return ""

    def _connect_signals(self):
        """连接信号到槽函数"""
        self.signals.show_bubble.connect(self.pet_window.show_bubble)
        self.signals.update_state.connect(self.pet_window.set_pet_state)
        self.signals.log_message.connect(self._log)

        # 连接对话请求信号
        self.pet_window.dialog_requested.connect(self._on_dialog_requested)

        # 连接退出和清除历史信号
        self.pet_window.quit_requested.connect(self._on_quit)
        self.pet_window.clear_history_requested.connect(self._on_clear_history)

        # 连接查看历史信号
        self.pet_window.view_history_requested.connect(self._on_view_history)

        # 启动主动交互定时器
        self._proactive_timer = QTimer()
        self._proactive_timer.timeout.connect(self._check_proactive_interaction)
        self._proactive_timer.start(30000)  # 每30秒检查一次

        # 启动压缩定时器（每10分钟）
        compress_interval = self.config.context.memory.compress_interval_minutes * 60 * 1000
        self._compress_timer = QTimer()
        self._compress_timer.timeout.connect(self._on_compress_timer)
        self._compress_timer.start(compress_interval)

        # 启动情绪衰减定时器（每小时）
        self._mood_decay_timer = QTimer()
        self._mood_decay_timer.timeout.connect(self._on_mood_decay_timer)
        self._mood_decay_timer.start(3600000)  # 每小时

    def _on_compress_timer(self):
        """压缩定时器回调"""
        try:
            self._log("定时触发记忆压缩...")
            self.context_manager.manual_compress()
        except Exception as e:
            self._log(f"压缩错误: {e}")

    def _on_mood_decay_timer(self):
        """情绪衰减定时器回调"""
        try:
            # 情绪衰减在PetProfileUpdater中自动处理
            pet_profile = self.context_manager.pet_profile
            self._log(f"情绪衰减检查: 能量={pet_profile.energy_level:.2f}")
        except Exception as e:
            self._log(f"情绪衰减错误: {e}")

    def _on_compress_complete(self, summary):
        """压缩完成回调"""
        self._log("=" * 50)
        self._log("【记忆压缩完成】")
        self._log(f"时间段: {summary.time_slot}")
        self._log(f"时间范围: {summary.start_time} ~ {summary.end_time}")
        self._log("-" * 50)
        if summary.dialog_summary:
            self._log(f"对话摘要: {summary.dialog_summary}")
        if summary.screen_summary:
            self._log(f"屏幕摘要: {summary.screen_summary}")
        if summary.topics:
            self._log(f"主要话题: {', '.join(summary.topics)}")
        self._log("=" * 50)

    def _log_profile_update(self, profile_type: str):
        """打印画像更新日志"""
        self._log("=" * 50)
        self._log(f"【{profile_type}画像更新】")

        if profile_type == "用户":
            profile = self.context_manager.user_profile
            self._log(f"  交互天数: {profile.total_interaction_days}")
            self._log(f"  最后活跃: {profile.last_active}")
            self._log(f"  工作状态: {profile.productivity_style}")
            self._log(f"  对话风格: {profile.communication_style}")
            if profile.primary_apps:
                top_apps = sorted(profile.primary_apps.items(), key=lambda x: x[1], reverse=True)[:3]
                self._log(f"  常用应用: {', '.join([a[0] for a in top_apps])}")
            if profile.topic_interests:
                top_topics = sorted(profile.topic_interests.items(), key=lambda x: x[1], reverse=True)[:3]
                self._log(f"  兴趣话题: {', '.join([t[0] for t in top_topics])}")
            self._log(f"  信任度: {profile.trust_level:.2f}")

        elif profile_type == "桌宠":
            profile = self.context_manager.pet_profile
            self._log(f"  熟悉度: {profile.familiarity_level:.2f}")
            self._log(f"  当前情绪: {profile.emotion}")
            self._log(f"  能量值: {profile.energy_level:.2f}")
            self._log(f"  注意力: {profile.attention_level:.2f}")
            if profile.learned_tones:
                top_tones = sorted(profile.learned_tones.items(), key=lambda x: x[1], reverse=True)[:2]
                self._log(f"  学习语气: {', '.join([t[0] for t in top_tones])}")
            if profile.topic_expertise:
                top_skills = sorted(profile.topic_expertise.items(), key=lambda x: x[1], reverse=True)[:3]
                self._log(f"  擅长话题: {', '.join([s[0] for s in top_skills])}")
            self._log(f"  学习回复数: {len(profile.learned_responses)}")

        self._log("=" * 50)

    def _show_user_bubble(self, text: str):
        """显示用户气泡"""
        self.pet_window.show_bubble(text, is_user=True)

    def _on_view_history(self):
        """查看对话历史"""
        from src.ui.pet_window import HistoryDialog
        history = self.context_manager.get_dialog_history()

        # 先销毁旧的历史窗口（如果存在）
        if hasattr(self, '_history_dialog') and self._history_dialog is not None:
            self._history_dialog.close()
            self._history_dialog.deleteLater()
            self._history_dialog = None

        # 创建新的历史窗口
        self._history_dialog = HistoryDialog(history)
        self._history_dialog.show()

    def _log(self, message: str):
        """输出日志"""
        print(f"[DesktopPet] {message}")

    def run(self):
        """运行应用"""
        self._log("启动桌面宠物...")

        # 检查 Ollama 连接
        if not self.vision_model.check_connection():
            self._log("警告: 无法连接到 Ollama 服务，请确保 Ollama 正在运行")
        else:
            self._log("Ollama 服务连接成功")

        # 显示宠物窗口
        initial_pos = self.config.pet.position
        self.pet_window.move(initial_pos[0], initial_pos[1])
        self.pet_window.show()

        # 确保初始状态为 idle
        self.pet_window.set_pet_state("idle")

        # 使用桌宠画像的问候语
        from src.context.pet_profile_updater import PetProfileUpdater
        updater = PetProfileUpdater()
        greeting = updater.get_greeting(self.context_manager.pet_profile)
        self.pet_window.show_bubble(f"{self.config.pet.name}：{greeting}", is_user=False)

        # 启动后台视觉理解任务
        self._start_vision_loop()

        # 进入事件循环
        result = self.app.exec()

        # 清理
        self._cleanup()

        return result

    def _start_vision_loop(self):
        """启动后台视觉理解任务"""
        self._running = True

        # 截图线程 - 每秒截图一次
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        # 分析线程 - 处理待分析的截图
        self._analyze_thread = threading.Thread(target=self._analyze_loop, daemon=True)
        self._analyze_thread.start()

    def _capture_loop(self):
        """截图循环 - 每秒截图一次，检测变化"""
        self._log("开始屏幕捕获循环...")

        while self._running:
            try:
                # 截图并检测变化
                screenshot, has_changed = self.screen_capture.capture_with_change_detection()

                if screenshot is not None and has_changed:
                    with self._pending_lock:
                        # 覆盖旧的待分析截图，只保留最新的
                        self._pending_screenshot = screenshot
                    self._log("检测到屏幕变化，加入待分析队列...")

                # 每秒截图一次
                time.sleep(1)

            except Exception as e:
                self._log(f"截图循环错误: {e}")
                time.sleep(1)

    def _analyze_loop(self):
        """分析循环 - 处理待分析的截图"""
        self._log("开始屏幕分析循环...")

        while self._running:
            try:
                screenshot = None

                # 获取待分析的截图
                with self._pending_lock:
                    if self._pending_screenshot is not None:
                        screenshot = self._pending_screenshot
                        self._pending_screenshot = None

                if screenshot is not None:
                    # 检查桌宠当前状态是否为空闲且输入框未打开
                    current_state = self.pet_window._current_state
                    is_input_open = getattr(self.pet_window, '_input_dialog_open', False)
                    is_idle = (current_state == "idle") and not is_input_open

                    # 有待分析的截图，开始分析
                    self._log("开始分析屏幕...")

                    start_time = time.time()
                    description = self.vision_model.understand_screen(screenshot)
                    elapsed = time.time() - start_time

                    if description:
                        self._log(f"屏幕理解完成 ({elapsed:.1f}s): {description}")
                        # 保存到上下文管理器（使用新方法，支持扩展字段）
                        app_name = self._extract_app_name(description)
                        activity_type = self._guess_activity_type(description)
                        self.context_manager.add_screen_event(
                            description=description,
                            app_name=app_name,
                            activity_type=activity_type
                        )

                        # 如果桌宠处于空闲状态且输入框未打开，触发主动交互
                        if is_idle:
                            self._log("桌宠空闲中，触发主动交互...")
                            # 重置交互时间，确保不会被定时器重复触发
                            self._last_interaction_time = time.time()
                            # 在后台线程处理主动交互
                            threading.Thread(target=self._process_proactive, daemon=True).start()
                    else:
                        self._log(f"屏幕理解失败 ({elapsed:.1f}s)")

                else:
                    # 没有待分析的截图，短暂休眠
                    time.sleep(0.1)

            except Exception as e:
                self._log(f"分析循环错误: {e}")
                time.sleep(0.5)

    def _extract_app_name(self, description: str) -> str:
        """从屏幕描述中提取应用名称"""
        # 常见应用关键词
        app_keywords = {
            "vscode": "VSCode",
            "visual studio code": "VSCode",
            "pycharm": "PyCharm",
            "chrome": "Chrome",
            "firefox": "Firefox",
            "edge": "Edge",
            "浏览器": "Browser",
            "terminal": "Terminal",
            "终端": "Terminal",
            "cmd": "CMD",
            "powershell": "PowerShell",
            "word": "Word",
            "excel": "Excel",
            "powerpoint": "PowerPoint",
            "ppt": "PowerPoint",
            "notion": "Notion",
            "discord": "Discord",
            "slack": "Slack",
            "微信": "WeChat",
            "qq": "QQ",
            "音乐": "Music Player",
            "视频": "Video Player"
        }

        desc_lower = description.lower()
        for keyword, app_name in app_keywords.items():
            if keyword in desc_lower:
                return app_name
        return "Unknown"

    def _guess_activity_type(self, description: str) -> str:
        """从屏幕描述中猜测活动类型"""
        desc_lower = description.lower()

        # 编程相关
        if any(kw in desc_lower for kw in ["代码", "code", "编程", "debug", "调试", "git"]):
            return "coding"

        # 工作相关
        if any(kw in desc_lower for kw in ["文档", "报告", "邮件", "excel", "word", "ppt"]):
            return "work"

        # 学习相关
        if any(kw in desc_lower for kw in ["教程", "学习", "课程", "文档"]):
            return "study"

        # 娱乐相关
        if any(kw in desc_lower for kw in ["游戏", "视频", "音乐", "电影", "娱乐"]):
            return "entertainment"

        # 沟通相关
        if any(kw in desc_lower for kw in ["聊天", "消息", "微信", "qq", "discord"]):
            return "communication"

        # 浏览相关
        if any(kw in desc_lower for kw in ["浏览器", "网页", "搜索", "浏览"]):
            return "browsing"

        return "other"

    def _on_dialog_requested(self, user_input: str):
        """处理用户对话请求"""
        self._log(f"用户输入: {user_input}")

        # 更新最后交互时间
        self._last_interaction_time = time.time()

        # 用户已发送消息，切换到思考状态
        self.signals.update_state.emit("think")

        # 显示用户气泡
        self.pet_window.show_bubble(user_input, is_user=True)

        # 在后台线程处理对话
        threading.Thread(
            target=self._process_dialog,
            args=(user_input,),
            daemon=True
        ).start()

    def _process_dialog(self, user_input: str):
        """处理对话（后台线程）"""
        try:
            self.signals.update_state.emit("think")

            # 保存用户输入（不带情绪）
            self.context_manager.add_dialog("user", user_input)

            # 使用新的上下文构建方法
            system_prompt = self.context_manager.build_full_prompt(user_input)

            # 获取对话历史
            dialog_history = self.context_manager.get_dialog_history()

            # 调用语言模型
            start_time = time.time()
            response = self.language_model.chat(dialog_history, system_prompt)
            elapsed = time.time() - start_time

            if response:
                # 解析情绪标签和内容
                emotion, content = self._parse_emotion(response)
                self._log(f"对话回复 ({elapsed:.1f}s): {content} [emotion: {emotion}]")

                # 保存助手回复（带情绪标签）
                self.context_manager.add_dialog("assistant", content, emotion=emotion)

                # 更新桌宠情绪
                self.context_manager.update_pet_emotion(emotion)

                # 更新桌宠画像
                self.context_manager.update_pet_after_dialog()

                # 显示回复（宠物气泡）
                self.signals.show_bubble.emit(content, False)

                # 切换到对应情绪的状态
                self.signals.update_state.emit(emotion)
            else:
                self._log(f"对话失败 ({elapsed:.1f}s)")
                self.signals.show_bubble.emit("抱歉，我暂时无法回应...", False)
                self.signals.update_state.emit("idle")

        except Exception as e:
            self._log(f"对话处理错误: {e}")
            self.signals.update_state.emit("idle")

    def _build_system_prompt(self) -> str:
        """构建系统提示词（兼容旧API）"""
        # 使用新的上下文构建器
        return self.context_manager.build_full_prompt("")

    def _parse_emotion(self, text: str) -> tuple:
        """
        解析情绪标签和内容

        Args:
            text: 完整的回复文本

        Returns:
            (emotion, content): 情绪标签和纯内容
        """
        # 尝试匹配 [emotion: xxx] 格式
        pattern = r'\[emotion:\s*(\w+)\]'
        match = re.search(pattern, text)

        if match:
            emotion = match.group(1).lower()
            content = text[match.end():].strip()
            return emotion, content
        else:
            # 没有情绪标签，默认为 idle
            return "idle", text

    def _check_proactive_interaction(self):
        """检查是否需要主动交互"""
        elapsed = time.time() - self._last_interaction_time

        if elapsed >= self._proactive_interval:
            # 超过设定时间无交互，主动说话
            self._proactive_speak()

    def _proactive_speak(self):
        """主动发起对话"""
        self._log("主动交互...")

        # 在后台线程处理
        threading.Thread(target=self._process_proactive, daemon=True).start()

    def _process_proactive(self):
        """处理主动交互（后台线程）"""
        try:
            # 先切换到思考状态
            self.signals.update_state.emit("think")

            # 使用新的主动交互提示词构建
            prompt = self.context_manager.build_proactive_prompt()

            # 调用语言模型
            response = self.language_model.simple_chat(prompt)

            if response:
                # 解析情绪标签和内容
                emotion, content = self._parse_emotion(response)
                self._log(f"主动说话: {content} [emotion: {emotion}]")

                # 保存助手回复（带情绪标签）
                self.context_manager.add_dialog("assistant", content, emotion=emotion)

                # 更新桌宠情绪
                self.context_manager.update_pet_emotion(emotion)

                # 显示回复（宠物气泡）
                self.signals.show_bubble.emit(content, False)

                # 切换到对应情绪的状态
                self.signals.update_state.emit(emotion)
            else:
                self.signals.update_state.emit("idle")

            # 更新最后交互时间
            self._last_interaction_time = time.time()

        except Exception as e:
            self._log(f"主动交互错误: {e}")
            self.signals.update_state.emit("idle")

    def _on_quit(self):
        """处理退出请求"""
        self._log("用户请求退出...")

        # 保存画像
        try:
            self.context_manager.db_manager.save_user_profile(self.context_manager.user_profile)
            self.context_manager.db_manager.save_pet_profile(self.context_manager.pet_profile)
            self._log("画像已保存")
        except Exception as e:
            self._log(f"保存画像失败: {e}")

        QApplication.quit()

    def _on_clear_history(self):
        """处理清除历史请求"""
        self._log("清除历史记录...")
        self.context_manager.clear_history()

        # 关闭历史窗口（如果存在）
        if hasattr(self, '_history_dialog') and self._history_dialog is not None:
            self._history_dialog.close()
            self._history_dialog.deleteLater()
            self._history_dialog = None

    def _cleanup(self):
        """清理资源"""
        self._running = False

        # 停止定时器
        if self._compress_timer:
            self._compress_timer.stop()
        if self._mood_decay_timer:
            self._mood_decay_timer.stop()

        if self.screen_capture:
            self.screen_capture.close()
        self._log("应用已退出")


def main():
    """入口函数"""
    app = DesktopPetApp("config.yaml")
    sys.exit(app.run())
