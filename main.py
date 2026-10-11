#!/usr/bin/env python3
import requests
import re
import sys
import os
import json
from html import unescape
import string
import time
import threading
import shutil
from colorama import Fore, init
from datetime import datetime, timedelta
from multiprocessing.dummy import Pool as ThreadPool
from urllib.parse import urljoin, urlparse

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

try:
    os.mkdir("Result")
except:
    pass

all_pages_link = []
init(autoreset=True)
RESULT_LOCK = threading.Lock()
PROXY_LOCK = threading.Lock()
PROXY_POOL = []
PROXY_INDEX = 0


class UrlscanRateLimitError(requests.RequestException):
    """Raised when URLScan asks the caller to slow down."""

    def __init__(self, message, retry_after=60):
        super().__init__(message)
        self.retry_after = retry_after

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def ConfigureProxies(proxy_file):
    global PROXY_POOL, PROXY_INDEX
    proxies = []
    with open(proxy_file, "r", encoding="utf-8") as proxy_handle:
        for line in proxy_handle:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            if "://" not in value:
                value = f"http://{value}"
            if value.startswith(("http://", "https://", "socks4://", "socks5://")):
                proxies.append(value)

    with PROXY_LOCK:
        PROXY_POOL = list(dict.fromkeys(proxies))
        PROXY_INDEX = 0
    return len(PROXY_POOL)


def RequestGet(url, **kwargs):
    global PROXY_INDEX
    with PROXY_LOCK:
        proxy_count = len(PROXY_POOL)
        start_index = PROXY_INDEX
        PROXY_INDEX += 1

    attempts = max(1, proxy_count)
    last_response = None
    last_error = None
    for offset in range(attempts):
        proxy_url = None
        if proxy_count:
            with PROXY_LOCK:
                proxy_url = PROXY_POOL[(start_index + offset) % proxy_count]
        request_kwargs = dict(kwargs)
        if proxy_url:
            request_kwargs["proxies"] = {
                "http": proxy_url,
                "https": proxy_url,
            }
        try:
            response = requests.get(url, **request_kwargs)
            if response.status_code == 429 and offset < attempts - 1:
                last_response = response
                continue
            return response
        except requests.RequestException as error:
            last_error = error
            if offset == attempts - 1:
                raise

    if last_response is not None:
        return last_response
    if last_error is not None:
        raise last_error
    raise requests.RequestException("Request failed without a response")


def NormalizeDomain(value):
    domain = value.strip().lower()
    domain = re.sub(r"^[a-z][a-z0-9+.-]*://", "", domain)
    domain = domain.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return domain.rstrip(".")


def AppendUniqueDomains(path, domains):
    candidates = []
    seen = set()
    for value in domains:
        domain = NormalizeDomain(value)
        if domain and "." in domain and domain not in seen:
            candidates.append(domain)
            seen.add(domain)

    if not candidates:
        return 0

    with RESULT_LOCK:
        existing = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as result_handle:
                existing = [
                    NormalizeDomain(line)
                    for line in result_handle
                    if NormalizeDomain(line)
                ]
        unique_existing = list(dict.fromkeys(existing))
        new_domains = [
            domain for domain in candidates if domain not in unique_existing
        ]
        all_domains = unique_existing + new_domains
        if all_domains != existing:
            with open(path, "w", encoding="utf-8") as result_handle:
                result_handle.write("\n".join(all_domains) + "\n")
    return len(new_domains)

