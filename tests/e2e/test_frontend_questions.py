#!/usr/bin/env python3
"""
자동화된 프론트엔드 질문 테스트 스크립트
gpt-oss-20b 모델로 15개 질문을 테스트하고 Claude API로 검증합니다.
"""

import asyncio
import json
import sys
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import re
import os
from anthropic import Anthropic


class Colors:
    """터미널 컬러 출력"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class QuestionTester:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = "openai/gpt-oss-20b"
        self.provider = "openrouter"
        self.results = []

        # Claude API 초기화 (검증용)
        self.validator_client = None
        self.validator_model = None
        self._init_validator()

    def _init_validator(self):
        """Claude API 검증 클라이언트 초기화"""
        try:
            # .env.validator 파일 로드
            env_file = Path(__file__).parent.parent.parent / ".env.validator"
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                if key == 'CLAUDE_API_KEY':
                                    claude_key = value
                                elif key == 'CLAUDE_MODEL':
                                    self.validator_model = value

                if claude_key and self.validator_model:
                    self.validator_client = Anthropic(api_key=claude_key)
                    print(f"{Colors.OKGREEN}✓ Claude 검증 시스템 초기화 완료{Colors.ENDC}")
                    print(f"  - 검증 모델: {self.validator_model}")
            else:
                print(f"{Colors.WARNING}⚠ .env.validator 파일이 없습니다. 규칙 기반 검증만 사용됩니다.{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.WARNING}⚠ Claude 검증 초기화 실패: {str(e)}{Colors.ENDC}")
            print(f"{Colors.WARNING}  규칙 기반 검증만 사용됩니다.{Colors.ENDC}")

    def setup_llm_config(self) -> bool:
        """LLM 설정을 저장하고 활성화"""
        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
        print(f"{Colors.HEADER}1단계: LLM 설정 저장 중...{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

        config_data = {
            "config_name": "gpt-oss-20b-test",
            "provider": self.provider,
            "api_key": self.api_key,
            "model": self.model,
            "base_url": None,
            "max_retries": 3,
            "timeout": 60000,
            "is_active": True,
            "user_id": "test_user",
            "tenant": "test_tenant"
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/settings",
                json=config_data,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                print(f"{Colors.OKGREEN}✓ LLM 설정 저장 성공{Colors.ENDC}")
                print(f"  - Provider: {self.provider}")
                print(f"  - Model: {self.model}")
                return True
            else:
                print(f"{Colors.FAIL}✗ LLM 설정 저장 실패: {result.get('message')}{Colors.ENDC}")
                return False

        except Exception as e:
            print(f"{Colors.FAIL}✗ LLM 설정 중 오류: {str(e)}{Colors.ENDC}")
            return False

    def run_single_question(self, question_data: Dict) -> Dict:
        """단일 질문 실행 및 결과 수집"""
        question_id = question_data["id"]
        question = question_data["question"]
        category = question_data["category"]

        print(f"\n{Colors.OKCYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
        print(f"{Colors.BOLD}질문 #{question_id} [{category}]{Colors.ENDC}")
        print(f"{Colors.OKCYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
        print(f"📝 {question}")

        request_data = {
            "request_text": question,
            "user_id": "test_user",
            "tenant": "test_tenant",
            "session_id": f"test_session_{question_id}"
        }

        result = {
            "question_id": question_id,
            "question": question,
            "category": category,
            "success": False,
            "events": [],
            "error": None,
            "execution_time": 0,
            "validation_details": {},
            "detailed_logs": {
                "planning": [],
                "execution_steps": [],
                "tool_calls": [],
                "final_response": ""
            }
        }

        start_time = datetime.now()

        try:
            # SSE 스트리밍 요청
            response = requests.post(
                f"{self.base_url}/api/orchestrate/stream",
                json=request_data,
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            # SSE 이벤트 수집 및 상세 로그 추출
            events = []
            full_response_text = ""
            detailed_logs = {
                "planning": [],
                "execution_steps": [],
                "tool_calls": [],
                "final_response": ""
            }

            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        try:
                            event_data = json.loads(line_str[6:])
                            events.append(event_data)

                            # 이벤트 타입별 처리 및 로그 수집
                            event_type = event_data.get('type', '')
                            event_payload = event_data.get('data', {})

                            if event_type == 'plan_created':
                                print(f"{Colors.OKBLUE}  📋 실행 계획 생성됨{Colors.ENDC}")
                                # Planning 로그 수집
                                plan = event_payload.get('plan', {})
                                detailed_logs['planning'].append({
                                    'plan': plan,
                                    'timestamp': event_payload.get('timestamp', '')
                                })

                            elif event_type == 'step_started':
                                step_desc = event_payload.get('step_description', '')
                                step_num = event_payload.get('step_number', 0)
                                print(f"{Colors.OKBLUE}  ▶ 단계 {step_num}: {step_desc}{Colors.ENDC}")
                                detailed_logs['execution_steps'].append({
                                    'step_number': step_num,
                                    'description': step_desc,
                                    'status': 'started',
                                    'timestamp': event_payload.get('timestamp', '')
                                })

                            elif event_type == 'tool_execution':
                                tool_name = event_payload.get('tool_name', '')
                                tool_input = event_payload.get('tool_input', {})
                                tool_output = event_payload.get('tool_output', '')
                                print(f"{Colors.OKBLUE}  🔧 도구 실행: {tool_name}{Colors.ENDC}")
                                # Tool call 로그 수집
                                detailed_logs['tool_calls'].append({
                                    'tool_name': tool_name,
                                    'input': tool_input,
                                    'output': tool_output,
                                    'timestamp': event_payload.get('timestamp', '')
                                })

                            elif event_type == 'step_completed':
                                step_desc = event_payload.get('step_description', '')
                                step_num = event_payload.get('step_number', 0)
                                step_result = event_payload.get('result', '')
                                print(f"{Colors.OKGREEN}  ✓ 단계 {step_num} 완료: {step_desc}{Colors.ENDC}")
                                # 실행 단계 업데이트
                                for step in detailed_logs['execution_steps']:
                                    if step.get('step_number') == step_num:
                                        step['status'] = 'completed'
                                        step['result'] = step_result
                                        break

                            elif event_type == 'step_failed':
                                error = event_payload.get('error', '')
                                step_num = event_payload.get('step_number', 0)
                                print(f"{Colors.FAIL}  ✗ 단계 {step_num} 실패: {error}{Colors.ENDC}")
                                for step in detailed_logs['execution_steps']:
                                    if step.get('step_number') == step_num:
                                        step['status'] = 'failed'
                                        step['error'] = error
                                        break

                            elif event_type == 'execution_completed':
                                print(f"{Colors.OKGREEN}  ✓ 전체 실행 완료{Colors.ENDC}")
                                final_result = event_payload.get('final_result', '')
                                full_response_text = final_result
                                detailed_logs['final_response'] = final_result

                            elif event_type == 'execution_error':
                                error = event_payload.get('error', '')
                                print(f"{Colors.FAIL}  ✗ 실행 오류: {error}{Colors.ENDC}")

                        except json.JSONDecodeError:
                            pass

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            result["events"] = events
            result["execution_time"] = execution_time
            result["full_response"] = full_response_text
            result["detailed_logs"] = detailed_logs

            # 결과 검증 (LLM 기반 또는 규칙 기반)
            validation_result = self.validate_result(question_data, events, full_response_text, detailed_logs)
            result["success"] = validation_result["success"]
            result["validation_details"] = validation_result

            if validation_result["success"]:
                print(f"\n{Colors.OKGREEN}✓ 검증 성공{Colors.ENDC}")
                for reason in validation_result.get("reasons", []):
                    print(f"  {Colors.OKGREEN}• {reason}{Colors.ENDC}")
            else:
                print(f"\n{Colors.FAIL}✗ 검증 실패{Colors.ENDC}")
                for reason in validation_result.get("reasons", []):
                    print(f"  {Colors.FAIL}• {reason}{Colors.ENDC}")

            print(f"\n⏱️  실행 시간: {execution_time:.2f}초")

        except requests.exceptions.Timeout:
            result["error"] = "타임아웃 (120초 초과)"
            print(f"{Colors.FAIL}✗ 타임아웃 발생{Colors.ENDC}")
        except Exception as e:
            result["error"] = str(e)
            print(f"{Colors.FAIL}✗ 오류 발생: {str(e)}{Colors.ENDC}")

        return result

    def validate_with_llm(self, question: str, detailed_logs: Dict, success_criteria: Dict) -> Dict:
        """Claude API를 사용한 LLM 기반 검증"""
        if not self.validator_client:
            return None

        try:
            # 상세 로그를 구조화된 텍스트로 변환
            logs_summary = self._format_logs_for_validation(detailed_logs)

            validation_prompt = f"""다음 질문에 대한 실행 결과를 분석하고 성공 여부를 판단해주세요.

