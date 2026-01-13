#!/usr/bin/env python3
"""
Computer Control MCP Server

컴퓨터를 조작할 수 있는 MCP 서버입니다.
- 마우스 조작 (클릭, 이동, 드래그)
- 키보드 입력
- 스크린샷 캡처
- 화면 정보 조회
- 클립보드 조작
- 창 관리 (선택적)
"""

import asyncio
import base64
import io
import os
import platform
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Literal

from fastmcp import FastMCP

# pyautogui 임포트
try:
    import pyautogui
    # 안전 기능 활성화 (화면 모서리로 마우스 이동 시 프로그램 중지)
    pyautogui.FAILSAFE = True
    # 명령 사이 대기 시간
    pyautogui.PAUSE = 0.1
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Pillow for image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# pyperclip for clipboard
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

mcp = FastMCP("computer")


def check_pyautogui():
    """pyautogui 사용 가능 여부 확인"""
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError("pyautogui가 설치되지 않았습니다. 'pip install pyautogui'를 실행하세요.")


def image_to_base64(image) -> str:
    """PIL 이미지를 base64 문자열로 변환"""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


@mcp.tool()
async def get_screen_info() -> dict:
    """
    화면 정보를 조회합니다.

    Returns:
        화면 해상도, 마우스 위치 등의 정보
    """
    check_pyautogui()

    screen_width, screen_height = pyautogui.size()
    mouse_x, mouse_y = pyautogui.position()

    return {
        "success": True,
        "screen": {
            "width": screen_width,
            "height": screen_height
        },
        "mouse_position": {
            "x": mouse_x,
            "y": mouse_y
        },
        "platform": platform.system(),
        "failsafe_enabled": pyautogui.FAILSAFE
    }


@mcp.tool()
async def take_screenshot(
    region: Optional[dict] = None,
    save_path: Optional[str] = None
) -> dict:
    """
    화면 스크린샷을 캡처합니다.

    Args:
        region: 캡처할 영역 {"x": int, "y": int, "width": int, "height": int}
                지정하지 않으면 전체 화면
        save_path: 저장 경로 (지정하지 않으면 base64로 반환)

    Returns:
        스크린샷 이미지 (base64) 또는 저장 경로
    """
    check_pyautogui()

    try:
        if region:
            screenshot = pyautogui.screenshot(
                region=(region["x"], region["y"], region["width"], region["height"])
            )
        else:
            screenshot = pyautogui.screenshot()

        result = {
            "success": True,
            "dimensions": {
                "width": screenshot.width,
                "height": screenshot.height
            },
            "timestamp": datetime.now().isoformat()
        }

        if save_path:
            screenshot.save(save_path)
            result["saved_to"] = save_path
        else:
            result["image_base64"] = image_to_base64(screenshot)
            result["format"] = "png"

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"스크린샷 캡처 실패: {str(e)}"
        }