def Banner():
    os.system("cls" if os.name == "nt" else "clear")
    artwork = """
                                                           
                        .:      .:.                        
                     .+=:        .=*=.                     
                   .*=.            .-*-.                   
                  .#=.              .:#+.                  
                  *#.                .=#:                  
                 .##.                .-#*.                 
                 .##:                .*#*.                 
                  ###:   .........  .=##:                  
                  .###=.:###***##=..*##*.                  
             ...:--=####*:.......-####*==-:..              
           .:###############*.###############*:            
         .-##*-... ..=#####+..:#####*-..   .-*##:          
        .+#=.       *+..*#*.   -##=..*:       .=#=         
        -*:.        =#=...:*-:=+....##.        .-*:        
       .*:.         .*#-..=#####:..*#-.         .=*        
       .+.           .=##::#####.=##:.           :*        
       ...             .-::#####.-:.             .:        
                         .+#####-.                         
                        .=###:###:.                        
           ....      ..:###*...###+...      ....           
           ..=--:..:=*###*.    .:####=:....:-=..           
              ..:=+++=:.          ..-=+++=:.               
                                                           
                                                           
"""
    terminal_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    for line in artwork.splitlines():
        if line.strip():
            print(f"{Fore.LIGHTCYAN_EX}{line.center(terminal_width)}{Fore.RESET}")
        else:
            print()
    print(f"{Fore.LIGHTCYAN_EX}{'Created By X-Jama'.center(terminal_width)}{Fore.RESET}")


