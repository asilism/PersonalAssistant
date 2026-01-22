"""
Browser-Use Built-in Tool

AI 에이전트가 웹 브라우저를 제어하여 복잡한 작업을 자동으로 수행하는 내장 도구입니다.
- 자연어 task를 받아 브라우저 자동 조작
- 로그인, 폼 작성, 데이터 추출 등 복잡한 웹 작업 지원
- 설정에서 LLM provider 및 모델 자동 사용
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, Any, Dict

# browser-use 임포트
try:
    from browser_use import Agent, Browser
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False

# Optional LLM providers
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_anthropic import ChatAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class BrowserUseTool:
    """Browser-Use 내장 도구"""

    def __init__(self, llm_provider: str = "anthropic", llm_model: str = None, llm_api_key: str = None, llm_base_url: Optional[str] = None):
        """
        Initialize BrowserUseTool with LLM configuration

        Args:
            llm_provider: LLM 제공자 (anthropic, openai)
            llm_model: 사용할 모델 이름
            llm_api_key: LLM API 키
            llm_base_url: LLM Base URL (선택사항)
        """
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url
        self._browser: Optional[Any] = None

    async def get_browser(self, headless: bool = True) -> Any:
        """브라우저 인스턴스 가져오기 (재사용)"""
        if not BROWSER_USE_AVAILABLE:
            raise RuntimeError("browser-use가 설치되지 않았습니다. 'pip install browser-use'를 실행하세요.")

        if self._browser is None:
            self._browser = Browser(
                config={
                    "headless": headless,
                }
            )

        return self._browser

    async def close_browser(self):
        """브라우저 정리"""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
            self._browser = None

    def get_llm(self):
        """
        설정에서 LLM 인스턴스 생성

        Returns:
            LLM 인스턴스
        """
        provider = self.llm_provider.lower()

        if provider == "anthropic":
            # Anthropic Claude
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError("langchain-anthropic가 설치되지 않았습니다. 'pip install langchain-anthropic'를 실행하세요.")

            # API 키 확인
            api_key = self.llm_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

            model = self.llm_model or "claude-3-5-sonnet-20241022"

            kwargs = {"model": model, "api_key": api_key}
            if self.llm_base_url:
                kwargs["base_url"] = self.llm_base_url

            return ChatAnthropic(**kwargs)

        elif provider == "openai":
            # OpenAI
            if not OPENAI_AVAILABLE:
                raise RuntimeError("langchain-openai가 설치되지 않았습니다. 'pip install langchain-openai'를 실행하세요.")

            # API 키 확인
            api_key = self.llm_api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

            model = self.llm_model or "gpt-4o"

            kwargs = {"model": model, "api_key": api_key}
            if self.llm_base_url:
                kwargs["base_url"] = self.llm_base_url

            return ChatOpenAI(**kwargs)

        else:
            raise ValueError(f"지원하지 않는 LLM 제공자: {provider}. 'anthropic' 또는 'openai'를 사용하세요.")

    async def browse_with_agent(
        self,
        task: str,
        headless: bool = True,
        max_steps: int = 100,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        AI 에이전트를 사용하여 자연어 task를 브라우저로 수행합니다.

        Args:
            task: 수행할 작업 (자연어로 기술)
                  예: "구글에서 '날씨'를 검색하고 서울의 현재 온도를 찾아줘"
                      "아마존에서 무선 마우스를 검색하고 가격순으로 정렬해줘"
            headless: 헤드리스 모드 여부 (기본: True)
            max_steps: 최대 단계 수 (기본: 100)
            timeout: 작업 타임아웃 (초, 기본: 300)

        Returns:
            작업 수행 결과 및 히스토리
        """
        if not BROWSER_USE_AVAILABLE:
            return {
                "success": False,
                "error": "browser-use가 설치되지 않았습니다. 'pip install browser-use'를 실행하세요."
            }

        try:
            # LLM 초기화 (설정에서 가져온 값 사용)
            llm = self.get_llm()

            # 브라우저 가져오기
            browser = await self.get_browser(headless=headless)

            # Agent 생성
            agent = Agent(
                task=task,
                llm=llm,
                browser=browser,
                max_steps=max_steps,
            )

            # 타임아웃과 함께 실행
            history = await asyncio.wait_for(
                agent.run(),
                timeout=timeout
            )

            # 결과 포맷팅
            result = {
                "success": True,
                "task": task,
                "llm_provider": self.llm_provider,
                "llm_model": self.llm_model or "default",
                "steps_taken": len(history) if history else 0,
                "timestamp": datetime.now().isoformat()
            }

            # 히스토리 정보 추출
            if history:
                # 마지막 결과 추출
                last_result = history[-1] if history else None
                if last_result:
                    result["final_result"] = str(last_result)

                # 각 단계 요약
                steps_summary = []
                for i, step in enumerate(history):
                    steps_summary.append({
                        "step_number": i + 1,
                        "action": str(step)[:200]  # 길이 제한
                    })
                result["steps"] = steps_summary

            return result

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"작업이 {timeout}초 내에 완료되지 않았습니다.",
                "task": task
            }

        except ValueError as e:
            return {
                "success": False,
                "error": f"설정 오류: {str(e)}",
                "task": task
            }

        except RuntimeError as e:
            return {
                "success": False,
                "error": f"런타임 오류: {str(e)}",
                "task": task
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"작업 수행 실패: {str(e)}",
                "task": task
            }

    @staticmethod
    def get_tool_definition() -> Dict[str, Any]:
        """
        도구 정의 반환 (MCP 형식과 호환)

        Returns:
            ToolDefinition 형식의 딕셔너리
        """
        return {
            "name": "browse_with_agent",
            "description": """AI 에이전트를 사용하여 자연어 task를 브라우저로 수행합니다.

예시:
- "구글에서 '날씨'를 검색하고 서울의 현재 온도를 찾아줘"
- "아마존에서 무선 마우스를 검색하고 가격순으로 정렬해줘"
- "네이버에 로그인하고 내 메일함을 열어줘"

이 도구는 설정에서 지정한 LLM provider와 모델을 자동으로 사용합니다.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "수행할 작업 (자연어로 기술)"
                    },
                    "headless": {
                        "type": "boolean",
                        "description": "헤드리스 모드 여부 (기본: True)",
                        "default": True
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "최대 단계 수 (기본: 100)",
                        "default": 100
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "작업 타임아웃 (초, 기본: 300)",
                        "default": 300
                    }
                },
                "required": ["task"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "작업 성공 여부"
                    },
                    "task": {
                        "type": "string",
                        "description": "수행한 작업"
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": "사용한 LLM 제공자"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "사용한 LLM 모델"
                    },
                    "steps_taken": {
                        "type": "integer",
                        "description": "수행한 단계 수"
                    },
                    "final_result": {
                        "type": "string",
                        "description": "최종 결과"
                    },
                    "steps": {
                        "type": "array",
                        "description": "각 단계 요약",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step_number": {"type": "integer"},
                                "action": {"type": "string"}
                            }
                        }
                    },
                    "error": {
                        "type": "string",
                        "description": "오류 메시지 (실패 시)"
                    }
                },
                "required": ["success"]
            }
        }
