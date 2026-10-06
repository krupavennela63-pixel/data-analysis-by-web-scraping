import re
import json
import time
import urllib.parse
import urllib.robotparser
from typing import Optional
import requests
from bs4 import BeautifulSoup


ALLOWED_SCHEMES = {'http', 'https'}
BLOCKED_HOSTS = {
    'localhost', '127.0.0.1', '0.0.0.0', '::1',
    '169.254.169.254',  # AWS metadata
    '10.0.0.1',
}
BLOCKED_PREFIXES = ('10.', '172.16.', '172.17.', '172.18.', '172.19.',
                    '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                    '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                    '172.30.', '172.31.', '192.168.')

HEADERS = {
    'User-Agent': 'DataAnalyzerBot/1.0 (Educational Web Scraper; +https://github.com/dataanalyzer)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

REQUEST_TIMEOUT = 15
MAX_PAGES = 10
REQUEST_DELAY = 1.5


def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL for security (prevent SSRF) and format."""
    if not url or not url.strip():
        return False, "URL cannot be empty."

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "Invalid URL format."

    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"URL scheme '{parsed.scheme}' is not allowed. Use http or https."

    hostname = parsed.hostname or ''
    hostname_lower = hostname.lower()

    if hostname_lower in BLOCKED_HOSTS:
        return False, "Access to this host is not permitted."

    for prefix in BLOCKED_PREFIXES:
        if hostname_lower.startswith(prefix):
            return False, "Access to private/internal IP ranges is not permitted."

    if re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname_lower):
        return False, "Direct IP addresses are not permitted. Use a domain name."

    if not hostname or '.' not in hostname:
        return False, "Invalid hostname in URL."

    return True, url


def check_robots_txt(base_url: str, path: str = '/') -> bool:
    """Check if scraping is allowed by robots.txt."""
    try:
        parsed = urllib.parse.urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(HEADERS['User-Agent'], base_url)
    except Exception:
        return True  # If robots.txt is unavailable, allow


def fetch_page(url: str, timeout: int = REQUEST_TIMEOUT) -> tuple[Optional[BeautifulSoup], Optional[str]]:
    """Fetch a page and return BeautifulSoup object."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            return None, f"URL does not return HTML content (got: {content_type})"

        soup = BeautifulSoup(response.text, 'lxml')
        return soup, None

    except requests.exceptions.Timeout:
        return None, "Request timed out. The website took too long to respond."
    except requests.exceptions.TooManyRedirects:
        return None, "Too many redirects. Cannot access this URL."
    except requests.exceptions.SSLError:
        return None, "SSL/TLS error. Cannot establish a secure connection."
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection error: {str(e)[:200]}"
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP error {e.response.status_code}: {e.response.reason}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)[:200]}"


def detect_html_elements(soup: BeautifulSoup) -> dict:
    """Detect tags, IDs, and CSS classes from the page."""
    tags = {}
    ids = {}
    classes = {}

    skip_tags = {'script', 'style', 'meta', 'link', 'head', 'html', 'body', 'noscript', 'iframe'}
    skip_classes_patterns = re.compile(
        r'(nav|header|footer|menu|cookie|modal|popup|overlay|advertisement|ad-|sidebar|breadcrumb)',
        re.IGNORECASE
    )

    for element in soup.find_all(True):
        tag_name = element.name
        if tag_name in skip_tags:
            continue

        text = element.get_text(strip=True)
        if not text or len(text) < 2:
            continue

        # Count tags
        if tag_name not in tags:
            tags[tag_name] = {'count': 0, 'sample': text[:100]}
        tags[tag_name]['count'] += 1

        # Collect IDs
        elem_id = element.get('id')
        if elem_id and len(elem_id) > 1:
            if elem_id not in ids:
                ids[elem_id] = {'count': 0, 'sample': text[:100], 'tag': tag_name}
            ids[elem_id]['count'] += 1

        # Collect classes
        elem_classes = element.get('class', [])
        for cls in elem_classes:
            if len(cls) < 2 or skip_classes_patterns.search(cls):
                continue
            if cls not in classes:
                classes[cls] = {'count': 0, 'sample': text[:100], 'tag': tag_name}
            classes[cls]['count'] += 1

    # Sort by count and take top entries
    sorted_tags = sorted(tags.items(), key=lambda x: x[1]['count'], reverse=True)[:20]
    sorted_ids = sorted(ids.items(), key=lambda x: x[1]['count'], reverse=True)[:20]
    sorted_classes = sorted(classes.items(), key=lambda x: x[1]['count'], reverse=True)[:30]

    return {
        'tags': [{'name': k, 'count': v['count'], 'sample': v['sample']} for k, v in sorted_tags],
        'ids': [{'name': k, 'count': v['count'], 'sample': v['sample'], 'tag': v['tag']} for k, v in sorted_ids],
        'classes': [{'name': k, 'count': v['count'], 'sample': v['sample'], 'tag': v['tag']} for k, v in sorted_classes],
        'page_title': soup.title.string.strip() if soup.title and soup.title.string else 'Unknown Page',
    }


