# 서울시 버스도착정보 MCP 서버 개발 명세서

## 개요
서울시 공공데이터 버스도착정보조회 API를 래핑한 MCP(Model Context Protocol) 서버 개발

## 기본 정보
- **Base URL**: `http://ws.bus.go.kr/api/rest/arrive`
- **인증**: 공공데이터포털(data.go.kr) 서비스키 필요
- **응답형식**: XML (기본) / JSON 지원
- **데이터 갱신주기**: 10초

---

## 구현할 API 목록

### 1. getArrInfoByRoute (핵심 - 우선 구현)
**용도**: 특정 정류소에서 특정 버스노선의 도착 정보 조회

**Endpoint**: `GET /getArrInfoByRoute`

**Request Parameters**:
| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|----------|------|------|------|------|
| serviceKey | string | Y | 인증키 | - |
| stId | string | Y | 정류소 고유 ID | "124000414" |
| busRouteId | string | Y | 노선 ID | "100100578" |
| ord | string | Y | 정류소 순번 (해당 노선에서 몇번째 정류소인지) | "29" |

**Response 주요 필드**:
| 필드 | 타입 | 설명 |
|------|------|------|
| arrmsg1 | string | 첫번째 버스 도착 메시지 (예: "10분1초후 [6번째 전]") |
| arrmsg2 | string | 두번째 버스 도착 메시지 |
| exps1 | int | 첫번째 버스 도착예정시간 (초 단위) |
| exps2 | int | 두번째 버스 도착예정시간 (초 단위) |
| rtNm | string | 노선명 (예: "3321") |
| stNm | string | 정류소명 |
| busType1 | string | 첫번째 버스 유형 (0:일반, 1:저상, 2:굴절) |
| busType2 | string | 두번째 버스 유형 |
| isArrive1 | string | 첫번째 버스 도착여부 (0:운행중, 1:도착) |
| isArrive2 | string | 두번째 버스 도착여부 |
| isLast1 | string | 첫번째 버스 막차여부 (0:막차아님, 1:막차) |
| isLast2 | string | 두번째 버스 막차여부 |
| firstTm | string | 첫차시간 (yyyyMMddHHmmss) |
| lastTm | string | 막차시간 (yyyyMMddHHmmss) |

---

### 2. getArrInfoByRouteAll
**용도**: 특정 노선의 전체 정류소 도착 정보 조회

**Endpoint**: `GET /getArrInfoByRouteAll`

**Request Parameters**:
| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|----------|------|------|------|------|
| serviceKey | string | Y | 인증키 | - |
| busRouteId | string | Y | 노선 ID | "100100118" |

**Response**: 위와 동일한 필드들이 정류소별로 리스트 반환

---

### 3. getLowArrInfoByStId
**용도**: 특정 정류소의 저상버스 도착 정보 조회 (교통약자용)

**Endpoint**: `GET /getLowArrInfoByStId`

**Request Parameters**:
| 파라미터 | 타입 | 필수 | 설명 | 예시 |
|----------|------|------|------|------|
| serviceKey | string | Y | 인증키 | - |
| stId | string | Y | 정류소 고유 ID | "124000414" |

---

### 4. getLowArrInfoByRoute
**용도**: 특정 정류소+노선의 저상버스 도착 정보 조회

**Endpoint**: `GET /getLowArrInfoByRoute`

**Request Parameters**: getArrInfoByRoute와 동일

---

## 에러 코드
| 코드 | 설명 |
|------|------|
| 0 | 정상 처리 |
| 1 | 시스템 오류 |
| 2 | 잘못된 쿼리 요청 (파라미터 확인 필요) |
| 3 | 정류소를 찾을 수 없음 |
| 4 | 노선을 찾을 수 없음 |
| 5 | 잘못된 위치 (위/경도 좌표 오류) |
| 6 | 실시간 정보 읽기 실패 (잠시 후 재시도) |
| 7 | 경로 검색 결과 없음 |
| 8 | 운행 종료 |

---

## MCP Tool 설계 제안

### Tool 1: `get_bus_arrival`
```json
{
  "name": "get_bus_arrival",
  "description": "특정 정류소에서 특정 버스의 도착 예정 시간을 조회합니다",
  "inputSchema": {
    "type": "object",
    "properties": {
      "stId": {
        "type": "string",
        "description": "정류소 고유 ID"
      },
      "busRouteId": {
        "type": "string",
        "description": "버스 노선 ID"
      },
      "ord": {
        "type": "string",
        "description": "정류소 순번"
      }
    },
    "required": ["stId", "busRouteId", "ord"]
  }
}
```

### Tool 2: `get_all_arrivals_by_route`
```json
{
  "name": "get_all_arrivals_by_route",
  "description": "특정 버스 노선의 전체 정류소 도착 정보를 조회합니다",
  "inputSchema": {
    "type": "object",
    "properties": {
      "busRouteId": {
        "type": "string",
        "description": "버스 노선 ID"
      }
    },
    "required": ["busRouteId"]
  }
}
```

### Tool 3: `get_low_floor_bus_arrival`
```json
{
  "name": "get_low_floor_bus_arrival",
  "description": "특정 정류소의 저상버스(교통약자용) 도착 정보를 조회합니다",
  "inputSchema": {
    "type": "object",
    "properties": {
      "stId": {
        "type": "string",
        "description": "정류소 고유 ID"
      }
    },
    "required": ["stId"]
  }
}
```

---

## 환경 변수
```
SEOUL_BUS_API_KEY=<공공데이터포털에서 발급받은 서비스키>
```

---

## 응답 XML 예시
```xml
<?xml version="1.0" encoding="UTF-8"?>
<ServiceResult>
  <msgHeader>
    <headerCd>0</headerCd>
    <headerMsg>정상적으로 처리되었습니다.</headerMsg>
    <itemCount>1</itemCount>
  </msgHeader>
  <msgBody>
    <itemList>
      <arrmsg1>10분1초후 [6번째 전]</arrmsg1>
      <arrmsg2>28분57초후 [14번째 전]</arrmsg2>
      <arsId>25361</arsId>
      <busRouteId>100100578</busRouteId>
      <busRouteAbrv>3321</busRouteAbrv>
      <rtNm>3321</rtNm>
      <stNm>강남역</stNm>
      <exps1>601</exps1>
      <exps2>1737</exps2>
      <busType1>1</busType1>
      <busType2>0</busType2>
      <isArrive1>0</isArrive1>
      <isArrive2>0</isArrive2>
      <isLast1>0</isLast1>
      <isLast2>0</isLast2>
      <firstTm>20230927050800</firstTm>
      <lastTm>20230928000800</lastTm>
    </itemList>
  </msgBody>
</ServiceResult>
```

---

## 참고사항
1. `ord` (정류소 순번)는 버스노선정보조회 API의 `getRoutePathList`로 조회 가능
2. 도착시간은 `exps1`, `exps2` 필드가 초 단위로 가장 정확함
3. `arrmsg1`, `arrmsg2`는 사람이 읽기 좋은 형태의 메시지
4. 첫번째 버스(`*1` 필드)와 두번째 버스(`*2` 필드)가 쌍으로 제공됨
5. 운행 종료 시 에러코드 8 반환
