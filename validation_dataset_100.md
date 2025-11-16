# Personal Assistant 검증용 데이터셋 (100개)

본 문서는 Personal Assistant 시스템 검증을 위한 100개의 테스트 질문을 포함합니다.

## 구성
- **단일 Agent 호출 (Single Agent)**: 25건 (1-25번)
- **복수 Agent 호출 (Multi Agent)**: 25건 (26-50번)
- **RPA 포함 호출 (With RPA)**: 50건 (51-100번)

---

## 단일 Agent 호출 (Single Agent) - 25건

### Calculator Agent (1-5)
1. (20/4) + 3 은 얼마야?
2. 123 곱하기 456을 계산해줘
3. 2의 10승은 얼마인지 알려줘
4. 9876에서 1234를 뺀 값을 계산해줘
5. 789를 3으로 나눈 값은?

### Mail Agent (6-10)
6. jiho@samsung.com에게 "See you at 2 PM"이라는 내용으로 이메일 보내줘
7. 안 읽은 이메일 5개만 보여줘
8. sungjun87.lee@samsung.com에서 온 이메일 검색해줘
9. "Project Review"라는 제목의 이메일을 찾아줘
10. 최근 이메일 10개 보여줘

### Calendar Agent (11-15)
11. 내일 오전 10시부터 11시까지 "Team Meeting" 일정 만들어줘
12. 11월 18일에 무슨 일정이 있는지 확인해줘
13. 11월 11일에 있는 일정 삭제해줘
14. 이번 주 모든 일정을 보여줘
15. "Sprint Planning" 일정을 11월 20일 오후 2시로 변경해줘

### Jira Agent (16-20)
16. "Implement user authentication"라는 제목으로 Jira 이슈 만들어줘
17. PROJ-1 이슈의 상세 정보를 보여줘
18. 상태가 "TO DO"인 Jira 이슈들을 찾아줘
19. PROJ-3 이슈를 "Done" 상태로 변경해줘
20. "Bug fix"라는 설명이 포함된 이슈를 검색해줘

### Contact Agent (21-25)
21. 김민지의 이메일 주소를 찾아줘
22. Engineering 부서의 모든 연락처를 보여줘
23. "Haneul"이 포함된 연락처를 검색해줘
24. 이하늘의 전화번호를 알려줘
25. 모든 연락처 목록을 보여줘

---

## 복수 Agent 호출 (Multi Agent) - 25건

### Calculator + Mail (26-28)
26. (150 + 250) / 2를 계산하고, 결과를 jiho@samsung.com에게 이메일로 보내줘
27. 1000 곱하기 1.15를 계산한 다음, 그 결과를 minji@samsung.com에게 "Budget calculation result"라는 제목으로 이메일 보내줘
28. 2의 8승을 계산해서 haneul@samsung.com에게 전송해줘

### Contact + Mail (29-33)
29. 김민지에게 "Meeting reminder for tomorrow"라는 이메일 보내줘
30. 이하늘에게 "Project update"라는 제목으로 "Please review the latest changes"라는 내용의 이메일 전송해줘
31. 박지수에게 "Sprint retrospective at 3 PM"이라는 내용 이메일 보내줘
32. 최수빈에게 "Weekly report is ready"라는 이메일 보내줘
33. 정지호에게 "Server maintenance scheduled for tonight"라는 이메일 보내줘

### Calendar + Contact + Mail (34-38)
34. 내일 오전 10시부터 11시까지 "Sprint Planning" 일정을 만들고, 김민지에게 안건을 이메일로 보내줘
35. 11월 20일 오후 2시부터 3시까지 "Design Review" 회의를 만들고, 이하늘에게 회의 초대 이메일 보내줘
36. 내일 오전 9시 "Team Standup" 일정 만들고, 박지수에게 안건 이메일 보내줘
37. 11월 22일 오후 4시 "Q4 Planning" 회의 만들고, 최수빈에게 준비사항 이메일 보내줘
38. 11월 25일 오전 11시 "Client Meeting" 일정 만들고, 정지호에게 자료 준비 요청 이메일 보내줘

