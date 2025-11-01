import re
import logging
import os
import hashlib
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SafetyChecker:
    def __init__(self):
        self.harmful_patterns = [
            r'\b(jailbreak|prompt injection|ignore instructions)\b',
            r'\b(ignore previous|forget everything|system prompt)\b',
            r'\b(act as|pretend to be|roleplay as)\b',
            r'\b(hack|crack|exploit|bypass)\b',
            r'\b(illegal|unlawful|harmful|dangerous)\b',
            r'\b(suicide|self-harm|violence|threat)\b',
            r'\b(personal information|private data|confidential)\b',
            r'\b(phishing|scam|fraud|malware)\b'
        ]
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.harmful_patterns]
        self.injection_keywords = [
            'ignore', 'forget', 'override', 'bypass', 'jailbreak',
            'system', 'admin', 'root', 'privilege', 'elevate',
            'injection', 'payload', 'exploit', 'vulnerability'
        ]
        self.max_question_length = 2000
        self.min_question_length = 3
        
        self.email_pattern = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b')
        self.phone_pattern = re.compile(r'\b\+?\d[\d\-\s]{7,}\d\b')
        self.account_pattern = re.compile(r'\b\d{2,4}[-\s]?\d{3,}[-\s]?\d{2,}\b')
        self.secrets_pattern = re.compile(r'(api[_-]?key|secret|token|password|ssn)\s*[:=]\s*\S+', re.IGNORECASE)
        self.code_fence_pattern = re.compile(r'```(.*?)```', re.DOTALL)
    
    def check_safety(self, question: str) -> Dict[str, Any]:
        if not question or not isinstance(question, str):
            return {
                'safe': False,
                'reason': 'Empty or invalid input',
                'confidence': 1.0
            }
        
        if len(question) < self.min_question_length:
            return {
                'safe': False,
                'reason': 'Question too short',
                'confidence': 1.0
            }
        
        if len(question) > self.max_question_length:
            return {
                'safe': False,
                'reason': 'Question too long',
                'confidence': 1.0
            }
        
        for pattern in self.compiled_patterns:
            if pattern.search(question):
                return {
                    'safe': False,
                    'reason': f'Detected potentially harmful content',
                    'confidence': 0.8
                }
        
        injection_score = self._calculate_injection_score(question)
        if injection_score > 0.5:
            return {
                'safe': False,
                'reason': f'High probability of prompt injection (score: {injection_score:.2f})',
                'confidence': injection_score
            }
        
        return {
            'safe': True,
            'reason': 'Input appears safe',
            'confidence': 0.9
        }
    
    def _calculate_injection_score(self, question: str) -> float:
        score = 0.0
        question_lower = question.lower()
        
        keyword_count = sum(1 for keyword in self.injection_keywords if keyword in question_lower)
        score += min(keyword_count * 0.2, 0.6)
        
        instruction_phrases = [
            'you must', 'you should', 'you will', 'act as', 
            'pretend to', 'roleplay as', 'developer mode', 
            'admin access', 'system prompt'
        ]
        
        instruction_count = sum(1 for phrase in instruction_phrases if phrase in question_lower)
        score += min(instruction_count * 0.25, 0.4)
        
        adversarial_patterns = [
            'ignore previous', 'forget everything', 'override', 
            'bypass', 'jailbreak', 'unrestricted', 'developer mode'
        ]
        
        adversarial_count = sum(1 for pattern in adversarial_patterns if pattern in question_lower)
        score += min(adversarial_count * 0.4, 0.5)
        
        return min(score, 1.0)
    
    def sanitize_user_input(self, text: str) -> str:
        if not text:
            return ""
        text = self._strip_control_phrases(text)
        text = self._literalize_code_blocks(text)
        return text.strip()
    
    def _strip_control_phrases(self, text: str) -> str:
        control_phrases = [
            r'ignore\s+(all\s+)?(previous\s+)?(your\s+)?instructions?',
            r'ignore\s+all\s+previous',
            r'forget\s+(everything|all)\s+(I\s+said|previous)',
            r'reveal\s+(system|hidden|your)\s+prompt',
            r'from\s+now\s+on\s+obey\s+me',
            r'developer\s+mode',
            r'jailbreak',
            r'act\s+as\s+.*?admin'
        ]
        for pattern in control_phrases:
            text = re.sub(pattern, '[blocked-control]', text, flags=re.IGNORECASE)
        return text
    
    def _literalize_code_blocks(self, text: str) -> str:
        def wrap(match):
            code = match.group(1).strip()
            return f"<USER_CODE>\n{code}\n</USER_CODE>"
        return self.code_fence_pattern.sub(wrap, text)
    
    def redact_pii(self, text: str) -> str:
        if not text:
            return ""
        text = self.email_pattern.sub('[redacted-email]', text)
        text = self.phone_pattern.sub('[redacted-phone]', text)
        text = self.account_pattern.sub('[redacted-account]', text)
        text = self.secrets_pattern.sub('[redacted-secret]', text)
        return text
    
    def mask_output(self, text: str) -> Dict[str, Any]:
        safe = self.redact_pii(text)
        has_pii = safe != text
        if has_pii:
            return {
                'action': 'allow-masked',
                'text': safe,
                'severity': 'medium'
            }
        return {
            'action': 'allow',
            'text': safe,
            'severity': 'low'
        }
    
    def anonymize_id(self, identifier: str, salt: str = None) -> str:
        if not salt:
            salt = os.getenv('LOG_SALT', 'static-salt')
        return hashlib.sha256((salt + str(identifier)).encode('utf-8')).hexdigest()
    
    def hash_content(self, content: str) -> str:
        redacted = self.redact_pii(content)
        return hashlib.sha256(redacted.encode('utf-8')).hexdigest()