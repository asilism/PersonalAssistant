#!/usr/bin/env python3
"""
Filesystem MCP Server (Read-Only + Create)

파일시스템을 안전하게 조작할 수 있는 MCP 서버입니다.
보안을 위해 Create와 Read만 지원합니다 (Update, Delete 제외).

지원 기능:
- 파일/디렉토리 읽기
- 새 파일/디렉토리 생성
- 파일 검색
- 파일 정보 조회
"""

import asyncio
import base64
import fnmatch
import hashlib
import mimetypes
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastmcp import FastMCP

mcp = FastMCP("filesystem")

# 접근 가능한 기본 디렉토리 (보안을 위해 제한 가능)
# 비어있으면 모든 경로 접근 가능
ALLOWED_ROOTS: List[str] = []

# 접근 금지 경로 패턴
FORBIDDEN_PATTERNS = [
    "/etc/shadow",
    "/etc/passwd",
    "**/.ssh/**",
    "**/id_rsa*",
    "**/*.pem",
    "**/.env*",
    "**/secrets*",
    "**/.git/config",
]


def is_path_allowed(path: str) -> bool:
    """경로가 접근 가능한지 확인"""
    abs_path = os.path.abspath(path)

    # 금지된 패턴 확인
    for pattern in FORBIDDEN_PATTERNS:
        if fnmatch.fnmatch(abs_path, pattern) or fnmatch.fnmatch(path, pattern):
            return False

    # ALLOWED_ROOTS가 설정된 경우 해당 디렉토리 내부만 허용
    if ALLOWED_ROOTS:
        return any(abs_path.startswith(os.path.abspath(root)) for root in ALLOWED_ROOTS)

    return True


def check_path_access(path: str) -> None:
    """경로 접근 권한 확인"""
    if not is_path_allowed(path):
        raise PermissionError(f"이 경로에 대한 접근이 제한되어 있습니다: {path}")


def get_file_info(path: str) -> Dict[str, Any]:
    """파일 정보 수집"""
    stat_info = os.stat(path)
    is_dir = os.path.isdir(path)

    return {
        "name": os.path.basename(path),
        "path": os.path.abspath(path),
        "type": "directory" if is_dir else "file",
        "size": stat_info.st_size if not is_dir else None,
        "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
        "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
        "permissions": oct(stat_info.st_mode)[-3:],
        "is_readable": os.access(path, os.R_OK),
        "is_writable": os.access(path, os.W_OK),
        "is_executable": os.access(path, os.X_OK),
    }


@mcp.tool()
async def read_file(
    path: str,
    encoding: str = "utf-8",
    max_size_mb: float = 10.0
) -> dict:
    """
    파일 내용을 읽습니다.

    Args:
        path: 읽을 파일 경로
        encoding: 텍스트 인코딩 (기본: utf-8)
        max_size_mb: 최대 읽기 크기 (MB, 기본: 10MB)

    Returns:
        파일 내용 및 정보
    """
    try:
        check_path_access(path)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {path}"
            }

        if os.path.isdir(path):
            return {
                "success": False,
                "error": "디렉토리는 read_file로 읽을 수 없습니다. list_directory를 사용하세요."
            }

        file_size = os.path.getsize(path)
        max_size_bytes = int(max_size_mb * 1024 * 1024)

        if file_size > max_size_bytes:
            return {
                "success": False,
                "error": f"파일이 너무 큽니다 ({file_size / 1024 / 1024:.2f}MB > {max_size_mb}MB)"
            }

        # MIME 타입 확인
        mime_type, _ = mimetypes.guess_type(path)

        # 바이너리 파일 여부 확인
        is_binary = mime_type and not mime_type.startswith('text/') and mime_type not in [
            'application/json', 'application/xml', 'application/javascript'
        ]

        if is_binary:
            # 바이너리 파일은 base64로 반환
            with open(path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('ascii')
            return {
                "success": True,
                "path": os.path.abspath(path),
                "content_base64": content,
                "encoding": "base64",
                "mime_type": mime_type,
                "size": file_size
            }
        else:
            # 텍스트 파일
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            return {
                "success": True,
                "path": os.path.abspath(path),
                "content": content,
                "encoding": encoding,
                "mime_type": mime_type or "text/plain",
                "size": file_size,
                "lines": content.count('\n') + 1
            }

    except UnicodeDecodeError as e:
        return {
            "success": False,
            "error": f"인코딩 오류: {str(e)}. 다른 encoding을 시도해보세요."
        }
    except PermissionError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"파일 읽기 실패: {str(e)}"
        }


