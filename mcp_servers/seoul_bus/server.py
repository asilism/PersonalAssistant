#!/usr/bin/env python3
"""
Seoul Bus Arrival MCP Server
서울시 버스 도착정보 조회 API를 제공하는 MCP 서버
"""

import os
import httpx
import xml.etree.ElementTree as ET
from fastmcp import FastMCP

mcp = FastMCP("seoul_bus")

# 서울시 버스 도착정보 API
BASE_URL = "http://ws.bus.go.kr/api/rest/arrive"

# 에러 코드 매핑
ERROR_CODES = {
    "0": "정상 처리",
    "1": "시스템 오류",
    "2": "잘못된 쿼리 요청 (파라미터 확인 필요)",
    "3": "정류소를 찾을 수 없음",
    "4": "노선을 찾을 수 없음",
    "5": "잘못된 위치 (위/경도 좌표 오류)",
    "6": "실시간 정보 읽기 실패 (잠시 후 재시도)",
    "7": "경로 검색 결과 없음",
    "8": "운행 종료",
}

# 버스 유형 매핑
BUS_TYPES = {
    "0": "일반버스",
    "1": "저상버스",
    "2": "굴절버스",
}


def get_api_key() -> str:
    """환경 변수에서 API 키를 가져옵니다."""
    api_key = os.environ.get("SEOUL_BUS_API_KEY")
    if not api_key:
        raise ValueError("SEOUL_BUS_API_KEY 환경 변수가 설정되지 않았습니다")
    return api_key


def parse_xml_response(xml_text: str) -> dict:
    """XML 응답을 파싱합니다."""
    root = ET.fromstring(xml_text)

    # 헤더 정보 파싱
    header = root.find(".//msgHeader")
    if header is None:
        return {"success": False, "error": "응답 형식 오류: 헤더를 찾을 수 없습니다"}

    header_cd = header.findtext("headerCd", "")
    header_msg = header.findtext("headerMsg", "")

    if header_cd != "0":
        error_msg = ERROR_CODES.get(header_cd, f"알 수 없는 오류 (코드: {header_cd})")
        return {"success": False, "error": error_msg, "error_code": header_cd}

    # 아이템 리스트 파싱
    items = []
    for item in root.findall(".//itemList"):
        item_dict = {}
        for child in item:
            item_dict[child.tag] = child.text
        items.append(item_dict)

    return {"success": True, "items": items, "header_msg": header_msg}


def format_arrival_info(item: dict) -> dict:
    """도착 정보를 사용자 친화적인 형태로 변환합니다."""
    def get_bus_type(code: str) -> str:
        return BUS_TYPES.get(code, "알 수 없음")

    def format_arrival_msg(msg: str, is_arrive: str, is_last: str) -> str:
        """도착 메시지에 추가 정보를 붙입니다."""
        if not msg:
            return "정보 없음"

        suffix = ""
        if is_arrive == "1":
            suffix = " [도착]"
        if is_last == "1":
            suffix += " [막차]"

        return msg + suffix

    return {
        "route_name": item.get("rtNm", ""),  # 노선명 (예: 3321)
        "station_name": item.get("stNm", ""),  # 정류소명
        "station_id": item.get("arsId", ""),  # 정류소 번호
        "first_bus": {
            "arrival_message": format_arrival_msg(
                item.get("arrmsg1", ""),
                item.get("isArrive1", "0"),
                item.get("isLast1", "0")
            ),
            "arrival_seconds": int(item.get("exps1", 0)) if item.get("exps1") else None,
            "arrival_minutes": round(int(item.get("exps1", 0)) / 60, 1) if item.get("exps1") else None,
            "bus_type": get_bus_type(item.get("busType1", "")),
            "is_arrived": item.get("isArrive1") == "1",
            "is_last": item.get("isLast1") == "1",
        },
        "second_bus": {
            "arrival_message": format_arrival_msg(
                item.get("arrmsg2", ""),
                item.get("isArrive2", "0"),
                item.get("isLast2", "0")
            ),
            "arrival_seconds": int(item.get("exps2", 0)) if item.get("exps2") else None,
            "arrival_minutes": round(int(item.get("exps2", 0)) / 60, 1) if item.get("exps2") else None,
            "bus_type": get_bus_type(item.get("busType2", "")),
            "is_arrived": item.get("isArrive2") == "1",
            "is_last": item.get("isLast2") == "1",
        },
        "first_bus_time": item.get("firstTm", ""),  # 첫차 시간
        "last_bus_time": item.get("lastTm", ""),  # 막차 시간
    }


@mcp.tool()
async def get_bus_arrival(st_id: str, bus_route_id: str, ord: str) -> dict:
    """
    특정 정류소에서 특정 버스 노선의 도착 예정 시간을 조회합니다.

    Args:
        st_id: 정류소 고유 ID (예: "124000414")
        bus_route_id: 버스 노선 ID (예: "100100578")
        ord: 정류소 순번 - 해당 노선에서 몇 번째 정류소인지 (예: "29")

    Returns:
        버스 도착 정보 (첫 번째/두 번째 버스의 도착 예정 시간, 노선명, 정류소명 등)
    """
    try:
        api_key = get_api_key()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/getArrInfoByRoute",
                params={
                    "serviceKey": api_key,
                    "stId": st_id,
                    "busRouteId": bus_route_id,
                    "ord": ord,
                },
                timeout=10.0,
            )
            response.raise_for_status()

        # XML 응답 파싱
        result = parse_xml_response(response.text)

        if not result["success"]:
            return result

        if not result["items"]:
            return {"success": False, "error": "도착 정보가 없습니다"}

        # 첫 번째 아이템만 사용 (특정 노선 조회이므로 하나만 반환됨)
        arrival_info = format_arrival_info(result["items"][0])

        return {
            "success": True,
            "arrival": arrival_info,
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"API 오류: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"요청 오류: {str(e)}"}
    except ET.ParseError as e:
        return {"success": False, "error": f"XML 파싱 오류: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"예상치 못한 오류: {str(e)}"}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8013)
