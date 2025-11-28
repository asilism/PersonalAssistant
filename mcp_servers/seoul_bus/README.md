# Seoul Bus Arrival MCP Server

서울시 버스 도착정보 조회 MCP 서버

## 기능

- `get_bus_arrival`: 특정 정류소에서 특정 버스 노선의 도착 예정 시간 조회

## 환경 변수

```
SEOUL_BUS_API_KEY=<공공데이터포털에서 발급받은 서비스키>
```

API 키는 [공공데이터포털](https://www.data.go.kr)에서 "서울특별시_정류소정보조회 서비스" 신청 후 발급받을 수 있습니다.

## 실행

```bash
cd mcp_servers/seoul_bus
python server.py
```

기본 포트: 8013

## Tool: get_bus_arrival

### 설명
특정 정류소에서 특정 버스 노선의 도착 예정 시간을 조회합니다.

### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|----------|------|------|------|------|
| st_id | string | Y | 정류소 고유 ID | "124000414" |
| bus_route_id | string | Y | 버스 노선 ID | "100100578" |
| ord | string | Y | 정류소 순번 (해당 노선에서 몇 번째 정류소인지) | "29" |

### 응답 예시

```json
{
  "success": true,
  "arrival": {
    "route_name": "3321",
    "station_name": "강남역",
    "station_id": "25361",
    "first_bus": {
      "arrival_message": "10분1초후 [6번째 전]",
      "arrival_seconds": 601,
      "arrival_minutes": 10.0,
      "bus_type": "저상버스",
      "is_arrived": false,
      "is_last": false
    },
    "second_bus": {
      "arrival_message": "28분57초후 [14번째 전]",
      "arrival_seconds": 1737,
      "arrival_minutes": 28.9,
      "bus_type": "일반버스",
      "is_arrived": false,
      "is_last": false
    },
    "first_bus_time": "20230927050800",
    "last_bus_time": "20230928000800"
  }
}
```

## MCP 서버 등록 방법

Web UI Settings 또는 API를 통해 등록:

```json
{
  "server_name": "seoul_bus",
  "transport": "streamable-http",
  "url": "http://localhost:8013/mcp",
  "enabled": true
}
```

## 참고

- 정류소 ID, 노선 ID, 정류소 순번은 서울시 버스노선정보조회 API를 통해 조회할 수 있습니다
- 도착시간은 `arrival_seconds` (초 단위)와 `arrival_minutes` (분 단위) 두 가지 형식으로 제공됩니다
- 운행 종료 시 에러코드 8이 반환됩니다