def Menu():
    Banner()
    menus = f"""
{Fore.LIGHTRED_EX}[{Fore.WHITE}1{Fore.LIGHTRED_EX}] {Fore.WHITE}Grabber By Date
{Fore.LIGHTRED_EX}[{Fore.WHITE}2{Fore.LIGHTRED_EX}] {Fore.WHITE}Grabber By KeyWord
{Fore.LIGHTRED_EX}[{Fore.WHITE}3{Fore.LIGHTRED_EX}] {Fore.WHITE}Grabber By TLD (azstats.org)
{Fore.LIGHTRED_EX}[{Fore.WHITE}4{Fore.LIGHTRED_EX}] {Fore.WHITE}Grabber By TLD (pagesinventory.com)
{Fore.LIGHTRED_EX}[{Fore.WHITE}5{Fore.LIGHTRED_EX}] {Fore.WHITE}Grabber By TLD (topsitessearch.com)
{Fore.LIGHTRED_EX}[{Fore.WHITE}6{Fore.LIGHTRED_EX}] {Fore.WHITE}Grabber Domain Random (www.topmillion.net)\n"""
    print(menus)
    try:
        choose = int(input(f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] {Fore.WHITE}Choose : "))
    except ValueError:
        print(f"{Fore.LIGHTRED_EX}Choose must be a number from 1 to 6.")
        return

    if choose == 1:
        CubDomain()
    elif choose == 2:
        try:
            keyword_file = SelectKeywordFile()
        except OSError as error:
            print(f"{Fore.LIGHTRED_EX}Unable to open file dialog: {error}")
            return
        if keyword_file is None:
            print(f"{Fore.LIGHTYELLOW_EX}No keyword file selected.")
            return

        try:
            with open(keyword_file, "r", encoding="utf-8") as keyword_handle:
                input_list = [line.strip() for line in keyword_handle if line.strip()]
        except OSError as error:
            print(f"{Fore.LIGHTRED_EX}Unable to read keyword file: {error}")
            return

        if not ConfigureProxyMode():
            return
        print(
            f"{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] "
            f"{Fore.WHITE}Loaded {Fore.LIGHTGREEN_EX}{len(input_list)} "
            f"{Fore.WHITE}keywords. Starting URLScan search..."
        )
        for index, keyword in enumerate(input_list, start=1):
            GrabberByKw(keyword, index, len(input_list))
    elif choose == 3:
        inp_tlds = ParseTlds(
            input(
                f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] "
                f"{Fore.WHITE}TLD Domain (ex: com,net,co,us) : "
            )
        )
        if not inp_tlds:
            print(f"{Fore.LIGHTRED_EX}At least one TLD is required.")
            return
        start_time = time.time()
        
        pool = ThreadPool(20)
        pool.map(GrabTldByTld, [(tld, "azstats") for tld in inp_tlds])
        pool.close()
        pool.join()
        
        end_time = time.time()

        print(f"{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Time Taken {Fore.LIGHTGREEN_EX}{str(end_time - start_time).split('.')[0]} {Fore.WHITE}Sec")
    elif choose == 4:
        inp_tlds = ParseTlds(
            input(
                f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] "
                f"{Fore.WHITE}TLD Domain (ex: com,net,co,us) : "
            )
        )
        if not inp_tlds:
            print(f"{Fore.LIGHTRED_EX}At least one TLD is required.")
            return
        start_time = time.time()
        
        pool = ThreadPool(20)
        pool.map(GrabTldByTld, [(tld, "pagesinventory") for tld in inp_tlds])
        pool.close()
        pool.join()
        
        end_time = time.time()

        print(f"\n{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Time Taken {Fore.LIGHTGREEN_EX}{str(end_time - start_time).split('.')[0]} {Fore.WHITE}Sec")
    elif choose == 5:
        inp_tlds = [
            tld.strip().lstrip(".")
            for tld in input(
                f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] "
                f"{Fore.WHITE}TLD Domain (ex: com,net,co,us) : "
            ).split(",")
            if tld.strip().lstrip(".")
        ]
        if not inp_tlds:
            print(f"{Fore.LIGHTRED_EX}At least one TLD is required.")
            return
        try:
            inp_page = int(input(f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] {Fore.WHITE}Total Page (ex: 100) : "))
            if inp_page < 1:
                raise ValueError
        except ValueError:
            print(f"{Fore.LIGHTRED_EX}Total page must be a positive number.")
            return
        list_url = []
        for inp_tld in inp_tlds:
            list_url.extend(GeneratePageTopSite(inp_tld, inp_page))
        
        start_time = time.time()
        
        pool = ThreadPool(5)
        pool.map(GrabTopSite, list_url)
        pool.close()
        pool.join()
        
        end_time = time.time()

        print(f"\n{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Time Taken {Fore.LIGHTGREEN_EX}{str(end_time - start_time).split('.')[0]} {Fore.WHITE}Sec")
    elif choose == 6:
        list_url = getTopMilionPageUrl()
        
        start_time = time.time()
        
        pool = ThreadPool(20)
        pool.map(grabTopMilionPageUrl, list_url)
        pool.close()
        pool.join()
        
        end_time = time.time()

        print(f"\n{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Time Taken {Fore.LIGHTGREEN_EX}{str(end_time - start_time).split('.')[0]} {Fore.WHITE}Sec")
    else:
        exit(f"{Fore.LIGHTRED_EX}[{Fore.WHITE}!{Fore.LIGHTRED_EX}] {Fore.LIGHTYELLOW_EX}Aborted.")

def SelectKeywordFile():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        root.update()
        return filedialog.askopenfilename(
            parent=root,
            title="Select keyword list",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        ) or None
    finally:
        root.attributes("-topmost", False)
        root.destroy()


def SelectProxyFile():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        root.update()
        return filedialog.askopenfilename(
            parent=root,
            title="Select proxy list",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        ) or None
    finally:
        root.attributes("-topmost", False)
        root.destroy()


def ConfigureProxyMode():
    choice = input(
        f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] "
        f"{Fore.WHITE}Use proxy? (y/n): "
    ).strip().lower()
    if choice not in {"y", "yes"}:
        with PROXY_LOCK:
            PROXY_POOL.clear()
        print(f"{Fore.LIGHTGREEN_EX}Proxy disabled. Using direct connection.")
        return True

    proxy_file = SelectProxyFile()
    if proxy_file is None:
        print(f"{Fore.LIGHTYELLOW_EX}No proxy file selected. Using direct connection.")
        return True
    try:
        count = ConfigureProxies(proxy_file)
    except (OSError, UnicodeError) as error:
        print(f"{Fore.LIGHTRED_EX}Unable to read proxy file: {error}")
        return False
    if not count:
        print(f"{Fore.LIGHTRED_EX}No valid proxy found in the selected file.")
        return False
    print(f"{Fore.LIGHTGREEN_EX}Loaded {count} proxies.")
    return True

def ParseTlds(value):
    return list(dict.fromkeys(
        tld.strip().lstrip(".").lower()
        for tld in value.split(",")
        if tld.strip().lstrip(".")
    ))