def scrape_with_selectors(soup: BeautifulSoup, selectors: list[dict]) -> list[dict]:
    """
    Scrape data using provided selectors.
    Each selector: {'type': 'tag'|'id'|'class', 'value': 'name', 'label': 'Display Name'}
    """
    rows = []

    # Build elements per selector
    selector_elements = {}
    for sel in selectors:
        sel_type = sel.get('type')
        sel_value = sel.get('value')
        label = sel.get('label', sel_value)

        if sel_type == 'tag':
            elements = soup.find_all(sel_value)
        elif sel_type == 'id':
            elem = soup.find(id=sel_value)
            elements = [elem] if elem else []
        elif sel_type == 'class':
            elements = soup.find_all(class_=sel_value)
        else:
            elements = []

        selector_elements[label] = [e.get_text(separator=' ', strip=True) for e in elements if e.get_text(strip=True)]

    if not selector_elements:
        return []

    # Align rows
    max_len = max((len(v) for v in selector_elements.values()), default=0)
    if max_len == 0:
        return []

    for i in range(max_len):
        row = {}
        for label, values in selector_elements.items():
            row[label] = values[i] if i < len(values) else ''
        rows.append(row)

    return rows


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    """Try to find a 'next page' link."""
    next_patterns = [
        'next', 'next-page', 'pagination-next', '»', '›', 'older posts',
        'load more', 'see more',
    ]

    for pattern in next_patterns:
        link = soup.find('a', string=re.compile(pattern, re.IGNORECASE))
        if link and link.get('href'):
            href = link['href']
            return urllib.parse.urljoin(current_url, href)

        link = soup.find('a', rel='next')
        if link and link.get('href'):
            return urllib.parse.urljoin(current_url, link['href'])

        link = soup.find('a', {'aria-label': re.compile(r'next', re.IGNORECASE)})
        if link and link.get('href'):
            return urllib.parse.urljoin(current_url, link['href'])

    return None


def multi_page_scrape(start_url: str, selectors: list[dict], max_pages: int = MAX_PAGES) -> tuple[list[dict], list[str]]:
    """Scrape multiple pages following pagination."""
    all_rows = []
    visited_urls = set()
    errors = []
    current_url = start_url
    page_num = 1

    while current_url and page_num <= max_pages:
        if current_url in visited_urls:
            break
        visited_urls.add(current_url)

        soup, error = fetch_page(current_url)
        if error:
            errors.append(f"Page {page_num} ({current_url}): {error}")
            break

        rows = scrape_with_selectors(soup, selectors)
        all_rows.extend(rows)

        next_url = find_next_page_url(soup, current_url)
        if not next_url or next_url == current_url:
            break

        # Validate next URL stays on same domain
        orig_parsed = urllib.parse.urlparse(start_url)
        next_parsed = urllib.parse.urlparse(next_url)
        if orig_parsed.netloc != next_parsed.netloc:
            break

        current_url = next_url
        page_num += 1
        time.sleep(REQUEST_DELAY)

    return all_rows, errors
