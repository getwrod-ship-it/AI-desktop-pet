"""数据库管理模块"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.context.models import (
    ScreenEvent,
    DialogTurn,
    TimeSlotSummary,
    UserProfile,
    PetProfile,
    get_preset_profile
)


class DatabaseManager:
    """数据库管理器"""

    # 数据库版本号
    DB_VERSION = 2  # v1: 原始版本, v2: 新增画像和压缩历史表

    def __init__(self, db_path: str = "./data/context.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库"""
        # 确保数据目录存在
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # 创建版本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_version (
                version INTEGER PRIMARY KEY
            )
        """)

        # 获取当前版本
        cursor.execute("SELECT version FROM db_version LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0

        # 如果是新数据库，插入版本号
        if current_version == 0:
            cursor.execute("INSERT INTO db_version (version) VALUES (?)", (self.DB_VERSION,))

        conn.commit()
        conn.close()

        # 根据版本执行升级
        if current_version < self.DB_VERSION:
            self._upgrade_db(current_version)

        # 确保所有表都存在
        self._create_tables()

    def _create_tables(self):
        """创建所有表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 创建屏幕事件表（兼容旧版本）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screen_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                description TEXT NOT NULL,
                app_name TEXT,
                activity_type TEXT DEFAULT 'other',
                importance REAL DEFAULT 0.5
            )
        """)

        # 创建对话历史表（兼容旧版本）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dialog_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                emotion TEXT,
                importance REAL DEFAULT 1.0
            )
        """)

        # 创建压缩历史表（新增）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compressed_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_slot TEXT UNIQUE NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                dialog_summary TEXT,
                recent_dialogs TEXT,
                screen_summary TEXT,
                recent_screens TEXT,
                topics TEXT
            )
        """)

        # 创建用户画像表（新增）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id TEXT PRIMARY KEY,
                first_seen TEXT,
                last_active TEXT,
                total_interaction_days INTEGER DEFAULT 0,
                work_patterns TEXT,
                dialog_preferences TEXT,
                emotion_patterns TEXT,
                milestones TEXT,
                relationship_memory TEXT,
                capabilities TEXT
            )
        """)

        # 创建桌宠画像表（新增）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pet_profile (
                pet_id TEXT PRIMARY KEY,
                identity TEXT,
                abilities TEXT,
                conversation_style TEXT,
                relationship_state TEXT,
                memory_preferences TEXT,
                current_mood TEXT,
                behavior_patterns TEXT,
                skills TEXT
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_time_slot ON compressed_history(time_slot)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_screen_timestamp ON screen_events(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dialog_timestamp ON dialog_history(timestamp)
        """)

        conn.commit()
        conn.close()

    def _upgrade_db(self, current_version: int):
        """数据库升级"""
        print(f"[Database] 升级数据库从版本 {current_version} 到 {self.DB_VERSION}")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if current_version < 2:
                # v1 -> v2: 添加新字段和新表
                self._upgrade_v1_to_v2(cursor)

            # 更新版本号
            cursor.execute("UPDATE db_version SET version = ?", (self.DB_VERSION,))
            conn.commit()
            print(f"[Database] 数据库升级完成，当前版本: {self.DB_VERSION}")

        except Exception as e:
            conn.rollback()
            print(f"[Database] 数据库升级失败: {e}")
            raise
        finally:
            conn.close()

    def _upgrade_v1_to_v2(self, cursor: sqlite3.Cursor):
        """v1 到 v2 的升级"""
        # 检查并添加新列到 screen_events 表
        try:
            cursor.execute("ALTER TABLE screen_events ADD COLUMN app_name TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在

        try:
            cursor.execute("ALTER TABLE screen_events ADD COLUMN activity_type TEXT DEFAULT 'other'")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE screen_events ADD COLUMN importance REAL DEFAULT 0.5")
        except sqlite3.OperationalError:
            pass

        # 检查并添加新列到 dialog_history 表
        try:
            cursor.execute("ALTER TABLE dialog_history ADD COLUMN emotion TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE dialog_history ADD COLUMN importance REAL DEFAULT 1.0")
        except sqlite3.OperationalError:
            pass

    # ============ 屏幕事件操作 ============

    def add_screen_event(self, event: ScreenEvent):
        """添加屏幕事件"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO screen_events (timestamp, description, app_name, activity_type, importance)
            VALUES (?, ?, ?, ?, ?)
        """, (
            event.timestamp,
            event.description,
            event.app_name,
            event.activity_type,
            event.importance
        ))
        conn.commit()
        conn.close()

    def get_recent_screen_events(self, limit: int = 100) -> List[ScreenEvent]:
        """获取最近的屏幕事件"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, description, app_name, activity_type, importance
            FROM screen_events
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            ScreenEvent(
                timestamp=row[0],
                description=row[1],
                app_name=row[2],
                activity_type=row[3] or "other",
                importance=row[4] or 0.5
            )
            for row in reversed(rows)
        ]

    def get_screen_events_since(self, since_time: datetime) -> List[ScreenEvent]:
        """获取指定时间之后的屏幕事件"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, description, app_name, activity_type, importance
            FROM screen_events
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_time.isoformat(),))
        rows = cursor.fetchall()
        conn.close()

        return [
            ScreenEvent(
                timestamp=row[0],
                description=row[1],
                app_name=row[2],
                activity_type=row[3] or "other",
                importance=row[4] or 0.5
            )
            for row in rows
        ]

    # ============ 对话记录操作 ============

    def add_dialog(self, turn: DialogTurn):
        """添加对话记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dialog_history (timestamp, role, content, emotion, importance)
            VALUES (?, ?, ?, ?, ?)
        """, (
            turn.timestamp,
            turn.role,
            turn.content,
            turn.emotion,
            turn.importance
        ))
        conn.commit()
        conn.close()

    def get_recent_dialogs(self, limit: int = 100) -> List[DialogTurn]:
        """获取最近的对话记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, role, content, emotion, importance
            FROM dialog_history
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            DialogTurn(
                timestamp=row[0],
                role=row[1],
                content=row[2],
                emotion=row[3],
                importance=row[4] or 1.0
            )
            for row in reversed(rows)
        ]

    def get_dialogs_since(self, since_time: datetime) -> List[DialogTurn]:
        """获取指定时间之后的对话记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, role, content, emotion, importance
            FROM dialog_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_time.isoformat(),))
        rows = cursor.fetchall()
        conn.close()

        return [
            DialogTurn(
                timestamp=row[0],
                role=row[1],
                content=row[2],
                emotion=row[3],
                importance=row[4] or 1.0
            )
            for row in rows
        ]

    # ============ 压缩历史操作 ============

    def save_time_slot_summary(self, summary: TimeSlotSummary):
        """保存时间段摘要"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO compressed_history
            (time_slot, start_time, end_time, dialog_summary, recent_dialogs,
             screen_summary, recent_screens, topics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.time_slot,
            summary.start_time,
            summary.end_time,
            summary.dialog_summary,
            json.dumps(summary.recent_dialogs, ensure_ascii=False),
            summary.screen_summary,
            json.dumps(summary.recent_screens, ensure_ascii=False),
            json.dumps(summary.topics, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

    def get_recent_summaries(self, limit: int = 5) -> List[TimeSlotSummary]:
        """获取最近的时间段摘要"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT time_slot, start_time, end_time, dialog_summary, recent_dialogs,
                   screen_summary, recent_screens, topics
            FROM compressed_history
            ORDER BY start_time DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        summaries = []
        for row in rows:
            summaries.append(TimeSlotSummary(
                time_slot=row[0],
                start_time=row[1],
                end_time=row[2],
                dialog_summary=row[3] or "",
                recent_dialogs=json.loads(row[4]) if row[4] else [],
                screen_summary=row[5] or "",
                recent_screens=json.loads(row[6]) if row[6] else [],
                topics=json.loads(row[7]) if row[7] else []
            ))

        return list(reversed(summaries))

    def cleanup_old_summaries(self, keep_days: int = 30):
        """清理过期的压缩历史"""
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM compressed_history WHERE end_time < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ============ 用户画像操作 ============

    def load_user_profile(self, user_id: str = "default") -> Optional[UserProfile]:
        """加载用户画像"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT first_seen, last_active, total_interaction_days,
                   work_patterns, dialog_preferences, emotion_patterns,
                   milestones, relationship_memory, capabilities
            FROM user_profile WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        def safe_json_load(data, default=None):
            if default is None:
                default = {}
            try:
                return json.loads(data) if data else default
            except (json.JSONDecodeError, TypeError):
                return default

        work_patterns = safe_json_load(row[3])
        dialog_preferences = safe_json_load(row[4])
        emotion_patterns = safe_json_load(row[5])
        milestones = safe_json_load(row[6], [])
        relationship_memory = safe_json_load(row[7])
        capabilities = safe_json_load(row[8])

        return UserProfile(
            user_id=user_id,
            first_seen=row[0] or "",
            last_active=row[1] or "",
            total_interaction_days=row[2] or 0,
            working_hours=work_patterns.get("working_hours", []),
            primary_apps=work_patterns.get("primary_apps", {}),
            productivity_style=work_patterns.get("productivity_style", "unknown"),
            break_patterns=work_patterns.get("break_patterns", []),
            communication_style=dialog_preferences.get("communication_style", "unknown"),
            response_timing=dialog_preferences.get("response_timing", "unknown"),
            topic_interests=dialog_preferences.get("topic_interests", {}),
            question_style=dialog_preferences.get("question_style", "unknown"),
            avg_daily_mood=emotion_patterns.get("avg_daily_mood", "neutral"),
            stress_indicators=emotion_patterns.get("stress_indicators", []),
            joy_triggers=emotion_patterns.get("joy_triggers", []),
            milestones=milestones,
            trust_level=relationship_memory.get("trust_level", 0.5),
            interaction_frequency=relationship_memory.get("interaction_frequency", 0),
            last_deep_conversation=relationship_memory.get("last_deep_conversation", ""),
            shared_contexts=relationship_memory.get("shared_contexts", []),
            technical_skills=capabilities.get("technical_skills", []),
            domains_of_interest=capabilities.get("domains_of_interest", []),
            learning_style=capabilities.get("learning_style", "unknown")
        )

    def save_user_profile(self, profile: UserProfile):
        """保存用户画像"""
        work_patterns = {
            "working_hours": profile.working_hours,
            "primary_apps": profile.primary_apps,
            "productivity_style": profile.productivity_style,
            "break_patterns": profile.break_patterns
        }
        dialog_preferences = {
            "communication_style": profile.communication_style,
            "response_timing": profile.response_timing,
            "topic_interests": profile.topic_interests,
            "question_style": profile.question_style
        }
        emotion_patterns = {
            "avg_daily_mood": profile.avg_daily_mood,
            "stress_indicators": profile.stress_indicators,
            "joy_triggers": profile.joy_triggers
        }
        relationship_memory = {
            "trust_level": profile.trust_level,
            "interaction_frequency": profile.interaction_frequency,
            "last_deep_conversation": profile.last_deep_conversation,
            "shared_contexts": profile.shared_contexts
        }
        capabilities = {
            "technical_skills": profile.technical_skills,
            "domains_of_interest": profile.domains_of_interest,
            "learning_style": profile.learning_style
        }

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_profile
            (user_id, first_seen, last_active, total_interaction_days,
             work_patterns, dialog_preferences, emotion_patterns,
             milestones, relationship_memory, capabilities)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.user_id,
            profile.first_seen,
            profile.last_active,
            profile.total_interaction_days,
            json.dumps(work_patterns, ensure_ascii=False),
            json.dumps(dialog_preferences, ensure_ascii=False),
            json.dumps(emotion_patterns, ensure_ascii=False),
            json.dumps(profile.milestones, ensure_ascii=False),
            json.dumps(relationship_memory, ensure_ascii=False),
            json.dumps(capabilities, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

    # ============ 桌宠画像操作 ============

    def load_pet_profile(self, pet_id: str = "default", preset: str = "penguin_curious") -> PetProfile:
        """加载桌宠画像"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT identity, abilities, conversation_style, relationship_state,
                   memory_preferences, current_mood, behavior_patterns, skills
            FROM pet_profile WHERE pet_id = ?
        """, (pet_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            # 返回预设画像
            return get_preset_profile(preset)

        def safe_json_load(data, default=None):
            if default is None:
                default = {}
            try:
                return json.loads(data) if data else default
            except (json.JSONDecodeError, TypeError):
                return default

        identity = safe_json_load(row[0])
        abilities = safe_json_load(row[1])
        conversation_style = safe_json_load(row[2])
        relationship_state = safe_json_load(row[3])
        memory_preferences = safe_json_load(row[4])
        current_mood = safe_json_load(row[5])
        behavior_patterns = safe_json_load(row[6])
        skills = safe_json_load(row[7])

        return PetProfile(
            name=identity.get("name", "小爪"),
            species=identity.get("species", "企鹅"),
            personality=identity.get("personality", "活泼、好奇、乐于助人"),
            default_mood=identity.get("default_mood", "友好"),
            catchphrase=identity.get("catchphrase", "让我看看~"),
            can_see_screen=abilities.get("can_see_screen", True),
            can_remember=abilities.get("can_remember", True),
            can_learn=abilities.get("can_learn", True),
            response_style=abilities.get("response_style", "友好助手"),
            default_tone=conversation_style.get("default_tone", "轻松愉快"),
            learned_tones=conversation_style.get("learned_tones", {}),
            humor_level=conversation_style.get("humor_level", 6),
            empathy_level=conversation_style.get("empathy_level", 8),
            familiarity_level=relationship_state.get("familiarity_level", 0.0),
            preferred_nickname=relationship_state.get("preferred_nickname"),
            inside_jokes=relationship_state.get("inside_jokes", []),
            shared_routines=relationship_state.get("shared_routines", []),
            importance_weights=memory_preferences.get("importance_weights", {}),
            retention_duration=memory_preferences.get("retention_duration", {}),
            compression_style=memory_preferences.get("compression_style", "balanced"),
            emotion=current_mood.get("emotion", "idle"),
            energy_level=current_mood.get("energy_level", 1.0),
            attention_level=current_mood.get("attention_level", 1.0),
            last_mood_update=current_mood.get("last_mood_update", ""),
            initiative_level=behavior_patterns.get("initiative_level", 7),
            greeting_style=behavior_patterns.get("greeting_style", "你好呀！今天有什么可以帮你的？"),
            farewell_style=behavior_patterns.get("farewell_style", "随时叫我哦~"),
            interruption_policy=behavior_patterns.get("interruption_policy", "礼貌提醒"),
            topic_expertise=skills.get("topic_expertise", {}),
            response_patterns=skills.get("response_patterns", {}),
            learned_responses=skills.get("learned_responses", [])
        )

    def save_pet_profile(self, profile: PetProfile, pet_id: str = "default"):
        """保存桌宠画像"""
        identity = {
            "name": profile.name,
            "species": profile.species,
            "personality": profile.personality,
            "default_mood": profile.default_mood,
            "catchphrase": profile.catchphrase
        }
        abilities = {
            "can_see_screen": profile.can_see_screen,
            "can_remember": profile.can_remember,
            "can_learn": profile.can_learn,
            "response_style": profile.response_style
        }
        conversation_style = {
            "default_tone": profile.default_tone,
            "learned_tones": profile.learned_tones,
            "humor_level": profile.humor_level,
            "empathy_level": profile.empathy_level
        }
        relationship_state = {
            "familiarity_level": profile.familiarity_level,
            "preferred_nickname": profile.preferred_nickname,
            "inside_jokes": profile.inside_jokes,
            "shared_routines": profile.shared_routines
        }
        memory_preferences = {
            "importance_weights": profile.importance_weights,
            "retention_duration": profile.retention_duration,
            "compression_style": profile.compression_style
        }
        current_mood = {
            "emotion": profile.emotion,
            "energy_level": profile.energy_level,
            "attention_level": profile.attention_level,
            "last_mood_update": profile.last_mood_update
        }
        behavior_patterns = {
            "initiative_level": profile.initiative_level,
            "greeting_style": profile.greeting_style,
            "farewell_style": profile.farewell_style,
            "interruption_policy": profile.interruption_policy
        }
        skills = {
            "topic_expertise": profile.topic_expertise,
            "response_patterns": profile.response_patterns,
            "learned_responses": profile.learned_responses
        }

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pet_profile
            (pet_id, identity, abilities, conversation_style, relationship_state,
             memory_preferences, current_mood, behavior_patterns, skills)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pet_id,
            json.dumps(identity, ensure_ascii=False),
            json.dumps(abilities, ensure_ascii=False),
            json.dumps(conversation_style, ensure_ascii=False),
            json.dumps(relationship_state, ensure_ascii=False),
            json.dumps(memory_preferences, ensure_ascii=False),
            json.dumps(current_mood, ensure_ascii=False),
            json.dumps(behavior_patterns, ensure_ascii=False),
            json.dumps(skills, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

    # ============ 清理操作 ============

    def clear_all(self):
        """清空所有数据"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM screen_events")
        cursor.execute("DELETE FROM dialog_history")
        cursor.execute("DELETE FROM compressed_history")
        conn.commit()
        conn.close()

    def clear_profiles(self):
        """清除用户和桌宠画像"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profile")
        cursor.execute("DELETE FROM pet_profile")
        conn.commit()
        conn.close()
        print("[Database] 画像已清除，下次启动将使用预设配置")
        cursor.execute("DELETE FROM compressed_history")
        conn.commit()
        conn.close()