## 질문
{question}

## 성공 기준
{json.dumps(success_criteria, ensure_ascii=False, indent=2)}

## 실행 로그

### 1. 계획 (Planning)
{json.dumps(detailed_logs.get('planning', []), ensure_ascii=False, indent=2)}

### 2. 실행 단계 (Execution Steps)
{json.dumps(detailed_logs.get('execution_steps', []), ensure_ascii=False, indent=2)}

### 3. 도구 호출 (Tool Calls)
{json.dumps(detailed_logs.get('tool_calls', []), ensure_ascii=False, indent=2)}

### 4. 최종 응답
{detailed_logs.get('final_response', '')}

---

## 분석 요청

위 실행 로그를 분석하여 다음 질문에 답변해주세요:

1. **질문의 의도가 성공적으로 수행되었나요?**
   - YES 또는 NO로 답변

2. **판단 근거는 무엇인가요?**
   - 구체적인 이유를 3-5개의 bullet point로 설명

3. **발견된 문제가 있다면?**
   - 실패했다면 어떤 문제가 있었는지 상세히 설명

응답은 다음 JSON 형식으로 제공해주세요:

```json
{{
  "success": true 또는 false,
  "confidence": 0.0~1.0 (확신도),
  "reasons": [
    "이유 1",
    "이유 2",
    "이유 3"
  ],
  "problems": [
    "문제점 1 (있다면)",
    "문제점 2 (있다면)"
  ]
}}
```"""

            response = self.validator_client.messages.create(
                model=self.validator_model,
                max_tokens=2000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": validation_prompt
                }]
            )

            # 응답에서 JSON 추출
            response_text = response.content[0].text

            # JSON 블록 찾기
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # JSON 블록이 없으면 전체 텍스트에서 파싱 시도
                json_str = response_text

            validation_result = json.loads(json_str)
            validation_result['method'] = 'llm'
            validation_result['raw_response'] = response_text

            return validation_result

        except Exception as e:
            print(f"{Colors.WARNING}⚠ LLM 검증 실패: {str(e)}{Colors.ENDC}")
            return None

    def _format_logs_for_validation(self, detailed_logs: Dict) -> str:
        """상세 로그를 검증용 텍스트로 포맷팅"""
        sections = []

        if detailed_logs.get('planning'):
            sections.append("Planning:\n" + json.dumps(detailed_logs['planning'], indent=2))

        if detailed_logs.get('execution_steps'):
            sections.append("Execution Steps:\n" + json.dumps(detailed_logs['execution_steps'], indent=2))

        if detailed_logs.get('tool_calls'):
            sections.append("Tool Calls:\n" + json.dumps(detailed_logs['tool_calls'], indent=2))

        if detailed_logs.get('final_response'):
            sections.append(f"Final Response:\n{detailed_logs['final_response']}")

        return "\n\n".join(sections)

    def validate_result(self, question_data: Dict, events: List[Dict], response_text: str, detailed_logs: Dict) -> Dict:
        """결과 검증 - LLM 우선, 실패시 규칙 기반"""
        success_criteria = question_data.get("success_criteria", {})

        # 1. LLM 기반 검증 시도
        llm_result = self.validate_with_llm(
            question_data["question"],
            detailed_logs,
            success_criteria
        )

        if llm_result:
            print(f"{Colors.OKCYAN}  🤖 LLM 검증 사용 (확신도: {llm_result.get('confidence', 0):.2%}){Colors.ENDC}")
            return llm_result

        # 2. LLM 실패시 규칙 기반 검증
        print(f"{Colors.WARNING}  📏 규칙 기반 검증 사용{Colors.ENDC}")
        return self.validate_with_rules(question_data, events, response_text)

    def validate_with_rules(self, question_data: Dict, events: List[Dict], response_text: str) -> Dict:
        """규칙 기반 검증 (Fallback)"""
        success_criteria = question_data.get("success_criteria", {})
        criteria_type = success_criteria.get("type", "")
        keywords = success_criteria.get("keywords", [])
        expected_result = success_criteria.get("expected_result", None)

        reasons = []
        success = True

        # 1. 실행 완료 확인
        execution_completed = any(e.get("type") == "execution_completed" for e in events)
        if not execution_completed:
            success = False
            reasons.append("실행이 완료되지 않음 (execution_completed 이벤트 없음)")
        else:
            reasons.append("실행 완료됨")

        # 2. 실행 오류 확인
        execution_errors = [e for e in events if e.get("type") == "execution_error"]
        if execution_errors:
            success = False
            for error_event in execution_errors:
                error_msg = error_event.get("data", {}).get("error", "")
                reasons.append(f"실행 오류: {error_msg}")

        # 3. 단계 실패 확인
        failed_steps = [e for e in events if e.get("type") == "step_failed"]
        if failed_steps:
            success = False
            for failed_step in failed_steps:
                error_msg = failed_step.get("data", {}).get("error", "")
                reasons.append(f"단계 실패: {error_msg}")

        # 4. 키워드 검증 (대소문자 무시)
        response_lower = response_text.lower()
        if keywords:
            matched_keywords = []
            missing_keywords = []

            for keyword in keywords:
                if keyword.lower() in response_lower:
                    matched_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)

            if missing_keywords:
                success = False
                reasons.append(f"누락된 키워드: {', '.join(missing_keywords)}")
            else:
                reasons.append(f"모든 키워드 발견: {', '.join(matched_keywords)}")

        # 5. 계산 결과 검증 (숫자 타입인 경우)
        if expected_result and criteria_type == "calculation":
            if expected_result in response_text:
                reasons.append(f"계산 결과 일치: {expected_result}")
            else:
                # 숫자만 추출해서 확인
                numbers = re.findall(r'\d+', response_text)
                if expected_result in numbers:
                    reasons.append(f"계산 결과 일치: {expected_result}")
                else:
                    success = False
                    reasons.append(f"계산 결과 불일치 (예상: {expected_result}, 응답: {response_text[:100]})")

        # 6. 다중 에이전트 검증 (expected_result가 있는 경우)
        if expected_result and criteria_type == "multi":
            if expected_result in response_text:
                reasons.append(f"예상 결과 포함: {expected_result}")

        return {
            "success": success,
            "reasons": reasons,
            "matched_events": len(events),
            "response_length": len(response_text),
            "method": "rules"
        }

    def run_all_tests(self, questions_file: str) -> None:
        """모든 질문 테스트 실행"""
        # 질문 로드
        with open(questions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        questions = data["questions"]

        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}프론트엔드 질문 자동 테스트 시작{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
        print(f"\n총 {len(questions)}개 질문 테스트 예정")
        print(f"모델: {self.model}")
        print(f"Provider: {self.provider}")
        if self.validator_client:
            print(f"검증: LLM 기반 (Claude {self.validator_model})")
        else:
            print(f"검증: 규칙 기반")

        # LLM 설정
        if not self.setup_llm_config():
            print(f"\n{Colors.FAIL}LLM 설정 실패. 테스트를 중단합니다.{Colors.ENDC}")
            sys.exit(1)

        # 각 질문 실행
        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
        print(f"{Colors.HEADER}2단계: 질문 실행 및 검증{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}")

        for question_data in questions:
            result = self.run_single_question(question_data)
            self.results.append(result)

        # 결과 리포트 출력
        self.print_report()

        # 결과 JSON 저장
        self.save_results()

    def print_report(self) -> None:
        """테스트 결과 리포트 출력"""
        total = len(self.results)
        success_count = sum(1 for r in self.results if r["success"])
        fail_count = total - success_count
        success_rate = (success_count / total * 100) if total > 0 else 0

        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}최종 테스트 결과{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

        print(f"총 질문 수: {total}")
        print(f"{Colors.OKGREEN}✓ 성공: {success_count}{Colors.ENDC}")
        print(f"{Colors.FAIL}✗ 실패: {fail_count}{Colors.ENDC}")
        print(f"성공률: {success_rate:.1f}%")

        # 검증 방법 통계
        llm_count = sum(1 for r in self.results if r.get("validation_details", {}).get("method") == "llm")
        rules_count = sum(1 for r in self.results if r.get("validation_details", {}).get("method") == "rules")
        print(f"\n검증 방법:")
        print(f"  🤖 LLM 기반: {llm_count}건")
        print(f"  📏 규칙 기반: {rules_count}건")

        # 카테고리별 통계
        categories = {}
        for result in self.results:
            category = result["category"]
            if category not in categories:
                categories[category] = {"total": 0, "success": 0}
            categories[category]["total"] += 1
            if result["success"]:
                categories[category]["success"] += 1

        print(f"\n{Colors.BOLD}카테고리별 성공률:{Colors.ENDC}")
        for category, stats in categories.items():
            rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            color = Colors.OKGREEN if rate == 100 else Colors.WARNING if rate >= 50 else Colors.FAIL
            print(f"  {color}{category}: {stats['success']}/{stats['total']} ({rate:.1f}%){Colors.ENDC}")

        # 실패한 질문 상세 정보
        if fail_count > 0:
            print(f"\n{Colors.FAIL}{Colors.BOLD}실패한 질문 상세:{Colors.ENDC}")
            for result in self.results:
                if not result["success"]:
                    print(f"\n  {Colors.FAIL}✗ 질문 #{result['question_id']} [{result['category']}]{Colors.ENDC}")
                    print(f"    질문: {result['question']}")
                    if result.get("error"):
                        print(f"    오류: {result['error']}")
                    else:
                        validation = result.get("validation_details", {})
                        for reason in validation.get("reasons", []):
                            print(f"    - {reason}")
                        if validation.get("problems"):
                            print(f"    문제점:")
                            for problem in validation["problems"]:
                                print(f"      • {problem}")

        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    def save_results(self) -> None:
        """결과를 JSON 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_results_{timestamp}.json"

        # 전체 결과 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "model": self.model,
                "provider": self.provider,
                "validator": "llm" if self.validator_client else "rules",
                "total": len(self.results),
                "success": sum(1 for r in self.results if r["success"]),
                "fail": sum(1 for r in self.results if not r["success"]),
                "results": self.results
            }, f, ensure_ascii=False, indent=2)

        print(f"{Colors.OKGREEN}전체 결과 저장됨: {output_file}{Colors.ENDC}")

        # 실패한 케이스만 별도 저장
        failed_results = [r for r in self.results if not r["success"]]
        if failed_results:
            failures_file = f"failures_{timestamp}.json"

            with open(failures_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": timestamp,
                    "model": self.model,
                    "provider": self.provider,
                    "validator": "llm" if self.validator_client else "rules",
                    "total_failures": len(failed_results),
                    "instructions": "이 파일을 Claude에게 제공하여 문제를 분석하고 수정하세요.",
                    "failures": failed_results
                }, f, ensure_ascii=False, indent=2)

            print(f"{Colors.WARNING}실패 케이스 저장됨: {failures_file}{Colors.ENDC}")
            print(f"{Colors.WARNING}👉 이 파일을 Claude에게 제공하여 문제를 수정하세요!{Colors.ENDC}")


