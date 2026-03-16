"""语言模型模块"""
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class LanguageModelConfig:
    """语言模型配置"""
    name: str = "qwen2.5:3b"
    base_url: str = "http://localhost:11434"
    num_predict: int = 100
    temperature: float = 0.7


class LanguageModel:
    """语言模型类，调用 Ollama API 进行对话"""

    def __init__(self, config: LanguageModelConfig):
        self.config = config
        self.api_url = f"{config.base_url}/api/chat"

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        进行对话

        Args:
            messages: 对话历史，格式为 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 系统提示词

        Returns:
            str: 模型回复，失败返回 None
        """
        try:
            # 构建消息列表
            full_messages = []

            if system_prompt:
                full_messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            full_messages.extend(messages)

            # === 打印提示词内容 ===
            print("\n" + "="*80)
            print("📤 发送给大语言模型的完整提示词：")
            print("="*80)

            if system_prompt:
                print("\n🎯 【系统提示词】")
                print("-" * 40)
                print(system_prompt)

            if messages:
                print("\n💬 【对话历史】")
                print("-" * 40)
                for msg in messages:
                    print(f"[{msg['role'].upper()}]: {msg['content']}")

            print("\n" + "="*80)
            print("✅ 提示词发送完成\n")
            # =======================

            payload = {
                "model": self.config.name,
                "messages": full_messages,
                "stream": False,
                "options": {
                    "num_predict": self.config.num_predict,
                    "temperature": self.config.temperature
                }
            }

            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            return result.get("message", {}).get("content", "").strip()

        except requests.exceptions.Timeout:
            print("语言模型请求超时")
            return None
        except requests.exceptions.RequestException as e:
            print(f"语言模型请求失败: {e}")
            return None
        except Exception as e:
            print(f"对话失败: {e}")
            return None

    def simple_chat(self, user_input: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """
        简单对话接口

        Args:
            user_input: 用户输入
            system_prompt: 系统提示词

        Returns:
            str: 模型回复
        """
        messages = [{"role": "user", "content": user_input}]
        return self.chat(messages, system_prompt)

    def check_connection(self) -> bool:
        """检查与 Ollama 服务的连接"""
        try:
            response = requests.get(f"{self.config.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