def getTopMilionPageUrl():
    try:
        req = RequestGet(
            "https://www.topmillion.net/pages/websites/",
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        req.raise_for_status()

        pages = re.findall(r"/pages/websites/page/(\d+)/", req.text)
        if not pages:
            sys.stdout.write(
                f"\n{Fore.LIGHTRED_EX}TopMillion did not return a page list."
            )
            return []

        last_page = max(map(int, pages))
        arr = []
        for page in range(1, last_page + 1):
            arr.append(f"https://www.topmillion.net/pages/websites/page/{page}/")
            
        return arr
    except requests.RequestException as error:
        sys.stdout.write(f"\n{Fore.LIGHTRED_EX}TopMillion request failed: {error}")
        return []

def grabTopMilionPageUrl(url):
    try:
        page = url.split("/")[-2]
        req = RequestGet(url, headers=REQUEST_HEADERS, timeout=15)
        req.raise_for_status()

        domains = [
            j.replace("https://", "").replace("http://", "").split("?")[0]
            for j in re.findall(
                r"https?://s\.wordpress\.com/mshots/v1/([^\"'<]+)\?w=400",
                req.text,
            )
        ]
        
        if len(domains) != 0:
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}{len(domains)} {Fore.WHITE}Domain Grabbed From Page {page}!")
            
            AppendUniqueDomains("Result/Random-Domain.txt", domains)
        else:
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}Domain Grabbed From Page {page}!")
    except requests.RequestException as error:
        sys.stdout.write(
            f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}"
            f"Domain Grabbed From Page {page} ({error})!"
        )

def GrabTopSite(url):
    try:
        page = url.rstrip("/").split("/")[-1]
        response = None
        last_error = None
        for attempt in range(2):
            try:
                response = RequestGet(
                    url,
                    headers=REQUEST_HEADERS,
                    timeout=20,
                )
                response.raise_for_status()
                break
            except requests.RequestException as error:
                last_error = error
                if attempt == 0:
                    time.sleep(1)

        if response is None:
            raise last_error

        domains = re.findall(
            r'(?:domain=|/(?:domain|site)/|domains/)([a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,})',
            response.text,
            flags=re.IGNORECASE,
        )
        domains = [
            domain.lower().rstrip(".")
            for domain in dict.fromkeys(domains)
            if "." in domain
        ]
        
        if len(domains) == 0:
            sys.stdout.write(
                f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}"
                f"Domain Grabbed From Page {page} (no matching domain links)!"
            )
        else:
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}{len(domains)} {Fore.WHITE}Domain Grabbed From Page {page}!")
            
            AppendUniqueDomains("Result/grab_tld.txt", domains)
    except requests.RequestException as error:
        status = getattr(error.response, "status_code", None)
        reason = f"HTTP {status}" if status else str(error)
        sys.stdout.write(
            f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}"
            f"Domain Grabbed From Page {page} ({reason})!"
        )

def GeneratePageTopSite(tld, totalPage):
    return [
        f"https://www.topsitessearch.com/domains/.{tld}/{page}"
        for page in range(1, totalPage + 1)
    ]

