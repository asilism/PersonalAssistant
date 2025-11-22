#!/usr/bin/env python3
"""
자동화된 프론트엔드 질문 테스트 스크립트
gpt-oss-20b 모델로 15개 질문을 테스트하고 결과를 검증합니다.
"""

import asyncio
import json
import sys
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import re


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
            "validation_details": {}
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

            # SSE 이벤트 수집
            events = []
            full_response_text = ""

            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        try:
                            event_data = json.loads(line_str[6:])
                            events.append(event_data)

                            # 이벤트 타입별 출력
                            event_type = event_data.get('type', '')

                            if event_type == 'plan_created':
                                print(f"{Colors.OKBLUE}  📋 실행 계획 생성됨{Colors.ENDC}")
                            elif event_type == 'step_started':
                                step_desc = event_data.get('data', {}).get('step_description', '')
                                print(f"{Colors.OKBLUE}  ▶ 단계 시작: {step_desc}{Colors.ENDC}")
                            elif event_type == 'step_completed':
                                step_desc = event_data.get('data', {}).get('step_description', '')
                                print(f"{Colors.OKGREEN}  ✓ 단계 완료: {step_desc}{Colors.ENDC}")
                            elif event_type == 'step_failed':
                                error = event_data.get('data', {}).get('error', '')
                                print(f"{Colors.FAIL}  ✗ 단계 실패: {error}{Colors.ENDC}")
                            elif event_type == 'execution_completed':
                                print(f"{Colors.OKGREEN}  ✓ 전체 실행 완료{Colors.ENDC}")
                                final_result = event_data.get('data', {}).get('final_result', '')
                                full_response_text = final_result
                            elif event_type == 'execution_error':
                                error = event_data.get('data', {}).get('error', '')
                                print(f"{Colors.FAIL}  ✗ 실행 오류: {error}{Colors.ENDC}")

                        except json.JSONDecodeError:
                            pass

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            result["events"] = events
            result["execution_time"] = execution_time
            result["full_response"] = full_response_text

            # 결과 검증
            validation_result = self.validate_result(question_data, events, full_response_text)
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

    def validate_result(self, question_data: Dict, events: List[Dict], response_text: str) -> Dict:
        """결과 검증"""
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
            "response_length": len(response_text)
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

        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    def save_results(self) -> None:
        """결과를 JSON 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_results_{timestamp}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "model": self.model,
                "provider": self.provider,
                "total": len(self.results),
                "success": sum(1 for r in self.results if r["success"]),
                "fail": sum(1 for r in self.results if not r["success"]),
                "results": self.results
            }, f, ensure_ascii=False, indent=2)

        print(f"{Colors.OKGREEN}결과 저장됨: {output_file}{Colors.ENDC}")


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
