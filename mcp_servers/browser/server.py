#!/usr/bin/env python3
"""
Browser/Web MCP Server

웹 브라우저를 조작하여 인터넷 정보를 수집하는 MCP 서버입니다.
- 구글 검색
- 웹 페이지 스크래핑
- URL에서 콘텐츠 추출
- 스크린샷 캡처
"""

import asyncio
import os
import re
import json
import base64
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastmcp import FastMCP

# Playwright는 선택적으로 사용 (설치된 경우에만)
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

mcp = FastMCP("browser")

# User-Agent 설정
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 전역 브라우저 인스턴스 (Playwright용)
_browser: Optional[Any] = None
_playwright: Optional[Any] = None


async def get_browser():
    """Playwright 브라우저 인스턴스 가져오기"""
    global _browser, _playwright

    if not PLAYWRIGHT_AVAILABLE:
        return None

    if _browser is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)

    return _browser


async def close_browser():
    """브라우저 정리"""
    global _browser, _playwright

    if _browser:
        await _browser.close()
        _browser = None

    if _playwright:
        await _playwright.stop()
        _playwright = None


def clean_text(text: str) -> str:
    """텍스트에서 불필요한 공백 제거"""
    # 여러 공백을 하나로
    text = re.sub(r'\s+', ' ', text)
    # 앞뒤 공백 제거
    return text.strip()


def extract_main_content(soup: BeautifulSoup) -> str:
    """HTML에서 메인 콘텐츠 추출"""
    # 불필요한 요소 제거
    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe']):
        tag.decompose()

    # 메인 콘텐츠 영역 찾기
    main_content = None
    for selector in ['article', 'main', '[role="main"]', '.content', '#content', '.post', '.article']:
        main_content = soup.select_one(selector)
        if main_content:
            break

    if main_content:
        return clean_text(main_content.get_text())

    # body 전체 사용
    body = soup.find('body')
    if body:
        return clean_text(body.get_text())

    return clean_text(soup.get_text())


@mcp.tool()
async def google_search(
    query: str,
    num_results: int = 10,
    language: str = "ko"
) -> dict:
    """
    구글에서 검색을 수행합니다.

    Args:
        query: 검색어
        num_results: 반환할 결과 수 (기본: 10, 최대: 20)
        language: 검색 언어 코드 (기본: ko - 한국어)

    Returns:
        검색 결과 목록
    """
    try:
        num_results = min(num_results, 20)

        # 구글 검색 URL 구성
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results}&hl={language}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                search_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": f"{language},en;q=0.5",
                }
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        results = []

        # 검색 결과 파싱 (구글의 검색 결과 구조)
        for g in soup.select('div.g'):
            # 제목과 링크
            title_elem = g.select_one('h3')
            link_elem = g.select_one('a')

            if not title_elem or not link_elem:
                continue

            title = title_elem.get_text(strip=True)
            link = link_elem.get('href', '')

            # 구글 내부 링크 제외
            if not link or link.startswith('/search') or 'google.com' in link:
                continue

            # 설명 추출
            snippet_elem = g.select_one('div[data-snf], div.VwiC3b, span.aCOpRe')
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            results.append({
                "title": title,
                "url": link,
                "snippet": snippet
            })

            if len(results) >= num_results:
                break

        return {
            "success": True,
            "data_type": "search_results",
            "query": query,
            "num_results": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP 오류: {str(e)}",
            "query": query
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"검색 실패: {str(e)}",
            "query": query
        }