### Jira + Mail (39-43)
39. "Fix login bug"라는 Jira 이슈를 만들고, haneul@samsung.com에게 알림 이메일 보내줘
40. PROJ-1 이슈 정보를 조회해서 minji@samsung.com에게 이메일로 보내줘
41. "Database optimization"이라는 Jira 이슈 만들고, jiho@samsung.com에게 할당 알림 보내줘
42. 상태가 "Done"인 이슈를 검색해서 soobin@samsung.com에게 완료 보고 이메일 보내줘
43. PROJ-5 이슈를 "In Progress"로 변경하고, jisu@samsung.com에게 진행 상황 이메일 보내줘

### Calendar + Jira (44-47)
44. 11월 19일에 일정이 있는지 확인하고, 일정이 있으면 "Meeting preparation"이라는 Jira 이슈를 만들어줘
45. "Code Review" 일정을 11월 21일 오후 3시에 만들고, "Prepare code review materials"라는 Jira 이슈도 생성해줘
46. 11월 18일 일정을 조회하고, 각 일정마다 준비 작업 Jira 이슈를 만들어줘
47. 내일 회의 일정을 만들고, 회의 안건을 정리하는 Jira 이슈도 생성해줘

### Contact + Calendar + Mail (48-50)
48. 김민지, 이하늘, 박지수의 이메일을 찾고, 11월 23일 오후 2시 "Product Demo" 일정을 만든 다음, 세 사람 모두에게 초대 이메일 보내줘
49. Engineering 부서 연락처를 조회하고, 내일 오전 10시 "Tech Talk" 일정을 만든 다음, 부서원 전체에게 공지 이메일 보내줘
50. 최수빈과 정지호의 연락처를 찾고, 11월 24일 오전 9시 "Leadership Sync" 일정 만들고, 두 사람에게 이메일 보내줘

---

## RPA 포함 호출 (With RPA) - 50건

### RPA - News Search + Report (51-60)
51. "AI"에 관한 최신 뉴스를 검색하고, 리포트를 작성해줘
52. "Samsung"에 관한 뉴스를 찾아서 요약 리포트 만들어줘
53. "Cloud Computing" 뉴스를 검색하고, HTML 형식 리포트 생성해줘
54. "Quantum Computing" 관련 뉴스를 찾아서 텍스트 리포트로 만들어줘
55. "Cybersecurity" 최신 뉴스 3개를 찾아서 마크다운 리포트 작성해줘
56. "5G Technology" 뉴스를 검색하고, "Tech Team"이 작성자인 리포트 만들어줘
57. "Startup Ecosystem" 관련 뉴스 5개를 찾아서 리포트 생성해줘
58. "Green Technology" 뉴스를 검색하고, HTML 리포트로 만들어줘
59. "Semiconductor" 산업 뉴스를 찾아서 상세 리포트 작성해줘
60. "Agile Methodology" 관련 최신 뉴스를 검색하고 리포트 만들어줘

### RPA - News + Mail (61-70)
61. "Samsung" 뉴스를 검색하고, 리포트를 작성한 다음, 김민지에게 이메일로 보내줘
62. "AI Technology" 최신 뉴스를 찾아서 리포트 만들고, haneul@samsung.com에게 전송해줘
63. "Cloud Computing" 뉴스 검색 후 리포트 작성하고, 이하늘에게 이메일 보내줘
64. "Cybersecurity" 관련 뉴스를 찾고, 리포트를 만든 다음, 박지수에게 이메일로 보내줘
65. "5G Network" 뉴스 검색 후 HTML 리포트 만들어서 최수빈에게 전송해줘
66. "Quantum Computing" 뉴스를 찾아 리포트 작성하고, jiho@samsung.com에게 이메일 보내줘
67. "Startup Investment" 관련 뉴스 검색 후 리포트 만들어서 정지호에게 보내줘
68. "Green Energy" 최신 뉴스 찾아서 리포트 작성하고, minji@samsung.com에게 전송해줘
69. "Semiconductor Supply" 뉴스 검색 후 리포트를 만들고, soobin@samsung.com에게 이메일 보내줘
70. "Jira Automation" 관련 뉴스를 찾아 리포트 작성해서 jisu@samsung.com에게 전송해줘

