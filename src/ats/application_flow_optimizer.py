#!/usr/bin/env python3
"""
Application Flow Optimizer
Optimizes the job application process with intelligent routing, pre-filling,
and adaptive strategies based on ATS detection and success patterns.
"""

import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from rich.console import Console

from src.utils.enhanced_error_tolerance import with_retry, safe_execute
from src.core.job_database import get_job_db

console = Console()

@dataclass
class ApplicationMetrics:
    """Metrics for tracking application performance."""
    total_attempts: int = 0
    successful_applications: int = 0
    failed_applications: int = 0
    manual_reviews_required: int = 0
    average_application_time: float = 0.0
    ats_detection_accuracy: float = 0.0
    form_prefill_success_rate: float = 0.0

class ApplicationFlowOptimizer:
    """
    Optimizes job application flow with intelligent ATS detection,
    form pre-filling, and adaptive strategies.
    """
    
    def __init__(self, profile_name: str):
        """
        Initialize the application flow optimizer.
        
        Args:
            profile_name: Name of the user profile
        """
        self.profile_name = profile_name
        self.db = get_job_db(profile_name)
        self.metrics = ApplicationMetrics()
        
        # Load optimization data
        self.ats_patterns = self._load_ats_patterns()
        self.form_field_mappings = self._load_form_mappings()
        self.success_patterns = self._load_success_patterns()
        
        # Application strategies
        self.strategies = {
            'workday': self._apply_workday_strategy,
            'greenhouse': self._apply_greenhouse_strategy,
            'lever': self._apply_lever_strategy,
            'bamboohr': self._apply_bamboohr_strategy,
            'generic': self._apply_generic_strategy
        }
    
    def _load_ats_patterns(self) -> Dict:
        """Load ATS detection patterns."""
        patterns = {
            'workday': {
                'url_patterns': ['workday.com', 'myworkday.com', 'wd1.myworkdayjobs.com'],
                'dom_selectors': ['[data-automation-id]', '.css-1hwfws3', '.workday'],
                'text_indicators': ['workday', 'powered by workday'],
                'form_patterns': ['input[data-automation-id]']
            },
            'greenhouse': {
                'url_patterns': ['greenhouse.io', 'boards.greenhouse.io'],
                'dom_selectors': ['.application-form', '.greenhouse-form'],
                'text_indicators': ['greenhouse', 'powered by greenhouse'],
                'form_patterns': ['input[name*="application"]']
            },
            'lever': {
                'url_patterns': ['lever.co', 'jobs.lever.co'],
                'dom_selectors': ['.application-form', '.lever-form'],
                'text_indicators': ['lever', 'powered by lever'],
                'form_patterns': ['input[name*="lever"]']
            },
            'bamboohr': {
                'url_patterns': ['bamboohr.com', 'bamboohr.co'],
                'dom_selectors': ['.bamboo-form', '.application-container'],
                'text_indicators': ['bamboohr', 'bamboo hr'],
                'form_patterns': ['input[name*="bamboo"]']
            }
        }
        return patterns
    
    def _load_form_mappings(self) -> Dict:
        """Load form field mappings for different ATS systems."""
        mappings = {
            'workday': {
                'first_name': ['input[data-automation-id*="firstName"]', 'input[name*="firstName"]'],
                'last_name': ['input[data-automation-id*="lastName"]', 'input[name*="lastName"]'],
                'email': ['input[data-automation-id*="email"]', 'input[type="email"]'],
                'phone': ['input[data-automation-id*="phone"]', 'input[type="tel"]'],
                'resume': ['input[data-automation-id*="resume"]', 'input[type="file"]'],
                'cover_letter': ['input[data-automation-id*="coverLetter"]']
            },
            'greenhouse': {
                'first_name': ['input[name*="first_name"]', '#first_name'],
                'last_name': ['input[name*="last_name"]', '#last_name'],
                'email': ['input[name*="email"]', '#email'],
                'phone': ['input[name*="phone"]', '#phone'],
                'resume': ['input[name*="resume"]', 'input[type="file"]'],
                'cover_letter': ['input[name*="cover_letter"]']
            },
            'generic': {
                'first_name': ['input[name*="first"]', '#firstName', '#first_name'],
                'last_name': ['input[name*="last"]', '#lastName', '#last_name'],
                'email': ['input[type="email"]', '#email', 'input[name*="email"]'],
                'phone': ['input[type="tel"]', '#phone', 'input[name*="phone"]'],
                'resume': ['input[type="file"]', 'input[name*="resume"]'],
                'cover_letter': ['input[name*="cover"]', 'input[name*="letter"]']
            }
        }
        return mappings
    
    def _load_success_patterns(self) -> Dict:
        """Load patterns that indicate successful applications."""
        return {
            'success_indicators': [
                'application submitted',
                'thank you for applying',
                'application received',
                'we have received your application',
                'application complete',
                'successfully submitted'
            ],
            'failure_indicators': [
                'error occurred',
                'please try again',
                'required field',
                'invalid format',
                'file too large',
                'unsupported file type'
            ],
            'manual_review_indicators': [
                'captcha',
                'verify you are human',
                'security check',
                'additional information required',
                'please complete',
                'screening questions'
            ]
        }
    
    @with_retry(operation_name="detect_ats", max_retries=2)
    def detect_ats_system(self, page, job_url: str) -> Tuple[str, float]:
        """
        Detect the ATS system being used with confidence score.
        
        Args:
            page: Playwright page object
            job_url: URL of the job posting
            
        Returns:
            Tuple of (ats_name, confidence_score)
        """
        try:
            # URL-based detection
            for ats_name, patterns in self.ats_patterns.items():
                for url_pattern in patterns['url_patterns']:
                    if url_pattern in job_url.lower():
                        console.print(f"[green]🎯 ATS detected by URL: {ats_name}[/green]")
                        return ats_name, 0.9
            
            # DOM-based detection
            page_content = safe_execute(lambda: page.content(), default_return="")
            
            for ats_name, patterns in self.ats_patterns.items():
                confidence = 0.0
                
                # Check DOM selectors
                for selector in patterns['dom_selectors']:
                    try:
                        elements = page.query_selector_all(selector)
                        if elements:
                            confidence += 0.3
                    except:
                        continue
                
                # Check text indicators
                for indicator in patterns['text_indicators']:
                    if indicator.lower() in page_content.lower():
                        confidence += 0.2
                
                # Check form patterns
                for form_pattern in patterns['form_patterns']:
                    try:
                        form_elements = page.query_selector_all(form_pattern)
                        if form_elements:
                            confidence += 0.2
                    except:
                        continue
                
                if confidence >= 0.6:
                    console.print(f"[green]🎯 ATS detected by DOM analysis: {ats_name} (confidence: {confidence:.2f})[/green]")
                    return ats_name, confidence
            
            # Fallback to generic
            console.print("[yellow]⚠️ No specific ATS detected, using generic strategy[/yellow]")
            return 'generic', 0.3
            
        except Exception as e:
            console.print(f"[red]❌ ATS detection failed: {e}[/red]")
            return 'generic', 0.1
    
    @with_retry(operation_name="optimize_application", max_retries=1)
    def optimize_application_flow(self, 
                                 job: Dict, 
                                 profile: Dict, 
                                 page) -> Dict:
        """
        Optimize the application flow for a specific job.
        
        Args:
            job: Job dictionary
            profile: User profile dictionary
            page: Playwright page object
            
        Returns:
            Dictionary with application results and metrics
        """
        start_time = time.time()
        
        console.print(f"\n[bold blue]🚀 Optimizing application for: {job.get('title', 'Unknown')}[/bold blue]")
        
        # Detect ATS system
        ats_system, confidence = self.detect_ats_system(page, job.get('url', ''))
        
        # Get appropriate strategy
        strategy_func = self.strategies.get(ats_system, self.strategies['generic'])
        
        # Execute application strategy
        try:
            result = strategy_func(job, profile, page, confidence)
            
            # Calculate metrics
            duration = time.time() - start_time
            result['application_duration'] = duration
            result['ats_system'] = ats_system
            result['ats_confidence'] = confidence
            
            # Update metrics
            self._update_application_metrics(result)
            
            return result
            
        except Exception as e:
            console.print(f"[red]❌ Application optimization failed: {e}[/red]")
            return {
                'status': 'failed',
                'error': str(e),
                'ats_system': ats_system,
                'ats_confidence': confidence,
                'application_duration': time.time() - start_time
            }
    
    def _apply_workday_strategy(self, job: Dict, profile: Dict, page, confidence: float) -> Dict:
        """Apply Workday-specific application strategy."""
        console.print("[cyan]🔧 Applying Workday strategy[/cyan]")
        
        try:
            # Workday-specific form filling
            mappings = self.form_field_mappings['workday']
            filled_fields = self._fill_form_fields(page, profile, mappings)
            
            # Handle Workday-specific elements
            self._handle_workday_specifics(page, profile)
            
            return {
                'status': 'applied',
                'strategy': 'workday',
                'fields_filled': filled_fields,
                'confidence': confidence
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'strategy': 'workday',
                'error': str(e),
                'confidence': confidence
            }
    
    def _apply_greenhouse_strategy(self, job: Dict, profile: Dict, page, confidence: float) -> Dict:
        """Apply Greenhouse-specific application strategy."""
        console.print("[cyan]🔧 Applying Greenhouse strategy[/cyan]")
        
        try:
            # Greenhouse-specific form filling
            mappings = self.form_field_mappings['greenhouse']
            filled_fields = self._fill_form_fields(page, profile, mappings)
            
            return {
                'status': 'applied',
                'strategy': 'greenhouse',
                'fields_filled': filled_fields,
                'confidence': confidence
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'strategy': 'greenhouse',
                'error': str(e),
                'confidence': confidence
            }
    
    def _apply_lever_strategy(self, job: Dict, profile: Dict, page, confidence: float) -> Dict:
        """Apply Lever-specific application strategy."""
        console.print("[cyan]🔧 Applying Lever strategy[/cyan]")
        
        try:
            # Lever-specific form filling
            mappings = self.form_field_mappings.get('lever', self.form_field_mappings['generic'])
            filled_fields = self._fill_form_fields(page, profile, mappings)
            
            return {
                'status': 'applied',
                'strategy': 'lever',
                'fields_filled': filled_fields,
                'confidence': confidence
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'strategy': 'lever',
                'error': str(e),
                'confidence': confidence
            }
    
    def _apply_bamboohr_strategy(self, job: Dict, profile: Dict, page, confidence: float) -> Dict:
        """Apply BambooHR-specific application strategy."""
        console.print("[cyan]🔧 Applying BambooHR strategy[/cyan]")
        
        try:
            # BambooHR-specific form filling
            mappings = self.form_field_mappings.get('bamboohr', self.form_field_mappings['generic'])
            filled_fields = self._fill_form_fields(page, profile, mappings)
            
            return {
                'status': 'applied',
                'strategy': 'bamboohr',
                'fields_filled': filled_fields,
                'confidence': confidence
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'strategy': 'bamboohr',
                'error': str(e),
                'confidence': confidence
            }
    
    def _apply_generic_strategy(self, job: Dict, profile: Dict, page, confidence: float) -> Dict:
        """Apply generic application strategy."""
        console.print("[cyan]🔧 Applying generic strategy[/cyan]")
        
        try:
            # Generic form filling
            mappings = self.form_field_mappings['generic']
            filled_fields = self._fill_form_fields(page, profile, mappings)
            
            return {
                'status': 'applied',
                'strategy': 'generic',
                'fields_filled': filled_fields,
                'confidence': confidence
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'strategy': 'generic',
                'error': str(e),
                'confidence': confidence
            }

    def _fill_form_fields(self, page, profile: Dict, mappings: Dict) -> Dict:
        """Fill form fields using the provided mappings."""
        filled_fields = {}

        # Basic profile data
        profile_data = {
            'first_name': profile.get('first_name', ''),
            'last_name': profile.get('last_name', ''),
            'email': profile.get('email', 'Nirajan.tech@gmail.com'),
            'phone': profile.get('phone', ''),
        }

        for field_name, selectors in mappings.items():
            if field_name in profile_data:
                value = profile_data[field_name]
                if value:
                    success = self._try_fill_field(page, selectors, value)
                    if success:
                        filled_fields[field_name] = value
                        console.print(f"[green]✅ Filled {field_name}: {value}[/green]")
                    else:
                        console.print(f"[yellow]⚠️ Could not fill {field_name}[/yellow]")

        return filled_fields

    def _try_fill_field(self, page, selectors: List[str], value: str) -> bool:
        """Try to fill a field using multiple selectors."""
        for selector in selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    # Check if field is empty before filling
                    current_value = safe_execute(lambda: element.input_value(), default_return="")
                    if not current_value:
                        element.fill(value)
                        return True
            except Exception:
                continue
        return False

    def _handle_workday_specifics(self, page, profile: Dict):
        """Handle Workday-specific elements and interactions."""
        try:
            # Handle Workday's multi-step form process
            # Look for "Next" or "Continue" buttons
            next_buttons = [
                'button[data-automation-id*="next"]',
                'button[data-automation-id*="continue"]',
                'button:has-text("Next")',
                'button:has-text("Continue")'
            ]

            for selector in next_buttons:
                try:
                    button = page.query_selector(selector)
                    if button and button.is_visible():
                        console.print("[cyan]🔄 Clicking Workday next button[/cyan]")
                        button.click()
                        page.wait_for_timeout(2000)  # Wait for page to load
                        break
                except Exception:
                    continue

        except Exception as e:
            console.print(f"[yellow]⚠️ Workday-specific handling failed: {e}[/yellow]")

    def _update_application_metrics(self, result: Dict):
        """Update application metrics based on result."""
        self.metrics.total_attempts += 1

        status = result.get('status', 'unknown')
        if status == 'applied':
            self.metrics.successful_applications += 1
        elif status == 'failed':
            self.metrics.failed_applications += 1
        elif status == 'manual_review':
            self.metrics.manual_reviews_required += 1

        # Update average application time
        duration = result.get('application_duration', 0)
        if duration > 0:
            total_time = self.metrics.average_application_time * (self.metrics.total_attempts - 1)
            self.metrics.average_application_time = (total_time + duration) / self.metrics.total_attempts

        # Update ATS detection accuracy
        confidence = result.get('ats_confidence', 0)
        if confidence > 0:
            total_confidence = self.metrics.ats_detection_accuracy * (self.metrics.total_attempts - 1)
            self.metrics.ats_detection_accuracy = (total_confidence + confidence) / self.metrics.total_attempts

        # Update form prefill success rate
        fields_filled = result.get('fields_filled', {})
        if fields_filled:
            success_rate = len(fields_filled) / max(len(self.form_field_mappings['generic']), 1)
            total_prefill = self.metrics.form_prefill_success_rate * (self.metrics.total_attempts - 1)
            self.metrics.form_prefill_success_rate = (total_prefill + success_rate) / self.metrics.total_attempts

    def get_optimization_summary(self) -> Dict:
        """Get summary of application optimization performance."""
        if self.metrics.total_attempts == 0:
            return {"message": "No applications attempted yet"}

        success_rate = (self.metrics.successful_applications / self.metrics.total_attempts) * 100

        return {
            "total_attempts": self.metrics.total_attempts,
            "successful_applications": self.metrics.successful_applications,
            "failed_applications": self.metrics.failed_applications,
            "manual_reviews_required": self.metrics.manual_reviews_required,
            "success_rate_percent": round(success_rate, 1),
            "average_application_time_seconds": round(self.metrics.average_application_time, 1),
            "ats_detection_accuracy": round(self.metrics.ats_detection_accuracy, 2),
            "form_prefill_success_rate": round(self.metrics.form_prefill_success_rate, 2)
        }

    def save_optimization_data(self):
        """Save optimization data for future use."""
        try:
            data_dir = Path("output") / "optimization_data"
            data_dir.mkdir(parents=True, exist_ok=True)

            data_file = data_dir / f"{self.profile_name}_optimization.json"

            optimization_data = {
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "total_attempts": self.metrics.total_attempts,
                    "successful_applications": self.metrics.successful_applications,
                    "failed_applications": self.metrics.failed_applications,
                    "manual_reviews_required": self.metrics.manual_reviews_required,
                    "average_application_time": self.metrics.average_application_time,
                    "ats_detection_accuracy": self.metrics.ats_detection_accuracy,
                    "form_prefill_success_rate": self.metrics.form_prefill_success_rate
                },
                "ats_patterns": self.ats_patterns,
                "form_field_mappings": self.form_field_mappings,
                "success_patterns": self.success_patterns
            }

            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(optimization_data, f, indent=2)

            console.print(f"[green]💾 Optimization data saved to {data_file}[/green]")

        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to save optimization data: {e}[/yellow]")

# Convenience function for easy integration
def optimize_job_application(profile_name: str, job: Dict, profile: Dict, page) -> Dict:
    """
    Optimize a job application using the flow optimizer.

    Args:
        profile_name: Name of the user profile
        job: Job dictionary
        profile: User profile dictionary
        page: Playwright page object

    Returns:
        Dictionary with application results
    """
    optimizer = ApplicationFlowOptimizer(profile_name)
    result = optimizer.optimize_application_flow(job, profile, page)
    optimizer.save_optimization_data()
    return result