@mcp.tool()
async def fetch_webpage(
    url: str,
    extract_text: bool = True,
    include_links: bool = False,
    include_images: bool = False
) -> dict:
    """
    웹 페이지 내용을 가져옵니다.

    Args:
        url: 가져올 웹 페이지 URL
        extract_text: 텍스트만 추출할지 여부 (기본: True)
        include_links: 페이지 내 링크 목록 포함 여부
        include_images: 페이지 내 이미지 목록 포함 여부

    Returns:
        웹 페이지 내용
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 페이지 제목
        title = soup.title.string if soup.title else ""

        # 메타 설명
        meta_desc = ""
        meta_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_tag:
            meta_desc = meta_tag.get('content', '')

        result = {
            "success": True,
            "url": str(response.url),
            "title": title,
            "meta_description": meta_desc,
            "status_code": response.status_code,
        }

        if extract_text:
            content = extract_main_content(soup)
            # 텍스트 길이 제한 (너무 길면 자름)
            if len(content) > 50000:
                content = content[:50000] + "... (truncated)"
            result["content"] = content
            result["content_length"] = len(content)
        else:
            result["html"] = response.text
            result["html_length"] = len(response.text)

        if include_links:
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)

                # 상대 URL을 절대 URL로 변환
                if href.startswith('/'):
                    href = urljoin(url, href)

                if href.startswith('http'):
                    links.append({"text": text, "url": href})

            result["links"] = links[:100]  # 최대 100개

        if include_images:
            images = []
            for img in soup.find_all('img', src=True):
                src = img['src']
                alt = img.get('alt', '')

                # 상대 URL을 절대 URL로 변환
                if src.startswith('/'):
                    src = urljoin(url, src)

                if src.startswith('http'):
                    images.append({"alt": alt, "url": src})

            result["images"] = images[:50]  # 최대 50개

        return result

    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP 오류: {str(e)}",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"페이지 가져오기 실패: {str(e)}",
            "url": url
        }


@mcp.tool()
async def extract_structured_data(
    url: str,
    selectors: Dict[str, str]
) -> dict:
    """
    CSS 셀렉터를 사용하여 웹 페이지에서 구조화된 데이터를 추출합니다.

    Args:
        url: 웹 페이지 URL
        selectors: 추출할 데이터의 CSS 셀렉터 딕셔너리
                   예: {"title": "h1.title", "price": "span.price", "description": "div.desc"}

    Returns:
        추출된 데이터
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        extracted = {}
        for key, selector in selectors.items():
            elements = soup.select(selector)
            if len(elements) == 1:
                extracted[key] = clean_text(elements[0].get_text())
            elif len(elements) > 1:
                extracted[key] = [clean_text(el.get_text()) for el in elements]
            else:
                extracted[key] = None

        return {
            "success": True,
            "url": url,
            "data": extracted
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


@mcp.tool()
async def take_screenshot(
    url: str,
    full_page: bool = False,
    width: int = 1920,
    height: int = 1080
) -> dict:
    """
    웹 페이지의 스크린샷을 캡처합니다. (Playwright 필요)

    Args:
        url: 스크린샷을 찍을 웹 페이지 URL
        full_page: 전체 페이지 스크린샷 여부 (기본: False - 뷰포트만)
        width: 뷰포트 너비 (기본: 1920)
        height: 뷰포트 높이 (기본: 1080)

    Returns:
        Base64 인코딩된 스크린샷 이미지
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "error": "Playwright가 설치되지 않았습니다. 'pip install playwright && playwright install chromium'을 실행하세요."
        }

    try:
        browser = await get_browser()
        page = await browser.new_page(viewport={"width": width, "height": height})

        await page.goto(url, wait_until="networkidle", timeout=30000)

        # 스크린샷 캡처
        screenshot_bytes = await page.screenshot(full_page=full_page)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        # 페이지 정보
        title = await page.title()

        await page.close()

        return {
            "success": True,
            "url": url,
            "title": title,
            "screenshot": screenshot_base64,
            "format": "png",
            "full_page": full_page,
            "dimensions": {"width": width, "height": height}
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"스크린샷 캡처 실패: {str(e)}",
            "url": url
        }


@mcp.tool()
async def browse_with_javascript(
    url: str,
    wait_for_selector: Optional[str] = None,
    execute_script: Optional[str] = None,
    extract_selector: Optional[str] = None,
    wait_until: str = "load"
) -> dict:
    """
    JavaScript가 필요한 동적 페이지를 브라우징합니다. (Playwright 필요)

    Args:
        url: 방문할 웹 페이지 URL
        wait_for_selector: 이 셀렉터가 나타날 때까지 대기
        execute_script: 실행할 JavaScript 코드
        extract_selector: 이 셀렉터의 내용을 추출
        wait_until: 페이지 로딩 대기 조건 ("load", "domcontentloaded", "networkidle", "commit")
                   기본값: "load" - 기본 리소스 로딩 완료 대기
                   "networkidle" - 500ms 동안 네트워크 요청 없음 (복잡한 페이지에서 timeout 가능)

    Returns:
        페이지 내용 또는 스크립트 실행 결과
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "error": "Playwright가 설치되지 않았습니다. 'pip install playwright && playwright install chromium'을 실행하세요."
        }

    try:
        browser = await get_browser()
        page = await browser.new_page()

        # Validate wait_until parameter
        valid_wait_until = ["load", "domcontentloaded", "networkidle", "commit"]
        if wait_until not in valid_wait_until:
            return {
                "success": False,
                "error": f"Invalid wait_until value: '{wait_until}'. Must be one of: {valid_wait_until}",
                "url": url
            }

        await page.goto(url, wait_until=wait_until, timeout=30000)

        # 특정 셀렉터 대기
        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, timeout=10000)

        result = {
            "success": True,
            "url": str(page.url),
            "title": await page.title()
        }

        # JavaScript 실행
        if execute_script:
            script_result = await page.evaluate(execute_script)
            result["script_result"] = script_result

        # 특정 셀렉터 내용 추출
        if extract_selector:
            elements = await page.query_selector_all(extract_selector)
            extracted = []
            for el in elements:
                text = await el.text_content()
                extracted.append(clean_text(text) if text else "")
            result["extracted_content"] = extracted

        # 기본적으로 페이지 텍스트 반환
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        result["content"] = extract_main_content(soup)[:30000]

        await page.close()

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"브라우징 실패: {str(e)}",
            "url": url
        }


