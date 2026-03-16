"""配置加载模块"""
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"


@dataclass
class ModelOptions:
    num_predict: int = 200
    temperature: float = 0.3


@dataclass
class VisionModelConfig:
    name: str = "minicpm-v:latest"
    options: ModelOptions = field(default_factory=ModelOptions)


@dataclass
class LanguageModelConfig:
    name: str = "qwen2.5:3b"
    options: ModelOptions = field(default_factory=lambda: ModelOptions(num_predict=100, temperature=0.7))


@dataclass
class ModelsConfig:
    vision: VisionModelConfig = field(default_factory=VisionModelConfig)
    language: LanguageModelConfig = field(default_factory=LanguageModelConfig)


@dataclass
class ScreenConfig:
    monitor: int = 1
    capture_interval: float = 5.0
    change_threshold: float = 0.05


# ============ 新增记忆系统配置 ============

@dataclass
class MemoryConfig:
    """记忆系统配置"""
    # 时间窗口
    recent_window_minutes: int = 10        # 近期上下文时间窗口（分钟）
    compress_interval_minutes: int = 10    # 压缩间隔（分钟）

    # 保留策略
    keep_recent_dialogs: int = 5           # 压缩时保留的完整对话数（摘要中）
    keep_recent_screens: int = 5           # 压缩时保留的完整屏幕事件数（摘要中）
    max_recent_dialogs: int = 100          # 近期上下文最大对话数
    max_recent_screens: int = 100          # 近期上下文最大屏幕事件数

    # 历史保留
    keep_history_days: int = 30            # 压缩历史保留天数
    max_history_slots: int = 100           # 最大历史时间段数

    # 压缩触发
    compress_trigger_count: int = 50       # 触发压缩的数据数量阈值


@dataclass
class UserProfileConfig:
    """用户画像配置"""
    # 工作模式学习
    work_pattern_min_samples: int = 5      # 学习工作模式的最小样本数
    app_importance_threshold: int = 10     # 应用重要性阈值

    # 对话偏好学习
    dialog_style_update_rate: float = 0.1  # 对话风格更新速率
    topic_interest_decay: float = 0.05     # 话题兴趣衰减率


@dataclass
class PetProfileConfig:
    """桌宠画像配置"""
    # 预设选择
    preset: str = "penguin_curious"        # 预设名称

    # 关系学习
    familiarity_increment: float = 0.01    # 每次交互增加的熟悉度
    familiarity_max: float = 1.0           # 最大熟悉度

    # 技能学习
    topic_expertise_increment: float = 0.05  # 话题熟练度增量
    topic_expertise_max: float = 1.0       # 最大熟练度

    # 情绪衰减
    mood_decay_rate: float = 0.1           # 每小时情绪衰减率
    mood_min_level: float = 0.2            # 最小情绪值


@dataclass
class ContextConfig:
    """上下文配置（兼容旧配置）"""
    max_screen_history: int = 50
    max_dialog_history: int = 20
    db_path: str = "./data/context.db"

    # 新增记忆系统配置
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    user_profile: UserProfileConfig = field(default_factory=UserProfileConfig)
    pet_profile: PetProfileConfig = field(default_factory=PetProfileConfig)


@dataclass
class PetConfig:
    name: str = "小爪"
    position: list = field(default_factory=lambda: [100, 100])
    bubble_duration: int = 5000


@dataclass
class Config:
    """应用配置"""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    screen: ScreenConfig = field(default_factory=ScreenConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    pet: PetConfig = field(default_factory=PetConfig)

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "Config":
        """从 YAML 文件加载配置"""
        config_path = Path(path)
        if not config_path.exists():
            print(f"配置文件 {path} 不存在，使用默认配置")
            return cls()

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls._parse_config(data)

    @classmethod
    def _parse_config(cls, data: dict) -> "Config":
        """解析配置数据"""
        config = cls()

        if "ollama" in data:
            config.ollama = OllamaConfig(**data["ollama"])

        if "models" in data:
            models_data = data["models"]
            if "vision" in models_data:
                vision_data = models_data["vision"]
                options = ModelOptions(**vision_data.get("options", {}))
                config.models.vision = VisionModelConfig(
                    name=vision_data.get("name", "minicpm-v:latest"),
                    options=options
                )
            if "language" in models_data:
                lang_data = models_data["language"]
                options = ModelOptions(**lang_data.get("options", {}))
                config.models.language = LanguageModelConfig(
                    name=lang_data.get("name", "qwen2.5:3b"),
                    options=options
                )

        if "screen" in data:
            config.screen = ScreenConfig(**data["screen"])

        if "context" in data:
            context_data = data["context"]

            # 解析基础上下文配置
            config.context.max_screen_history = context_data.get("max_screen_history", 50)
            config.context.max_dialog_history = context_data.get("max_dialog_history", 20)
            config.context.db_path = context_data.get("db_path", "./data/context.db")

            # 解析记忆系统配置
            if "memory" in context_data:
                memory_data = context_data["memory"]
                config.context.memory = MemoryConfig(
                    recent_window_minutes=memory_data.get("recent_window_minutes", 10),
                    compress_interval_minutes=memory_data.get("compress_interval_minutes", 10),
                    keep_recent_dialogs=memory_data.get("keep_recent_dialogs", 5),
                    keep_recent_screens=memory_data.get("keep_recent_screens", 5),
                    max_recent_dialogs=memory_data.get("max_recent_dialogs", 100),
                    max_recent_screens=memory_data.get("max_recent_screens", 100),
                    keep_history_days=memory_data.get("keep_history_days", 30),
                    max_history_slots=memory_data.get("max_history_slots", 100),
                    compress_trigger_count=memory_data.get("compress_trigger_count", 50)
                )

            # 解析用户画像配置
            if "user_profile" in context_data:
                user_profile_data = context_data["user_profile"]
                config.context.user_profile = UserProfileConfig(
                    work_pattern_min_samples=user_profile_data.get("work_pattern_min_samples", 5),
                    app_importance_threshold=user_profile_data.get("app_importance_threshold", 10),
                    dialog_style_update_rate=user_profile_data.get("dialog_style_update_rate", 0.1),
                    topic_interest_decay=user_profile_data.get("topic_interest_decay", 0.05)
                )

            # 解析桌宠画像配置
            if "pet_profile" in context_data:
                pet_profile_data = context_data["pet_profile"]
                config.context.pet_profile = PetProfileConfig(
                    preset=pet_profile_data.get("preset", "penguin_curious"),
                    familiarity_increment=pet_profile_data.get("familiarity_increment", 0.01),
                    familiarity_max=pet_profile_data.get("familiarity_max", 1.0),
                    topic_expertise_increment=pet_profile_data.get("topic_expertise_increment", 0.05),
                    topic_expertise_max=pet_profile_data.get("topic_expertise_max", 1.0),
                    mood_decay_rate=pet_profile_data.get("mood_decay_rate", 0.1),
                    mood_min_level=pet_profile_data.get("mood_min_level", 0.2)
                )

        if "pet" in data:
            config.pet = PetConfig(**data["pet"])

        return config
