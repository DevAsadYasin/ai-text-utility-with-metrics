#!/usr/bin/env python3
import os
import json
import time
import csv
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextUtility:
    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.safety_checker = self._init_safety_checker()
        self.metrics_file = Path("metrics/metrics.csv")
        self.prompt_template = self._load_prompt_template()
        self.ai_clients = self._initialize_ai_providers()
        
        self.metrics_file.parent.mkdir(exist_ok=True)
        if not self.metrics_file.exists():
            self._init_metrics_file()
    
    def _init_safety_checker(self):
        try:
            from safety import SafetyChecker
            return SafetyChecker()
        except ImportError:
            logger.warning("Safety module not found, using basic safety checks")
            return None
    
    def _load_prompt_template(self) -> str:
        prompt_file = Path("prompts/main_prompt.txt")
        if prompt_file.exists():
            return prompt_file.read_text()
        return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        return """You are a helpful customer support assistant. For any user question, provide a structured response in the following JSON format:

{{
    "answer": "A clear, concise answer to the user's question",
    "confidence": 0.85,
    "actions": ["action1", "action2"],
    "category": "technical|billing|general|other",
    "follow_up": "Optional follow-up question or clarification needed"
}}

User Question: {{question}}

Respond with ONLY the JSON object, no additional text."""

    def _init_metrics_file(self):
        with open(self.metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'question', 'provider', 'tokens_prompt', 'tokens_completion', 
                'total_tokens', 'latency_ms', 'estimated_cost_usd', 'safety_check_passed'
            ])
    
    def _initialize_ai_providers(self) -> Dict[str, Any]:
        clients = {}
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            try:
                from openai import OpenAI
                clients['openai'] = OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")
        
        gemini_key = os.getenv('GEMINI_API_KEY')
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                clients['gemini'] = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Gemini provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        
        openrouter_key = os.getenv('OPENROUTER_API_KEY')
        if openrouter_key:
            try:
                from openai import OpenAI as OpenRouterClient
                clients['openrouter'] = OpenRouterClient(
                    api_key=openrouter_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                logger.info("OpenRouter client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter: {e}")
        
        if not clients:
            logger.warning("No AI providers available!")
        else:
            logger.info(f"Available providers: {', '.join(clients.keys())}")
        
        return clients
    
    def _calculate_cost(self, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = {
            'openai': {
                'prompt': 0.001,
                'completion': 0.002
            },
            'gemini': {
                'prompt': 0.075 / 1000,
                'completion': 0.30 / 1000
            },
            'openrouter': {
                'prompt': 0.0005,  # Average across models
                'completion': 0.0015
            }
        }
        
        p = pricing.get(provider, pricing['openrouter'])
        prompt_cost = (prompt_tokens / 1000) * p['prompt']
        completion_cost = (completion_tokens / 1000) * p['completion']
        
        return prompt_cost + completion_cost
    
    def _log_metrics(self, question: str, provider: str, prompt_tokens: int, 
                    completion_tokens: int, latency_ms: float, safety_passed: bool):
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = self._calculate_cost(provider, prompt_tokens, completion_tokens)
        
        with open(self.metrics_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                question[:100],
                provider,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                round(latency_ms, 2),
                round(estimated_cost, 4),
                safety_passed
            ])
    
    def _safety_check(self, question: str) -> Dict[str, Any]:
        if self.safety_checker:
            return self.safety_checker.check_safety(question)
        else:
            if not question or len(question.strip()) < 3:
                return {'safe': False, 'reason': 'Empty or too short'}
            if len(question) > 2000:
                return {'safe': False, 'reason': 'Too long'}
            return {'safe': True, 'reason': 'Passed basic checks'}
    
    def _choose_provider(self) -> Optional[str]:
        if self.provider == "openai" and "openai" in self.ai_clients:
            return "openai"
        elif self.provider == "gemini" and "gemini" in self.ai_clients:
            return "gemini"
        elif self.provider == "openrouter" and "openrouter" in self.ai_clients:
            return "openrouter"
        elif self.provider == "auto":
            if "openrouter" in self.ai_clients:
                return "openrouter"
            elif "gemini" in self.ai_clients:
                return "gemini"
            elif "openai" in self.ai_clients:
                return "openai"
        
        return None
    
    def _call_ai_provider(self, provider: str, formatted_prompt: str) -> Dict[str, Any]:
        try:
            if provider == "openai":
                return self._call_openai(formatted_prompt)
            elif provider == "gemini":
                return self._call_gemini(formatted_prompt)
            elif provider == "openrouter":
                return self._call_openrouter(formatted_prompt)
            else:
                return {
                    'success': False,
                    'error': f'Unknown provider: {provider}',
                    'content': None,
                    'tokens_prompt': 0,
                    'tokens_completion': 0
                }
        except Exception as e:
            logger.error(f"Error calling {provider}: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None,
                'tokens_prompt': 0,
                'tokens_completion': 0
            }
    
    def _call_openai(self, formatted_prompt: str) -> Dict[str, Any]:
        response = self.ai_clients['openai'].chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that responds only with valid JSON."},
                {"role": "user", "content": formatted_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        usage = response.usage
        
        return {
            'success': True,
            'content': content,
            'tokens_prompt': usage.prompt_tokens,
            'tokens_completion': usage.completion_tokens
        }
    
    def _call_gemini(self, formatted_prompt: str) -> Dict[str, Any]:
        response = self.ai_clients['gemini'].generate_content(
            formatted_prompt,
            generation_config={
                'temperature': 0.3,
                'max_output_tokens': 500
            }
        )
        
        content = response.text.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        tokens_prompt = max(1, len(formatted_prompt) // 3.5)
        tokens_completion = max(1, len(content) // 3.5)
        
        return {
            'success': True,
            'content': content,
            'tokens_prompt': tokens_prompt,
            'tokens_completion': tokens_completion
        }
    
    def _call_openrouter(self, formatted_prompt: str) -> Dict[str, Any]:
        response = self.ai_clients['openrouter'].chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that responds only with valid JSON."},
                {"role": "user", "content": formatted_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()
        
        tokens_prompt = max(1, len(formatted_prompt) // 3.5)
        tokens_completion = max(1, len(content) // 3.5)
        
        return {
            'success': True,
            'content': content,
            'tokens_prompt': tokens_prompt,
            'tokens_completion': tokens_completion
        }
    
    def process_query(self, question: str) -> Dict[str, Any]:
        logger.info(f"Processing query: {question[:50]}...")
        safety_result = self._safety_check(question)
        if not safety_result['safe']:
            logger.warning(f"Safety check failed: {safety_result['reason']}")
            return {
                'answer': 'I cannot process this request',
                'confidence': 1.0,
                'actions': ['Please rephrase your question'],
                'category': 'other',
                'follow_up': None,
                'safety_warning': safety_result['reason'],
                'metrics': {
                    'tokens_prompt': 0,
                    'tokens_completion': 0,
                    'total_tokens': 0,
                    'latency_ms': 0,
                    'estimated_cost_usd': 0.0
                }
            }
        
        provider = self._choose_provider()
        if not provider:
            return {
                'answer': 'No AI provider available. Please configure API keys.',
                'confidence': 0.0,
                'actions': ['Check your API key configuration'],
                'category': 'other',
                'follow_up': None,
                'error': 'No AI provider available',
                'metrics': {
                    'tokens_prompt': 0,
                    'tokens_completion': 0,
                    'total_tokens': 0,
                    'latency_ms': 0,
                    'estimated_cost_usd': 0.0
                }
            }
        
        formatted_prompt = self.prompt_template.format(question=question)
        start_time = time.time()
        api_result = self._call_ai_provider(provider, formatted_prompt)
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        if not api_result['success']:
            logger.error(f"API call failed: {api_result['error']}")
            return {
                'answer': f'Error processing request: {api_result["error"]}',
                'confidence': 0.0,
                'actions': ['Please try again later'],
                'category': 'other',
                'follow_up': None,
                'error': api_result['error'],
                'metrics': {
                    'tokens_prompt': 0,
                    'tokens_completion': 0,
                    'total_tokens': 0,
                    'latency_ms': latency_ms,
                    'estimated_cost_usd': 0.0
                }
            }
        
        try:
            json_response = json.loads(api_result['content'])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            json_response = {
                'answer': 'Error parsing response',
                'confidence': 0.0,
                'actions': ['Please try again'],
                'category': 'other',
                'follow_up': None
            }
        
        self._log_metrics(question, provider, api_result['tokens_prompt'], 
                         api_result['tokens_completion'], latency_ms, True)
        
        json_response['metrics'] = {
            'tokens_prompt': api_result['tokens_prompt'],
            'tokens_completion': api_result['tokens_completion'],
            'total_tokens': api_result['tokens_prompt'] + api_result['tokens_completion'],
            'latency_ms': round(latency_ms, 2),
            'estimated_cost_usd': round(self._calculate_cost(provider, api_result['tokens_prompt'], 
                                                            api_result['tokens_completion']), 4),
            'provider': provider
        }
        
        logger.info(f"Query processed with {provider}. Tokens: {api_result['tokens_prompt'] + api_result['tokens_completion']}, Latency: {latency_ms:.2f}ms")
        return json_response

def main():
    openai_key = os.getenv('OPENAI_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    if not any([openai_key, gemini_key, openrouter_key]):
        print("Error: No AI provider API keys found")
        print("Please set at least one of:")
        print("  export OPENAI_API_KEY='your-openai-key'")
        print("  export GEMINI_API_KEY='your-gemini-key'")
        print("  export OPENROUTER_API_KEY='your-openrouter-key'")
        return
    
    utility = TextUtility(provider="auto")
    print("Multi-Task Text Utility")
    print("Type 'quit' to exit")
    print("-" * 40)
    
    while True:
        question = input("\nEnter your question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            break
        
        if not question:
            continue
        
        result = utility.process_query(question)
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        
        if 'metrics' in result:
            metrics = result['metrics']
            print(f"\nMetrics:")
            print(f"  Provider: {metrics.get('provider', 'unknown')}")
            print(f"  Tokens: {metrics['total_tokens']} (prompt: {metrics['tokens_prompt']}, completion: {metrics['tokens_completion']})")
            print(f"  Latency: {metrics['latency_ms']}ms")
            print(f"  Estimated Cost: ${metrics['estimated_cost_usd']:.4f}")

if __name__ == "__main__":
    main()