### RPA - Attendance Collection (71-75)
71. "Product Launch Dinner" 행사에 minji@samsung.com, haneul@samsung.com, jisu@samsung.com의 참석 여부를 수집하고, 요약을 soobin@samsung.com에게 보내줘
72. "Team Building Event"에 대해 jiho@samsung.com은 참석, seojun@samsung.com은 불참으로 기록하고, 출석 요약 보고서 만들어줘
73. "Q4 Review Meeting"에 대한 출석 정보를 수집하고, 김민지에게 요약 이메일 보내줘
74. "Sprint Retrospective"에 참석 예정인 사람들을 기록하고, 출석률을 계산해서 리포트 만들어줘
75. "Weekend Workshop"의 참석자 데이터를 수집하고, haneul@samsung.com에게 요약 전송해줘

### RPA - News + Report + Mail (Multi-step) (76-85)
76. "Samsung Electronics" 뉴스를 검색하고, 3개 섹션으로 리포트 작성한 다음, 김민지와 이하늘에게 이메일 보내줘
77. "AI Breakthrough" 관련 뉴스 5개를 찾고, 상세 리포트를 HTML로 만든 후, Engineering 부서 전체에게 이메일 보내줘
78. "Cloud Technology" 최신 뉴스를 검색해서 요약 리포트 만들고, 최수빈과 정지호에게 전송해줘
79. "Cybersecurity Threats" 뉴스를 찾아서 보안 리포트 작성하고, seohyun@samsung.com에게 우선 전송해줘
80. "5G Deployment" 관련 뉴스 검색 후 마크다운 리포트 만들어서 minji@samsung.com, jiho@samsung.com에게 보내줘
81. "Quantum Research" 뉴스를 찾고, 기술 리포트 작성한 다음, jimin@samsung.com에게 이메일로 전송해줘
82. "Green Technology Investment" 뉴스 검색 후 투자 리포트 만들어서 soobin@samsung.com에게 보내줘
83. "Semiconductor Innovation" 관련 뉴스를 찾아 산업 리포트 작성하고, haneul@samsung.com, jisu@samsung.com에게 전송해줘
84. "Startup Funding" 최신 뉴스 검색해서 시장 분석 리포트 만들고, 박지수에게 이메일 보내줘
85. "Agile Transformation" 뉴스를 찾아 프로젝트 관리 리포트 작성하고, hayoon@samsung.com에게 전송해줘

### RPA + Jira (86-90)
86. "TO DO" 상태의 모든 Jira 이슈를 검색하고, 요약 리포트를 작성한 다음, haneul@samsung.com에게 이메일로 보내줘
87. Jira에서 완료된 이슈들을 조회하고, 주간 완료 리포트를 만들어서 soobin@samsung.com에게 전송해줘
88. "Bug"가 포함된 Jira 이슈를 검색하고, 버그 리포트 작성해서 김민지에게 보내줘
89. "In Progress" 상태의 이슈들을 찾아서 진행 상황 리포트 만들고, 최수빈에게 이메일 보내줬어
90. Jira에서 우선순위가 높은 이슈를 조회하고, 우선순위 리포트 작성해서 이하늘에게 전송해줘

### RPA + Calendar + Mail (91-95)
91. 11월 18일의 모든 일정을 조회하고, 일정 요약 리포트를 작성해서 jiho@samsung.com에게 보내줘
92. 이번 주 회의 일정을 확인하고, 주간 회의 일정표를 만들어서 김민지에게 이메일 전송해줘
93. 내일 일정을 조회해서 일일 스케줄 리포트 작성하고, minji@samsung.com에게 보내줘
94. 11월 20일부터 25일까지 일정을 확인하고, 주간 플래너 리포트 만들어서 soobin@samsung.com에게 전송해줘
95. "Client Meeting" 관련 일정을 찾아서 고객 미팅 준비 리포트 작성하고, 정지호에게 이메일 보내줘