@mcp.tool()
async def search_news(
    query: str,
    num_results: int = 10,
    language: str = "ko"
) -> dict:
    """
    구글 뉴스에서 검색합니다.

    Args:
        query: 검색어
        num_results: 반환할 결과 수 (기본: 10)
        language: 검색 언어 코드 (기본: ko)

    Returns:
        뉴스 검색 결과
    """
    try:
        # 구글 뉴스 검색 URL
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=nws&num={num_results}&hl={language}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                search_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": f"{language},en;q=0.5",
                }
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        results = []

        # 뉴스 결과 파싱
        for article in soup.select('div.SoaBEf, div.dbsr'):
            title_elem = article.select_one('div.n0jPhd, div.JheGif')
            link_elem = article.select_one('a')
            source_elem = article.select_one('div.CEMjEf span, div.XTjFC')
            time_elem = article.select_one('span.WG9SHc span, div.OSrXXb span')
            snippet_elem = article.select_one('div.GI74Re, div.Y3v8qd')

            if not title_elem or not link_elem:
                continue

            title = title_elem.get_text(strip=True)
            link = link_elem.get('href', '')

            # 구글 리다이렉트 URL 정리
            if link.startswith('/url?'):
                import urllib.parse
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                link = parsed.get('q', [link])[0]

            results.append({
                "title": title,
                "url": link,
                "source": source_elem.get_text(strip=True) if source_elem else "",
                "time": time_elem.get_text(strip=True) if time_elem else "",
                "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
            })

            if len(results) >= num_results:
                break

        return {
            "success": True,
            "data_type": "news_articles",
            "query": query,
            "num_results": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"뉴스 검색 실패: {str(e)}",
            "query": query
        }


@mcp.tool()
async def download_file(
    url: str,
    save_path: Optional[str] = None
) -> dict:
    """
    URL에서 파일을 다운로드합니다.

    Args:
        url: 다운로드할 파일 URL
        save_path: 저장 경로 (지정하지 않으면 임시 디렉토리에 저장)

    Returns:
        다운로드 결과 및 파일 정보
    """
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()

        # 파일명 추출
        filename = os.path.basename(urlparse(url).path)
        if not filename:
            # Content-Disposition 헤더에서 추출
            content_disp = response.headers.get('content-disposition', '')
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[1].strip('"\'')
            else:
                filename = f"downloaded_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 저장 경로 결정
        if save_path:
            filepath = save_path
        else:
            import tempfile
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, filename)

        # 파일 저장
        with open(filepath, 'wb') as f:
            f.write(response.content)

        return {
            "success": True,
            "url": url,
            "saved_to": filepath,
            "filename": filename,
            "size_bytes": len(response.content),
            "content_type": response.headers.get('content-type', 'unknown')
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"다운로드 실패: {str(e)}",
            "url": url
        }


@mcp.tool()
async def get_page_metadata(url: str) -> dict:
    """
    웹 페이지의 메타데이터를 추출합니다 (OpenGraph, Twitter Cards 등).

    Args:
        url: 메타데이터를 추출할 웹 페이지 URL

    Returns:
        페이지 메타데이터
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        metadata = {
            "url": str(response.url),
            "title": soup.title.string if soup.title else None,
        }

        # 일반 메타 태그
        meta_tags = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            if name and content:
                meta_tags[name] = content

        metadata["meta"] = meta_tags

        # OpenGraph 데이터
        og_data = {}
        for key in ['og:title', 'og:description', 'og:image', 'og:url', 'og:type', 'og:site_name']:
            if key in meta_tags:
                og_data[key.replace('og:', '')] = meta_tags[key]
        metadata["opengraph"] = og_data if og_data else None

        # Twitter Cards
        twitter_data = {}
        for key in ['twitter:title', 'twitter:description', 'twitter:image', 'twitter:card']:
            if key in meta_tags:
                twitter_data[key.replace('twitter:', '')] = meta_tags[key]
        metadata["twitter"] = twitter_data if twitter_data else None

        # Canonical URL
        canonical = soup.find('link', rel='canonical')
        if canonical:
            metadata["canonical_url"] = canonical.get('href')

        # Favicon
        favicon = soup.find('link', rel=lambda x: x and 'icon' in x.lower())
        if favicon:
            favicon_url = favicon.get('href')
            if favicon_url and favicon_url.startswith('/'):
                favicon_url = urljoin(url, favicon_url)
            metadata["favicon"] = favicon_url

        return {
            "success": True,
            **metadata
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


if __name__ == "__main__":
    import atexit

    # 종료 시 브라우저 정리
    @atexit.register
    def cleanup():
        if _browser:
            asyncio.get_event_loop().run_until_complete(close_browser())

    mcp.run(transport="streamable-http", host="0.0.0.0", port=8013)
