import re
import logging
from typing import Dict, Any

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