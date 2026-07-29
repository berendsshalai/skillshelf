import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parents[1]

def test_all_routes():
    for route in ("skills", "architecture", "installation", "provenance", "agents", "mcp", "credits", "socials"):
        path = ROOT / "site" / route / "index.html"
        assert path.is_file()
        value = path.read_text()
        assert 'lang="en-ZA"' in value
        assert 'rel="canonical"' in value

def test_social_exact_order_and_security():
    value = (ROOT / "site/socials/index.html").read_text()
    urls = [
        "https://github.com/berendsshalai",
        "https://www.linkedin.com/in/sha-lai-berends",
        "https://x.com/berendsshalai",
        "https://www.facebook.com/p/Sha-Lai-Berends-61591546301365/",
        "https://www.instagram.com/berendsshalai",
        "https://bit.ly/3sA5312",
        "https://sha-lai-be-2a6c6108-shalaiberends.wix-site-host.com",
    ]
    positions = [value.index(f'href="{url}"') for url in urls]
    assert positions == sorted(positions)
    assert value.count('class="social-card"') == 7
    assert value.count('rel="me noopener noreferrer"') == 7
    assert ":focus-visible" in (ROOT / "site/assets/styles.css").read_text()
    structured = re.search(r'<script type="application/ld\+json">(.*?)</script>', value).group(1)
    assert json.loads(structured)["mainEntity"]["name"] == "Sha-Lai Berends"

def test_reduced_motion_and_mobile():
    css = (ROOT / "site/assets/styles.css").read_text()
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (max-width: 560px)" in css
    assert "overflow" not in re.sub(r"overflow: auto", "", css)
