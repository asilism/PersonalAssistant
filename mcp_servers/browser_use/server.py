#!/usr/bin/env python3
"""
Browser-Use MCP Server

AI 에이전트가 웹 브라우저를 제어하여 복잡한 작업을 자동으로 수행하는 MCP 서버입니다.
- 자연어 task를 받아 브라우저 자동 조작
- 로그인, 폼 작성, 데이터 추출 등 복잡한 웹 작업 지원
- 여러 LLM 제공자 지원 (ChatBrowserUse, OpenAI, Anthropic 등)
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from fastmcp import FastMCP

# browser-use 임포트
try:
    from browser_use import Agent, Browser, ChatBrowserUse
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

mcp = FastMCP("browser-use")

# 전역 브라우저 인스턴스 (재사용)
_browser: Optional[Any] = None


class LLMProvider(str, Enum):
    """지원되는 LLM 제공자"""
    CHAT_BROWSER_USE = "chat_browser_use"  # 기본 (유료)
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


async def get_browser(headless: bool = True, use_cloud: bool = False):
    """브라우저 인스턴스 가져오기 (재사용)"""
    global _browser

    if not BROWSER_USE_AVAILABLE:
        raise RuntimeError("browser-use가 설치되지 않았습니다. 'pip install browser-use'를 실행하세요.")

    if _browser is None:
        _browser = Browser(
            config={
                "headless": headless,
                "use_cloud": use_cloud,
            }
        )

    return _browser


async def close_browser():
    """브라우저 정리"""
    global _browser

    if _browser:
        try:
            await _browser.close()
        except:
            pass
        _browser = None


def get_llm(provider: str = None, model: str = None, api_key: str = None):
    """
    LLM 인스턴스 생성

    Args:
        provider: LLM 제공자 (chat_browser_use, openai, anthropic)
        model: 모델 이름 (제공자별로 다름)
        api_key: API 키 (환경 변수에서 가져올 수도 있음)

    Returns:
        LLM 인스턴스
    """
    # 환경 변수에서 provider 가져오기
    if provider is None:
        provider = os.getenv("BROWSER_USE_LLM_PROVIDER", "chat_browser_use")

    provider = provider.lower()

    if provider == LLMProvider.CHAT_BROWSER_USE:
        # ChatBrowserUse (기본, 유료)
        if not BROWSER_USE_AVAILABLE:
            raise RuntimeError("browser-use가 설치되지 않았습니다.")

        # API 키 확인
        if api_key:
            os.environ["BROWSER_USE_API_KEY"] = api_key
        elif not os.getenv("BROWSER_USE_API_KEY"):
            raise ValueError("BROWSER_USE_API_KEY가 설정되지 않았습니다.")

        return ChatBrowserUse()

    elif provider == LLMProvider.OPENAI:
        # OpenAI
        if not OPENAI_AVAILABLE:
            raise RuntimeError("langchain-openai가 설치되지 않았습니다. 'pip install langchain-openai'를 실행하세요.")

        # API 키 확인
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        elif not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

        model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(model=model)

    elif provider == LLMProvider.ANTHROPIC:
        # Anthropic Claude
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("langchain-anthropic가 설치되지 않았습니다. 'pip install langchain-anthropic'를 실행하세요.")

        # API 키 확인
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        elif not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

        model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        return ChatAnthropic(model=model)

    else:
        raise ValueError(f"지원하지 않는 LLM 제공자: {provider}")


@mcp.tool()
async def browse_with_agent(
    task: str,
    llm_provider: str = "chat_browser_use",
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    headless: bool = True,
    use_cloud: bool = False,
    max_steps: int = 100,
    timeout: int = 300
) -> dict:
    """
    AI 에이전트를 사용하여 자연어 task를 브라우저로 수행합니다.

    Args:
        task: 수행할 작업 (자연어로 기술)
              예: "구글에서 '날씨'를 검색하고 서울의 현재 온도를 찾아줘"
                  "아마존에서 무선 마우스를 검색하고 가격순으로 정렬해줘"
        llm_provider: LLM 제공자 (chat_browser_use, openai, anthropic)
                      기본값: "chat_browser_use" (가장 빠르고 정확하지만 유료)
        llm_model: 사용할 모델 이름 (선택 사항)
                   - openai: "gpt-4o", "gpt-4-turbo" 등
                   - anthropic: "claude-3-5-sonnet-20241022" 등
        llm_api_key: LLM API 키 (환경 변수에서 자동으로 가져올 수도 있음)
        headless: 헤드리스 모드 여부 (기본: True)
        use_cloud: Browser Use Cloud 사용 여부 (기본: False)
                   True로 설정하면 stealth 브라우저 사용 (CAPTCHA 우회 등)
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
        # LLM 초기화
        llm = get_llm(
            provider=llm_provider,
            model=llm_model,
            api_key=llm_api_key
        )

        # 브라우저 가져오기
        browser = await get_browser(headless=headless, use_cloud=use_cloud)

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
            "llm_provider": llm_provider,
            "llm_model": llm_model or "default",
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


@mcp.tool()
async def check_browser_use_status() -> dict:
    """
    Browser-Use MCP 서버의 상태를 확인합니다.

    Returns:
        서버 상태 정보
    """
    status = {
        "browser_use_installed": BROWSER_USE_AVAILABLE,
        "openai_available": OPENAI_AVAILABLE,
        "anthropic_available": ANTHROPIC_AVAILABLE,
    }

    # API 키 확인 (값은 보여주지 않고 존재 여부만)
    status["api_keys"] = {
        "BROWSER_USE_API_KEY": bool(os.getenv("BROWSER_USE_API_KEY")),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
    }

    # LLM 제공자 설정
    status["default_llm_provider"] = os.getenv("BROWSER_USE_LLM_PROVIDER", "chat_browser_use")

    # 브라우저 상태
    status["browser_running"] = _browser is not None

    return {
        "success": True,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
async def close_browser_session() -> dict:
    """
    현재 실행 중인 브라우저 세션을 종료합니다.

    Returns:
        종료 결과
    """
    try:
        await close_browser()
        return {
            "success": True,
            "message": "브라우저 세션이 종료되었습니다.",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"브라우저 종료 실패: {str(e)}"
        }


if __name__ == "__main__":
    import atexit

    # 종료 시 브라우저 정리
    @atexit.register
    def cleanup():
        if _browser:
            try:
                asyncio.get_event_loop().run_until_complete(close_browser())
            except:
                pass

    # MCP 서버 실행 (포트 8016)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8016)