### Complex Multi-Agent + RPA (96-100)
96. "Samsung" 뉴스를 검색하고, 리포트를 작성한 다음, "News Summary" Jira 이슈를 만들고, 김민지에게 이메일 보내줘
97. "AI Technology" 뉴스를 찾아 리포트 만들고, 내일 오전 10시 "AI Discussion" 일정을 생성한 후, 이하늘과 박지수에게 이메일 보내줘
98. "Cybersecurity" 뉴스 검색, 보안 리포트 작성, "Security Review" 이슈 생성, 그리고 seohyun@samsung.com에게 이메일 전송해줘
99. "Product Launch Dinner" 행사의 참석 정보를 minji@samsung.com, haneul@samsung.com, jisu@samsung.com에게서 수집하고, 요약 리포트를 작성해서 soobin@samsung.com에게 보내줘
100. "TO DO" 상태의 Jira 이슈를 모두 검색하고, 작업 현황 리포트를 생성한 다음, 11월 21일 오후 3시 "Sprint Planning" 회의 일정을 만들고, haneul@samsung.com에게 리포트와 회의 안건을 이메일로 보내줘

---

## 참고사항

### 사용 가능한 MCP Tools

#### Calculator Agent
- add, subtract, multiply, divide, power

#### Mail Agent
- send_email, read_emails, get_email, delete_email, search_emails

#### Calendar Agent
- create_event, read_event, update_event, delete_event, list_events

#### Jira Agent
- create_issue, read_issue, update_issue, delete_issue, search_issues

#### Contact Agent (NEW)
- search_contacts, get_contact_by_name, get_contact_email, list_all_contacts

#### RPA Agent
- search_latest_news, write_report, collect_attendance

### 주요 연락처 (Contact Database)

- **김민지 (Minji Kim)**: minji@samsung.com - Product Manager
- **이하늘 (Haneul Lee)**: haneul@samsung.com - Senior Software Engineer
- **박지수 (Jisu Park)**: jisu@samsung.com - Software Engineer
- **최수빈 (Soobin Choi)**: soobin@samsung.com - Team Lead
- **정지호 (Jiho Jung)**: jiho@samsung.com - DevOps Engineer
- **이성준 (Sungjun Lee)**: sungjun87.lee@samsung.com - Engineering Manager
- **박민호 (Minho Park)**: minho.park@samsung.com - Senior Software Engineer
- **최소연 (Soyeon Choi)**: soyeon.choi@samsung.com - Senior UX Designer
- **김재현 (Jaehyun Kim)**: jaehyun.kim@samsung.com - Software Engineer
- **안서현 (Seohyun Ahn)**: seohyun@samsung.com - Security Engineer
- **한지민 (Jimin Han)**: jimin@samsung.com - Data Scientist
- **송하윤 (Hayoon Song)**: hayoon@samsung.com - Backend Developer
- **조은우 (Eunwoo Jo)**: eunwoo@samsung.com - Frontend Developer

### 테스트 시나리오

각 질문은 다음을 검증합니다:
1. **단일 Agent**: 개별 Agent의 기본 기능 동작
2. **복수 Agent**: 여러 Agent 간의 데이터 전달 및 조율
3. **RPA 포함**: RPA 자동화 기능과 다른 Agent들의 통합 작업

### Contact Lookup 기능 활용

- 이름만 제공된 경우 자동으로 contact lookup 수행
- 한국어 이름과 영어 이름 모두 지원
- 부서별 연락처 조회 가능
- 이메일 주소 자동 검색 및 치환

---

**생성일**: 2025-11-16
**버전**: 1.0
**목적**: Personal Assistant 시스템 검증 및 테스트
