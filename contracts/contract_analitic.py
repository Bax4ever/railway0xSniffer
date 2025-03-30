import requests
import time
import re
from urllib.parse import urlparse
from services.etherscan_api import get_contract_source_code
API_KEY = 'QKTQF4UIB2C55B3K1VQ4VQRD5U4D5NFM7B'

def extract_social_links(text):
    if not text:
        return {
            "telegram": [],
            "twitter": [],
            "website": [],
            "others": []
        }
    tg_pattern = r'(https?://t\.me/[\w\d_-]+)'
    twitter_pattern = r'(https?://(?:www\.)?(?:x\.com|twitter\.com)/[\w\d_-]+)'
    website_pattern = r'(https?://[\w\d\.-]+\.[\w]{2,}/?)'
    website_keyword_pattern = r'Website:\s*([A-Za-z0-9\.-]+\.[A-Za-z]{2,})'
    twitter_keyword_pattern = r'(?:Twitter|X):\s*(https?://[A-Za-z0-9\.-]+\.[A-Za-z]{2,}/[\w\d_-]+)'

    tg_links = re.findall(tg_pattern, text)
    twitter_links = re.findall(twitter_pattern, text)
    website_links = re.findall(website_pattern, text)
    keyword_website_links = re.findall(website_keyword_pattern, text)
    keyword_twitter_links = re.findall(twitter_keyword_pattern, text)

    result = {}
    for i, link in enumerate(tg_links, 1):
        result[f'tg{i}'] = link
    all_twitter_links = set(twitter_links + keyword_twitter_links)
    for i, link in enumerate(all_twitter_links, 1):
        result[f'x{i}'] = link
    filtered_website_links = [
        link for link in website_links + ['https://' + link if not link.startswith('http') else link for link in keyword_website_links]
        if not any(sub in link for sub in ['t.me', 'x.com', 'twitter.com'])
    ]
    unique_website_links = list(set(filtered_website_links))
    for i, link in enumerate(unique_website_links, 1):
        result[f'web{i}'] = link
    return result

def extract_total_supply_from_source_code(source_code):
    pattern1 = re.compile(r'totalSupply\s*=\s*(\d+)', re.IGNORECASE)
    pattern2 = re.compile(r'uint256\s+totalSupply\s*=\s*(\d+)', re.IGNORECASE)
    pattern3 = re.compile(r'_tTotal\s*=\s*(\d+)', re.IGNORECASE)
    match = pattern1.search(source_code) or pattern2.search(source_code) or pattern3.search(source_code)
    if match:
        return int(match.group(1))
    else:
        return None

def extract_max_wallet_limit(source_contract, total_supply):
    max_wallet_pattern = r'maxWalletSize\s*=\s*totalSupply\.mul\((\d+)\)\.div\((\d+)\);'
    match = re.search(max_wallet_pattern, source_contract)
    if not match:
        max_wallet_pattern_alt = r'_maxWalletSize\s*=\s*(\d+)\s*\*\s*10\*\*\_decimals'
        match = re.search(max_wallet_pattern_alt, source_contract)
    if match:
        if len(match.groups()) == 2:
            multiplier = int(match.group(1))
            divisor = int(match.group(2))
            return (total_supply * multiplier) / divisor
        else:
            return int(match.group(1))
    return None

def extract_tax_and_swap_parameters(source_code):
    parameters = {}
    patterns = {
        '_initialBuyTax': r'uint256\s+private\s+_initialBuyTax\s*=\s*(\d+);',
        '_initialSellTax': r'uint256\s+private\s+_initialSellTax\s*=\s*(\d+);',
        '_finalBuyTax': r'uint256\s+public\s+_finalBuyTax\s*=\s*(\d+);',
        '_finalSellTax': r'uint256\s+public\s+_finalSellTax\s*=\s*(\d+);',
        '_reduceBuyTaxAt': r'uint256\s+private\s+_reduceBuyTaxAt\s*=\s*(\d+);',
        '_reduceSellTaxAt': r'uint256\s+private\s+_reduceSellTaxAt\s*=\s*(\d+);',
        '_preventSwapBefore': r'uint256\s+private\s+_preventSwapBefore\s*=\s*(\d+);',
        '_transferTax': r'uint256\s+public\s+_transferTax\s*=\s*(\d+);',
        '_buyCount': r'uint256\s+public\s+_buyCount\s*=\s*(\d+);'
    }
    for param, pattern in patterns.items():
        match = re.search(pattern, source_code, re.IGNORECASE)
        if match:
            parameters[param] = int(match.group(1))
        else:
            parameters[param] = None
    return parameters