def CubDomain_GetDomain(urls: str):
    try:
        response = RequestGet(urls, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        req = response.text

        all_domains = re.findall(
            r'<a[^>]+href=["\'](?:https?://www\.cubdomain\.com)?/site/([^"\'>/?]+)'
            r'|<div[^>]+class=["\'][^"\']*\bcol-md-4\b[^"\']*["\'][^>]*>'
            r'\s*<a[^>]*>([^<]+)',
            req,
            flags=re.IGNORECASE,
        )
        all_domains = [
            (domain[0] or domain[1]).strip()
            for domain in all_domains
            if (domain[0] or domain[1]).strip()
        ]
        
        if len(all_domains) == 0:
            sys.stdout.write(
                f"\n{Fore.LIGHTCYAN_EX}[{Fore.LIGHTBLUE_EX}-{Fore.LIGHTCYAN_EX}] "
                f"{Fore.WHITE}No domain data in page (source returned app shell)"
            )
        else:
            sys.stdout.write(f"\n{Fore.LIGHTCYAN_EX}[{Fore.LIGHTBLUE_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Grabbed {Fore.LIGHTGREEN_EX}{len(all_domains)} {Fore.WHITE}Domain")
            AppendUniqueDomains("Result/cubdomain_bydate.txt", all_domains)
    except requests.RequestException as error:
        sys.stdout.write(f"\n{Fore.LIGHTRED_EX}CubDomain request failed: {error}")

def CubDomain_GetAllPages(date: str):
    global all_pages_link
    
    try:
        response = RequestGet(
            f"https://www.cubdomain.com/domains-registered-by-date/{date}/1",
            headers=REQUEST_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        all_pages_link.append(response.url)
        all_pages = re.findall(
            r'<a[^>]+class=["\']?page-link["\']?[^>]+href=["\']([^"\']+)',
            response.text,
            flags=re.IGNORECASE,
        )
        for page_url in all_pages:
            all_pages_link.append(urljoin(response.url, page_url))
    except requests.RequestException as error:
        sys.stdout.write(f"\n{Fore.LIGHTRED_EX}CubDomain page request failed: {error}")

def GenerateTLD2(tld):
    try:
        arr = []
        
        for x in string.ascii_lowercase:
            arr.append(f"https://www.pagesinventory.com/tld/{tld}/{x}.html")
        
        return arr
    except:
        return []

def SaveTldDomains(domains):
    return AppendUniqueDomains("Result/grab_tld.txt", domains)

def FetchCertificateDomains(tld):
    last_error = None
    for attempt in range(2):
        try:
            response = RequestGet(
                "https://crt.sh/",
                params={"q": f".{tld}", "output": "json"},
                headers=REQUEST_HEADERS,
                timeout=15,
            )
            response.raise_for_status()
            records = response.json()
            domains = []
            for record in records:
                for name in record.get("name_value", "").splitlines():
                    name = name.strip().lower().lstrip("*.")
                    if name.endswith(f".{tld}") and " " not in name:
                        domains.append(name)
            return domains
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt == 0:
                time.sleep(2)

    raise requests.RequestException(
        f"Certificate Transparency service unavailable after 2 attempts: {last_error}"
    )

def FetchKeywordDomains(keyword):
    last_error = None
    search_terms = [
        term.lower()
        for term in re.findall(r"[a-z0-9-]+", keyword.lower())
        if len(term) >= 3
    ]
    if not search_terms:
        return []

    for attempt in range(2):
        try:
            response = RequestGet(
                "https://crt.sh/",
                params={"q": f"%{keyword}%", "output": "json"},
                headers=REQUEST_HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            records = response.json()
            domains = []
            for record in records:
                for name in record.get("name_value", "").splitlines():
                    name = name.strip().lower().lstrip("*.")
                    if "." in name and any(term in name for term in search_terms):
                        domains.append(name)
            return domains
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt == 0:
                time.sleep(2)

    raise requests.RequestException(
        f"Keyword fallback unavailable after 2 attempts: {last_error}"
    )

def FetchUrlscanKeywordDomains(keyword):
    terms = list(dict.fromkeys(
        term for term in re.findall(r"[a-z0-9-]+", keyword.lower())
        if len(term) >= 3
    ))
    if not terms:
        return []

    query = " OR ".join(
        f"page.domain:{term} OR page.url:{term}" for term in terms
    )
    last_error = None
    for attempt in range(3):
        try:
            response = RequestGet(
                "https://urlscan.io/api/v1/search/",
                params={"q": query},
                headers=REQUEST_HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            domains = []
            for result in response.json().get("results", []):
                domain = result.get("page", {}).get("domain", "")
                if domain and "." in domain:
                    domains.append(domain.lower().strip())
            return list(dict.fromkeys(domains))
        except (requests.RequestException, ValueError) as error:
            last_error = error
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status == 429:
                retry_after = getattr(
                    getattr(error, "response", None), "headers", {}
                ).get("Retry-After", "")
                try:
                    retry_seconds = max(5, int(retry_after))
                except (TypeError, ValueError):
                    retry_seconds = 60
                raise UrlscanRateLimitError(
                    "URLScan rate limit reached",
                    retry_after=retry_seconds,
                ) from error
            if attempt < 2:
                retry_after = getattr(getattr(error, "response", None), "headers", {}).get(
                    "Retry-After", ""
                )
                try:
                    delay = max(5, min(int(retry_after), 60))
                except (TypeError, ValueError):
                    delay = 5 * (attempt + 1)
                if status == 429:
                    time.sleep(delay)
                else:
                    time.sleep(2)

    raise requests.RequestException(
        f"URLScan search unavailable after 3 attempts: {last_error}"
    )

def FetchDuckDuckGoKeywordDomains(keyword):
    response = RequestGet(
        "https://html.duckduckgo.com/html/",
        params={"q": keyword},
        headers=REQUEST_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    domains = []
    for href in re.findall(
        r'class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)',
        response.text,
        flags=re.IGNORECASE,
    ):
        url = unescape(href)
        parsed = urlparse(url)
        domain = parsed.hostname
        if domain and "." in domain:
            domains.append(domain.lower())
    return domains

def FetchKeywordFallbacks(keyword):
    domains = FetchUrlscanKeywordDomains(keyword)
    return list(dict.fromkeys(domains))

def GrabTldByTld(task):
    tld, source = task
    source_url = (
        f"https://azstats.org/top/domain-zone/{tld}/1"
        if source == "azstats"
        else f"https://www.pagesinventory.com/tld/{tld}/a.html"
    )
    page = f"{source}:{tld}"

    source_error = None
    try:
        response = RequestGet(source_url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        domains = re.findall(
            r'(?:href=["\'](?:https?://[^"\']+)?/(?:site|domain)/|domain=)'
            r'([^"\'&<>\s/?]+)',
            response.text,
            flags=re.IGNORECASE,
        )
        saved = SaveTldDomains(domains)
        if saved:
            sys.stdout.write(
                f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}{saved} "
                f"{Fore.WHITE}Grabbed From {page}!"
            )
            return
    except requests.RequestException as error:
        source_error = error

    try:
        domains = FetchCertificateDomains(tld)
        saved = SaveTldDomains(domains)
        sys.stdout.write(
            f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}{saved} "
            f"{Fore.WHITE}Grabbed From public fallback {tld}!"
        )
    except requests.RequestException as error:
        sys.stdout.write(
            f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}Domain "
            f"Grabbed From {page}: source unavailable ({source_error}); "
            f"fallback unavailable ({error})."
        )

def GrabTld2(url):
    try:
        req = RequestGet(url, headers=REQUEST_HEADERS, timeout=15)
        req.raise_for_status()
        domains = re.findall(r'href=["\']/domain/([^"\']+?)\.html', req.text)
        
        if len(domains) != 0:
            saved = AppendUniqueDomains("Result/grab_tld.txt", domains)
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}{saved} {Fore.WHITE}New Domain Grabbed!")
        else:
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}Grabbed!")
    except requests.RequestException as error:
        status = getattr(error.response, "status_code", None)
        reason = (
            f"HTTP {status} - source blocked or unavailable"
            if status
            else str(error)
        )
        sys.stdout.write(
            f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}"
            f"Grabbed ({reason})!"
        )