@mcp.tool()
async def mouse_move(
    x: int,
    y: int,
    duration: float = 0.25
) -> dict:
    """
    마우스를 지정한 위치로 이동합니다.

    Args:
        x: 목표 X 좌표
        y: 목표 Y 좌표
        duration: 이동 시간 (초, 기본: 0.25)

    Returns:
        이동 결과
    """
    check_pyautogui()

    try:
        pyautogui.moveTo(x, y, duration=duration)
        current_x, current_y = pyautogui.position()

        return {
            "success": True,
            "moved_to": {"x": current_x, "y": current_y},
            "duration": duration
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def mouse_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: Literal["left", "right", "middle"] = "left",
    clicks: int = 1,
    interval: float = 0.1
) -> dict:
    """
    마우스 클릭을 수행합니다.

    Args:
        x: 클릭할 X 좌표 (None이면 현재 위치)
        y: 클릭할 Y 좌표 (None이면 현재 위치)
        button: 마우스 버튼 ("left", "right", "middle")
        clicks: 클릭 횟수 (2면 더블클릭)
        interval: 클릭 사이 간격 (초)

    Returns:
        클릭 결과
    """
    check_pyautogui()

    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)
        else:
            pyautogui.click(clicks=clicks, interval=interval, button=button)

        current_x, current_y = pyautogui.position()

        return {
            "success": True,
            "clicked_at": {"x": current_x, "y": current_y},
            "button": button,
            "clicks": clicks
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    button: Literal["left", "right", "middle"] = "left"
) -> dict:
    """
    마우스 드래그를 수행합니다.

    Args:
        start_x: 시작 X 좌표
        start_y: 시작 Y 좌표
        end_x: 끝 X 좌표
        end_y: 끝 Y 좌표
        duration: 드래그 시간 (초)
        button: 마우스 버튼

    Returns:
        드래그 결과
    """
    check_pyautogui()

    try:
        pyautogui.moveTo(start_x, start_y)
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)

        return {
            "success": True,
            "from": {"x": start_x, "y": start_y},
            "to": {"x": end_x, "y": end_y},
            "duration": duration
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def mouse_scroll(
    clicks: int,
    x: Optional[int] = None,
    y: Optional[int] = None
) -> dict:
    """
    마우스 스크롤을 수행합니다.

    Args:
        clicks: 스크롤 양 (양수: 위로, 음수: 아래로)
        x: 스크롤할 X 좌표 (None이면 현재 위치)
        y: 스크롤할 Y 좌표 (None이면 현재 위치)

    Returns:
        스크롤 결과
    """
    check_pyautogui()

    try:
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x, y)
        else:
            pyautogui.scroll(clicks)

        return {
            "success": True,
            "scroll_amount": clicks,
            "direction": "up" if clicks > 0 else "down"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def keyboard_type(
    text: str,
    interval: float = 0.02
) -> dict:
    """
    키보드로 텍스트를 입력합니다.

    Args:
        text: 입력할 텍스트
        interval: 키 입력 간격 (초)

    Returns:
        입력 결과
    """
    check_pyautogui()

    try:
        pyautogui.typewrite(text, interval=interval)

        return {
            "success": True,
            "typed_text": text,
            "length": len(text)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def keyboard_write(
    text: str,
    interval: float = 0.0
) -> dict:
    """
    키보드로 텍스트를 입력합니다 (유니코드/한글 지원).

    Args:
        text: 입력할 텍스트 (한글 등 유니코드 지원)
        interval: 키 입력 간격 (초)

    Returns:
        입력 결과
    """
    check_pyautogui()

    try:
        # write()는 유니코드를 지원 (클립보드 사용)
        pyautogui.write(text, interval=interval)

        return {
            "success": True,
            "typed_text": text,
            "length": len(text)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def keyboard_press(
    key: str
) -> dict:
    """
    특수 키를 누릅니다.

    Args:
        key: 키 이름 (예: "enter", "tab", "escape", "space", "backspace",
             "up", "down", "left", "right", "f1"~"f12", "ctrl", "alt", "shift" 등)

    Returns:
        키 입력 결과
    """
    check_pyautogui()

    try:
        pyautogui.press(key)

        return {
            "success": True,
            "pressed_key": key
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def keyboard_hotkey(keys: list[str]) -> dict:
    """
    단축키 조합을 입력합니다.

    Args:
        keys: 키 조합 리스트 (예: ["ctrl", "c"])

    Returns:
        단축키 입력 결과

    예시:
        keyboard_hotkey(["ctrl", "c"])  # Ctrl+C
        keyboard_hotkey(["ctrl", "alt", "delete"])  # Ctrl+Alt+Delete
    """
    check_pyautogui()

    try:
        pyautogui.hotkey(*keys)

        return {
            "success": True,
            "hotkey": "+".join(keys)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def keyboard_shortcut(
    shortcut: str
) -> dict:
    """
    단축키 조합을 입력합니다 (문자열 형식).

    Args:
        shortcut: 단축키 문자열 (예: "ctrl+c", "ctrl+alt+del", "cmd+shift+s")

    Returns:
        단축키 입력 결과
    """
    check_pyautogui()

    try:
        # "ctrl+c" -> ["ctrl", "c"]
        keys = [k.strip().lower() for k in shortcut.split("+")]

        # mac의 cmd를 ctrl로 변환하거나 그 반대
        if platform.system() == "Darwin":
            keys = ["command" if k == "ctrl" else k for k in keys]

        pyautogui.hotkey(*keys)

        return {
            "success": True,
            "shortcut": shortcut,
            "keys": keys
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def get_clipboard() -> dict:
    """
    클립보드 내용을 가져옵니다.

    Returns:
        클립보드 텍스트 내용
    """
    if not PYPERCLIP_AVAILABLE:
        return {
            "success": False,
            "error": "pyperclip이 설치되지 않았습니다. 'pip install pyperclip'을 실행하세요."
        }

    try:
        content = pyperclip.paste()
        return {
            "success": True,
            "content": content,
            "length": len(content)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def set_clipboard(text: str) -> dict:
    """
    클립보드에 텍스트를 복사합니다.

    Args:
        text: 복사할 텍스트

    Returns:
        복사 결과
    """
    if not PYPERCLIP_AVAILABLE:
        return {
            "success": False,
            "error": "pyperclip이 설치되지 않았습니다. 'pip install pyperclip'을 실행하세요."
        }

    try:
        pyperclip.copy(text)
        return {
            "success": True,
            "copied_text": text,
            "length": len(text)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def locate_on_screen(
    image_path: str,
    confidence: float = 0.9,
    grayscale: bool = False
) -> dict:
    """
    화면에서 이미지를 찾습니다.

    Args:
        image_path: 찾을 이미지 파일 경로
        confidence: 유사도 임계값 (0.0 ~ 1.0, 기본: 0.9)
        grayscale: 흑백 검색 사용 여부 (속도 향상)

    Returns:
        이미지 위치 (중심점 좌표)
    """
    check_pyautogui()

    try:
        location = pyautogui.locateCenterOnScreen(
            image_path,
            confidence=confidence,
            grayscale=grayscale
        )

        if location:
            return {
                "success": True,
                "found": True,
                "center": {"x": location[0], "y": location[1]}
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": "이미지를 화면에서 찾을 수 없습니다."
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def alert_box(
    message: str,
    title: str = "알림"
) -> dict:
    """
    알림 대화상자를 표시합니다.

    Args:
        message: 표시할 메시지
        title: 대화상자 제목

    Returns:
        사용자 응답
    """
    check_pyautogui()

    try:
        result = pyautogui.alert(text=message, title=title)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def confirm_box(
    message: str,
    title: str = "확인"
) -> dict:
    """
    확인 대화상자를 표시합니다 (OK/Cancel).

    Args:
        message: 표시할 메시지
        title: 대화상자 제목

    Returns:
        사용자 선택 ("OK" 또는 "Cancel")
    """
    check_pyautogui()

    try:
        result = pyautogui.confirm(text=message, title=title)
        return {
            "success": True,
            "result": result,
            "confirmed": result == "OK"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def prompt_box(
    message: str,
    title: str = "입력",
    default: str = ""
) -> dict:
    """
    텍스트 입력 대화상자를 표시합니다.

    Args:
        message: 표시할 메시지
        title: 대화상자 제목
        default: 기본값

    Returns:
        사용자가 입력한 텍스트 (취소 시 None)
    """
    check_pyautogui()

    try:
        result = pyautogui.prompt(text=message, title=title, default=default)
        return {
            "success": True,
            "result": result,
            "cancelled": result is None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def run_command(
    command: str,
    shell: bool = True,
    timeout: int = 30
) -> dict:
    """
    시스템 명령을 실행합니다.

    Args:
        command: 실행할 명령어
        shell: 쉘을 통해 실행할지 여부
        timeout: 실행 제한 시간 (초)

    Returns:
        명령 실행 결과
    """
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return {
            "success": True,
            "command": command,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"명령 실행 시간 초과 ({timeout}초)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def open_application(
    path: str,
    args: Optional[List[str]] = None
) -> dict:
    """
    애플리케이션을 실행합니다.

    Args:
        path: 애플리케이션 경로 또는 이름
        args: 실행 인자 목록

    Returns:
        실행 결과
    """
    try:
        cmd = [path]
        if args:
            cmd.extend(args)

        process = subprocess.Popen(cmd)

        return {
            "success": True,
            "path": path,
            "pid": process.pid
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def open_url(url: str) -> dict:
    """
    기본 브라우저에서 URL을 엽니다.

    Args:
        url: 열 URL

    Returns:
        실행 결과
    """
    import webbrowser

    try:
        webbrowser.open(url)
        return {
            "success": True,
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8014)
