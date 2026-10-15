"""
ML Text Preprocessing Module

Handles text cleaning, feature extraction, and preprocessing for the
ticket resolution time prediction model.

Technical keywords (WiFi, VPN, DNS, SQL, API, etc.) are preserved
to maintain semantic meaning for the model.
"""

import re
import string
from typing import List, Optional


STOPWORDS = set("""
a an the and or but is are was were be been being to of in on at for with by from as it its
this that these those i you he she we they them his her their our your my me us
do does did done have has had having will would could should may might shall can
not no nor never more most less very too much too many all any some each every both
either neither what which who whom whose which that when where while how why how much
how many whether which here there to from up down out off over under again further
then once if only than so such than then else some what which who whom why how where
""".split())

TECHNICAL_TERMS = {
    "wifi", "vpn", "dns", "sql", "api", "postgresql", "python", "django",
    "router", "server", "network", "dns", "tcp", "udp", "http", "https",
    "ssh", "ftp", "smtp", "imap", "pop3", "ssl", "tls", "oauth", "ldap",
    "json", "xml", "html", "css", "javascript", "react", "node", "npm",
    "git", "docker", "kubernetes", "aws", "azure", "gcp", "s3", "ec2",
    "postgres", "mysql", "redis", "mongo", "elasticsearch", "kafka",
    "nginx", "apache", "centos", "ubuntu", "windows", "linux", "macos",
    "ms office", "excel", "powerpoint", "word", "outlook", "teams",
    "zoom", "slack", "jira", "confluence", "salesforce", "workday",
    "printer", "mouse", "keyboard", "monitor", "laptop", "desktop",
    "hardware", "software", "firmware", "bios", "bluetooth", "ethernet",
    "firewall", "antivirus", "malware", "virus", "trojan", "ransomware",
    "password", "authentication", "authorization", "encryption", "backup",
    "restore", "migration", "deployment", "integration", "api", "sdk",
    "sdk", "cli", "gui", "ui", "ux", "saas", "paas", "iaas", "devops",
    "ci/cd", "pipeline", "jenkins", "gitlab", "github", "bitbucket"
}


def clean_text(text: str) -> str:
    if not text or not str(text).strip():
        return ""
    
    text = str(text)
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation.replace("_", "")))
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


def tokenize_preserve_technical(text: str) -> str:
    cleaned = clean_text(text)
    return cleaned


def extract_features(text: str) -> str:
    return tokenize_preserve_technical(text)


def combine_text(title: str, description: str, issue_type: str = None) -> str:
    parts = []
    if title:
        parts.append(title)
    if description:
        parts.append(description)
    if issue_type:
        parts.append(issue_type)
    return " ".join(parts) if parts else ""


def preprocess_ticket_text(title: str, description: str, issue_type: str = None) -> str:
    combined = combine_text(title, description, issue_type)
    return extract_features(combined)