@mcp.tool()
async def read_file_lines(
    path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    encoding: str = "utf-8"
) -> dict:
    """
    파일의 특정 줄 범위를 읽습니다.

    Args:
        path: 읽을 파일 경로
        start_line: 시작 줄 번호 (1부터 시작)
        end_line: 끝 줄 번호 (None이면 끝까지)
        encoding: 텍스트 인코딩

    Returns:
        지정된 줄 범위의 내용
    """
    try:
        check_path_access(path)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"파일을 찾을 수 없습니다: {path}"
            }

        with open(path, 'r', encoding=encoding) as f:
            lines = f.readlines()

        total_lines = len(lines)

        if start_line < 1:
            start_line = 1
        if end_line is None or end_line > total_lines:
            end_line = total_lines

        selected_lines = lines[start_line - 1:end_line]
        content = ''.join(selected_lines)

        return {
            "success": True,
            "path": os.path.abspath(path),
            "content": content,
            "start_line": start_line,
            "end_line": end_line,
            "total_lines": total_lines,
            "lines_read": len(selected_lines)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def list_directory(
    path: str = ".",
    show_hidden: bool = False,
    recursive: bool = False,
    max_depth: int = 3
) -> dict:
    """
    디렉토리 내용을 나열합니다.

    Args:
        path: 디렉토리 경로 (기본: 현재 디렉토리)
        show_hidden: 숨김 파일 표시 여부
        recursive: 하위 디렉토리도 표시할지 여부
        max_depth: recursive일 때 최대 깊이

    Returns:
        디렉토리 내 파일 및 폴더 목록
    """
    try:
        check_path_access(path)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"디렉토리를 찾을 수 없습니다: {path}"
            }

        if not os.path.isdir(path):
            return {
                "success": False,
                "error": f"디렉토리가 아닙니다: {path}"
            }

        def list_dir(dir_path: str, current_depth: int = 0) -> List[Dict]:
            items = []

            try:
                entries = os.listdir(dir_path)
            except PermissionError:
                return [{"error": "Permission denied", "path": dir_path}]

            for entry in sorted(entries):
                # 숨김 파일 필터링
                if not show_hidden and entry.startswith('.'):
                    continue

                entry_path = os.path.join(dir_path, entry)

                # 접근 제한 경로 건너뛰기
                if not is_path_allowed(entry_path):
                    continue

                try:
                    info = get_file_info(entry_path)

                    # recursive 모드에서 하위 디렉토리 처리
                    if recursive and info["type"] == "directory" and current_depth < max_depth:
                        info["children"] = list_dir(entry_path, current_depth + 1)

                    items.append(info)
                except (PermissionError, OSError):
                    items.append({
                        "name": entry,
                        "path": entry_path,
                        "type": "unknown",
                        "error": "접근 불가"
                    })

            return items

        items = list_dir(path)

        # 통계
        dirs = sum(1 for item in items if item.get("type") == "directory")
        files = sum(1 for item in items if item.get("type") == "file")

        return {
            "success": True,
            "path": os.path.abspath(path),
            "items": items,
            "total": len(items),
            "directories": dirs,
            "files": files
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def get_file_info_tool(path: str) -> dict:
    """
    파일 또는 디렉토리의 상세 정보를 조회합니다.

    Args:
        path: 파일 또는 디렉토리 경로

    Returns:
        상세 정보 (크기, 생성일, 수정일, 권한 등)
    """
    try:
        check_path_access(path)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"경로를 찾을 수 없습니다: {path}"
            }

        info = get_file_info(path)

        # 추가 정보
        if os.path.isfile(path):
            # MIME 타입
            mime_type, _ = mimetypes.guess_type(path)
            info["mime_type"] = mime_type

            # MD5 해시 (작은 파일만)
            if info["size"] and info["size"] < 100 * 1024 * 1024:  # 100MB 미만
                with open(path, 'rb') as f:
                    info["md5"] = hashlib.md5(f.read()).hexdigest()

            # 확장자
            info["extension"] = os.path.splitext(path)[1]

        elif os.path.isdir(path):
            # 디렉토리 내 항목 수
            try:
                entries = os.listdir(path)
                info["item_count"] = len(entries)
                info["hidden_items"] = sum(1 for e in entries if e.startswith('.'))
            except PermissionError:
                info["item_count"] = "접근 불가"

        return {
            "success": True,
            **info
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def create_file(
    path: str,
    content: str = "",
    encoding: str = "utf-8",
    overwrite: bool = False
) -> dict:
    """
    새 파일을 생성합니다.

    Args:
        path: 생성할 파일 경로
        content: 파일 내용 (기본: 빈 파일)
        encoding: 텍스트 인코딩
        overwrite: 기존 파일 덮어쓰기 여부 (기본: False)

    Returns:
        생성 결과
    """
    try:
        check_path_access(path)

        # 이미 존재하는지 확인
        if os.path.exists(path) and not overwrite:
            return {
                "success": False,
                "error": f"파일이 이미 존재합니다: {path}. overwrite=True를 사용하세요."
            }

        # 부모 디렉토리 확인
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            return {
                "success": False,
                "error": f"부모 디렉토리가 존재하지 않습니다: {parent_dir}"
            }

        # 파일 생성
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)

        return {
            "success": True,
            "path": os.path.abspath(path),
            "size": len(content.encode(encoding)),
            "created": True
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def create_directory(
    path: str,
    parents: bool = True
) -> dict:
    """
    새 디렉토리를 생성합니다.

    Args:
        path: 생성할 디렉토리 경로
        parents: 부모 디렉토리도 함께 생성할지 여부 (기본: True)

    Returns:
        생성 결과
    """
    try:
        check_path_access(path)

        if os.path.exists(path):
            if os.path.isdir(path):
                return {
                    "success": True,
                    "path": os.path.abspath(path),
                    "message": "디렉토리가 이미 존재합니다."
                }
            else:
                return {
                    "success": False,
                    "error": f"같은 이름의 파일이 이미 존재합니다: {path}"
                }

        if parents:
            os.makedirs(path)
        else:
            os.mkdir(path)

        return {
            "success": True,
            "path": os.path.abspath(path),
            "created": True
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def search_files(
    path: str = ".",
    pattern: str = "*",
    search_type: str = "name",
    content_pattern: Optional[str] = None,
    max_results: int = 100,
    max_depth: int = 10
) -> dict:
    """
    파일을 검색합니다.

    Args:
        path: 검색 시작 경로
        pattern: 파일명 패턴 (glob 패턴, 예: "*.py", "test_*")
        search_type: 검색 유형 ("name": 이름, "content": 내용)
        content_pattern: 파일 내용 검색 패턴 (정규식)
        max_results: 최대 결과 수
        max_depth: 최대 검색 깊이

    Returns:
        검색 결과 목록
    """
    try:
        check_path_access(path)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"경로를 찾을 수 없습니다: {path}"
            }

        results = []
        content_regex = re.compile(content_pattern) if content_pattern else None

        def search_recursive(dir_path: str, depth: int = 0):
            if depth > max_depth or len(results) >= max_results:
                return

            try:
                entries = os.listdir(dir_path)
            except PermissionError:
                return

            for entry in entries:
                if len(results) >= max_results:
                    return

                entry_path = os.path.join(dir_path, entry)

                if not is_path_allowed(entry_path):
                    continue

                # 파일명 패턴 매칭
                if fnmatch.fnmatch(entry, pattern):
                    if os.path.isfile(entry_path):
                        # 내용 검색이 필요한 경우
                        if search_type == "content" and content_regex:
                            try:
                                with open(entry_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    matches = content_regex.findall(content)
                                    if matches:
                                        results.append({
                                            "path": os.path.abspath(entry_path),
                                            "name": entry,
                                            "matches": matches[:10]  # 최대 10개 매치
                                        })
                            except (PermissionError, OSError):
                                pass
                        else:
                            results.append({
                                "path": os.path.abspath(entry_path),
                                "name": entry,
                                "size": os.path.getsize(entry_path)
                            })

                # 하위 디렉토리 검색
                if os.path.isdir(entry_path):
                    search_recursive(entry_path, depth + 1)

        search_recursive(path)

        return {
            "success": True,
            "search_path": os.path.abspath(path),
            "pattern": pattern,
            "results": results,
            "count": len(results),
            "truncated": len(results) >= max_results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def get_directory_size(path: str) -> dict:
    """
    디렉토리의 전체 크기를 계산합니다.

    Args:
        path: 디렉토리 경로

    Returns:
        디렉토리 크기 정보
    """
    try:
        check_path_access(path)

        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"경로를 찾을 수 없습니다: {path}"
            }

        if not os.path.isdir(path):
            # 파일인 경우
            size = os.path.getsize(path)
            return {
                "success": True,
                "path": os.path.abspath(path),
                "type": "file",
                "size_bytes": size,
                "size_human": _human_readable_size(size)
            }

        total_size = 0
        file_count = 0
        dir_count = 0

        for dirpath, dirnames, filenames in os.walk(path):
            if not is_path_allowed(dirpath):
                continue

            dir_count += len(dirnames)
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                    file_count += 1
                except (PermissionError, OSError):
                    pass

        return {
            "success": True,
            "path": os.path.abspath(path),
            "type": "directory",
            "size_bytes": total_size,
            "size_human": _human_readable_size(total_size),
            "file_count": file_count,
            "directory_count": dir_count
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def _human_readable_size(size: int) -> str:
    """바이트를 사람이 읽기 쉬운 형태로 변환"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


@mcp.tool()
async def check_path_exists(path: str) -> dict:
    """
    경로가 존재하는지 확인합니다.

    Args:
        path: 확인할 경로

    Returns:
        존재 여부 및 타입
    """
    try:
        check_path_access(path)

        exists = os.path.exists(path)
        result = {
            "success": True,
            "path": os.path.abspath(path),
            "exists": exists
        }

        if exists:
            result["is_file"] = os.path.isfile(path)
            result["is_directory"] = os.path.isdir(path)
            result["is_symlink"] = os.path.islink(path)

        return result

    except PermissionError as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
async def get_current_directory() -> dict:
    """
    현재 작업 디렉토리를 반환합니다.

    Returns:
        현재 디렉토리 경로
    """
    return {
        "success": True,
        "path": os.getcwd()
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8015)
