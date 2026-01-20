"""
Token Tracker - Track token usage and costs per job application.
Provides detailed breakdown and cost estimation for GPT-4o-mini usage.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()


# GPT-4o-mini pricing (as of Jan 2025)
PRICING = {
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,   # $0.15 per 1M input tokens
        "output": 0.60 / 1_000_000,  # $0.60 per 1M output tokens
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,   # $2.50 per 1M input tokens
        "output": 10.00 / 1_000_000, # $10.00 per 1M output tokens
    }
}


@dataclass
class StepUsage:
    """Token usage for a single automation step."""
    step: int
    input_tokens: int
    output_tokens: int
    action_type: str
    timestamp: datetime = field(default_factory=datetime.now)


class TokenTracker:
    """
    Track token usage and costs for job application automation.
    
    Usage:
        tracker = TokenTracker(model="gpt-4o-mini")
        
        # After each API call
        tracker.record(response, action_type="fill")
        
        # At the end
        tracker.print_summary()
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        """
        Initialize token tracker.
        
        Args:
            model: The OpenAI model being used (for pricing)
        """
        self.model = model
        self.step_usage: List[StepUsage] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.start_time = datetime.now()
    
    def record(self, response, step: int = None, action_type: str = "unknown") -> dict:
        """
        Record token usage from an OpenAI API response.
        
        Args:
            response: OpenAI ChatCompletion response object
            step: Current automation step number
            action_type: Type of action being performed
            
        Returns:
            Current usage summary dict
        """
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        
        # Update totals
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        # Record step usage
        step_num = step if step is not None else len(self.step_usage) + 1
        self.step_usage.append(StepUsage(
            step=step_num,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            action_type=action_type
        ))
        
        return self.get_summary()
    
    def get_summary(self) -> dict:
        """
        Get comprehensive usage summary.
        
        Returns:
            Dictionary with usage statistics and cost estimation
        """
        pricing = PRICING.get(self.model, PRICING["gpt-4o-mini"])
        input_cost = self.total_input_tokens * pricing["input"]
        output_cost = self.total_output_tokens * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "model": self.model,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "estimated_cost_usd": round(total_cost, 6),
            "steps": len(self.step_usage),
            "avg_tokens_per_step": (
                (self.total_input_tokens + self.total_output_tokens) // len(self.step_usage)
                if self.step_usage else 0
            ),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds()
        }
    
    def print_summary(self):
        """Print a formatted summary table to console."""
        summary = self.get_summary()
        
        console.print("\n")
        table = Table(title="📊 Token Usage Summary", border_style="cyan")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Model", summary["model"])
        table.add_row("Total Steps", str(summary["steps"]))
        table.add_row("Input Tokens", f"{summary['input_tokens']:,}")
        table.add_row("Output Tokens", f"{summary['output_tokens']:,}")
        table.add_row("Total Tokens", f"{summary['total_tokens']:,}")
        table.add_row("Avg Tokens/Step", f"{summary['avg_tokens_per_step']:,}")
        table.add_row("Duration", f"{summary['duration_seconds']:.1f}s")
        table.add_row("─" * 15, "─" * 15)
        table.add_row("Input Cost", f"${summary['input_cost_usd']:.4f}")
        table.add_row("Output Cost", f"${summary['output_cost_usd']:.4f}")
        table.add_row("Total Cost", f"${summary['estimated_cost_usd']:.4f}", style="bold green")
        
        console.print(table)
    
    def print_step_breakdown(self):
        """Print detailed per-step breakdown."""
        if not self.step_usage:
            console.print("[dim]No steps recorded yet[/dim]")
            return
        
        table = Table(title="Step-by-Step Breakdown", border_style="blue")
        table.add_column("Step", style="cyan", justify="right")
        table.add_column("Action", style="white")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Total", justify="right")
        
        for step in self.step_usage:
            total = step.input_tokens + step.output_tokens
            table.add_row(
                str(step.step),
                step.action_type,
                str(step.input_tokens),
                str(step.output_tokens),
                str(total)
            )
        
        console.print(table)
    
    def reset(self):
        """Reset all tracking data."""
        self.step_usage = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.start_time = datetime.now()