def GrabTld(url):
    try:
        req = RequestGet(url, headers=REQUEST_HEADERS, timeout=15)
        req.raise_for_status()
        domains = re.findall(r'href=["\']/site/([^"\']+?)/["\']', req.text)
        
        if len(domains) != 0:
            saved = AppendUniqueDomains("Result/grab_tld.txt", domains)
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}{saved} {Fore.WHITE}New Domain Grabbed!")
        else:
            sys.stdout.write(f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}Grabbed!")
    except requests.RequestException as error:
        status = getattr(error.response, "status_code", None)
        reason = (
            f"HTTP {status} - source blocked or unavailable"
            if status
            else str(error)
        )
        sys.stdout.write(
            f"\n{Fore.WHITE}---> {Fore.LIGHTBLUE_EX}0 {Fore.WHITE}"
            f"Grabbed ({reason})!"
        )

def GenerateTldLink(tld):
    try:
        arr = []
        
        for x in range(1, 101):
            arr.append(f"https://azstats.org/top/domain-zone/{tld}/{x}")

        return arr
    except:
        return []

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def CubDomain():
    global all_pages_link

    try:
        date1 = datetime.strptime(
            input(f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] {Fore.WHITE}From Date (ex: YYYY-mm-dd) : "),
            "%Y-%m-%d",
        )
        date2 = datetime.strptime(
            input(f"{Fore.LIGHTRED_EX}[{Fore.WHITE}?{Fore.LIGHTRED_EX}] {Fore.WHITE}To Date (ex: YYYY-mm-dd) : "),
            "%Y-%m-%d",
        )
    except ValueError:
        print(f"{Fore.LIGHTRED_EX}Date must use the YYYY-mm-dd format.")
        return

    if date1 > date2:
        print(f"{Fore.LIGHTRED_EX}From Date cannot be later than To Date.")
        return

    all_pages_link.clear()
    date_arr = [ f"{str(this_date.year)}-{str(this_date.month).zfill(2)}-{str(this_date.day).zfill(2)}" for this_date in daterange(date1, date2) ]

    print(f"{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Grabbing All Pages")

    start_time = time.time()

    pool = ThreadPool(20)
    pool.map(CubDomain_GetAllPages, date_arr)
    pool.close()
    pool.join()

    print(f"{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Grabbing Domain From {Fore.LIGHTGREEN_EX}{len(all_pages_link)} {Fore.WHITE}Pages")

    pools = ThreadPool(20)
    pools.map(CubDomain_GetDomain, all_pages_link)
    pools.close()
    pools.join()

    end_time = time.time()

    result_file = "Result/cubdomain_bydate.txt"
    domain_count = 0
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as result_handle:
            domain_count = sum(1 for line in result_handle if line.strip())

    print(f"\n\n{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Done Grabbing {Fore.LIGHTGREEN_EX}{domain_count} {Fore.WHITE}Domain")
    print(f"{Fore.LIGHTCYAN_EX}[{Fore.LIGHTGREEN_EX}-{Fore.LIGHTCYAN_EX}] {Fore.WHITE}Time Taken {Fore.LIGHTGREEN_EX}{str(end_time - start_time).split('.')[0]} {Fore.WHITE}Sec")

def GrabberByKw(kw, index=1, total=1):
    print(
        f"\n[{index}/{total}] Searching keyword "
        f"{Fore.LIGHTBLUE_EX}{kw}{Fore.WHITE} via URLScan...",
        end="",
        flush=True,
    )
    try:
        fallback_domains = FetchKeywordFallbacks(kw)
        saved = SaveKeywordDomains(fallback_domains)
        sys.stdout.write(
            f" {Fore.WHITE}-- got {Fore.LIGHTGREEN_EX}{saved} "
            f"{Fore.WHITE}Domain"
        )
    except UrlscanRateLimitError as error:
        wait_seconds = min(error.retry_after, 60)
        sys.stdout.write(
            f" {Fore.WHITE}-- {Fore.LIGHTRED_EX}{error}; "
            f"waiting {wait_seconds}s before continuing"
        )
        sys.stdout.flush()
        time.sleep(wait_seconds)
        return True
    except requests.RequestException as error:
        sys.stdout.write(
            f" {Fore.WHITE}-- {Fore.LIGHTRED_EX}No result ({error})"
        )
    return True

def SaveKeywordDomains(domains):
    return AppendUniqueDomains("Result/domain_keyword.txt", domains)

if __name__ == "__main__":
    Menu()