def main():
    parser = argparse.ArgumentParser(description='프론트엔드 질문 자동 테스트')
    parser.add_argument('--api-key', type=str, help='OpenRouter API 키')
    parser.add_argument('--base-url', type=str, default='http://localhost:8000',
                        help='API 서버 URL (기본값: http://localhost:8000)')
    parser.add_argument('--questions-file', type=str,
                        default='tests/e2e/frontend_questions.json',
                        help='질문 JSON 파일 경로')

    args = parser.parse_args()

    # API 키 입력 (인자가 없으면 대화형으로 입력)
    api_key = args.api_key
    if not api_key:
        print(f"\n{Colors.BOLD}OpenRouter API 키를 입력하세요:{Colors.ENDC}")
        api_key = input("> ").strip()
        if not api_key:
            print(f"{Colors.FAIL}API 키가 필요합니다.{Colors.ENDC}")
            sys.exit(1)

    # 질문 파일 존재 확인
    if not Path(args.questions_file).exists():
        print(f"{Colors.FAIL}질문 파일을 찾을 수 없습니다: {args.questions_file}{Colors.ENDC}")
        sys.exit(1)

    # 테스트 실행
    tester = QuestionTester(api_key=api_key, base_url=args.base_url)
    tester.run_all_tests(args.questions_file)


if __name__ == "__main__":
    main()
