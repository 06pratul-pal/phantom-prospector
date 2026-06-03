#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║          PHANTOM PROSPECTOR — AI Lead Gen Agent          ║
║     Fully Autonomous · Built with OpenAI API + Rich      ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import csv
import time
import re
from openai import OpenAI
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.rule import Rule
from rich import box
from tools import web_search_tool, extract_emails_tool, qualify_lead_tool, write_outreach_tool

console = Console()

# ─── Tool Definitions for OpenAI ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web to find potential leads (businesses, people, companies). "
                "Use targeted queries like 'AI agency owners Delhi' or "
                "'digital marketing agencies Mumbai email contact'. Returns list of results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find leads. Be specific and targeted."
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_emails",
            "description": (
                "Visit a webpage URL and extract publicly visible email addresses, "
                "contact info, company name, and person name from that page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to scrape for contact info"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "qualify_lead",
            "description": (
                "Analyze a lead and give it a qualification score from 1-10 "
                "based on relevance to the target criteria."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "url": {"type": "string"},
                    "snippet": {"type": "string"},
                    "target_criteria": {"type": "string", "description": "What we are looking for"}
                },
                "required": ["company_name", "url", "snippet", "target_criteria"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_outreach",
            "description": "Write a personalized outreach email for a qualified lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "contact_name": {"type": "string"},
                    "email": {"type": "string"},
                    "what_they_do": {"type": "string"},
                    "sender_context": {"type": "string"}
                },
                "required": ["company_name", "email", "what_they_do", "sender_context"]
            }
        }
    }
]


# ─── Tool Dispatcher ──────────────────────────────────────────────────────────

def run_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "web_search":
            results = web_search_tool(
                query=tool_input["query"],
                num_results=tool_input.get("num_results", 5)
            )
            return json.dumps(results)
        elif tool_name == "extract_emails":
            result = extract_emails_tool(url=tool_input["url"])
            return json.dumps(result)
        elif tool_name == "qualify_lead":
            result = qualify_lead_tool(
                company_name=tool_input["company_name"],
                url=tool_input["url"],
                snippet=tool_input["snippet"],
                target_criteria=tool_input["target_criteria"]
            )
            return json.dumps(result)
        elif tool_name == "write_outreach":
            result = write_outreach_tool(
                company_name=tool_input["company_name"],
                contact_name=tool_input.get("contact_name", ""),
                email=tool_input["email"],
                what_they_do=tool_input["what_they_do"],
                sender_context=tool_input["sender_context"]
            )
            return json.dumps(result)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Display Helpers ──────────────────────────────────────────────────────────

def display_tool_call(tool_name: str, tool_input: dict):
    icons = {
        "web_search": "🔍",
        "extract_emails": "📧",
        "qualify_lead": "⭐",
        "write_outreach": "✍️ "
    }
    colors = {
        "web_search": "blue",
        "extract_emails": "cyan",
        "qualify_lead": "yellow",
        "write_outreach": "green"
    }
    icon = icons.get(tool_name, "🔧")
    color = colors.get(tool_name, "white")

    if tool_name == "web_search":
        console.print(f"  {icon} [{color}]Searching:[/{color}] [italic]{tool_input.get('query', '')}[/italic]")
    elif tool_name == "extract_emails":
        url = tool_input.get("url", "")[:60]
        console.print(f"  {icon} [{color}]Extracting emails from:[/{color}] [italic]{url}[/italic]")
    elif tool_name == "qualify_lead":
        console.print(f"  {icon} [{color}]Qualifying:[/{color}] [italic]{tool_input.get('company_name', '')}[/italic]")
    elif tool_name == "write_outreach":
        console.print(f"  {icon} [{color}]Writing outreach for:[/{color}] [italic]{tool_input.get('company_name', '')}[/italic]")


def display_tool_result(tool_name: str, result_str: str):
    try:
        result = json.loads(result_str)
        if tool_name == "web_search":
            count = len(result) if isinstance(result, list) else 0
            console.print(f"    [dim]↳ Found {count} results[/dim]")
        elif tool_name == "extract_emails":
            emails = result.get("emails", [])
            if emails:
                console.print(f"    [dim green]↳ Email found: {', '.join(emails[:2])}[/dim green]")
            else:
                console.print(f"    [dim red]↳ No emails found[/dim red]")
        elif tool_name == "qualify_lead":
            score = result.get("score", 0)
            color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
            console.print(f"    [dim {color}]↳ Score: {score}/10 — {result.get('reasoning', '')[:80]}[/dim {color}]")
        elif tool_name == "write_outreach":
            console.print(f"    [dim green]↳ Outreach message written ✓[/dim green]")
    except Exception:
        pass


# ─── Core Agentic Loop ────────────────────────────────────────────────────────

def run_agent(user_query: str, target_leads: int, sender_context: str) -> list:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    system_prompt = f"""You are Phantom Prospector, an elite autonomous lead generation agent.

Your mission: Find {target_leads} high-quality leads based on the user's query.

For each lead you MUST collect:
1. Company/person name
2. Website URL
3. Email address (use extract_emails tool on their website)
4. Qualification score (use qualify_lead tool)
5. Personalized outreach message (use write_outreach tool)

WORKFLOW:
1. Use web_search to find potential leads
2. Use extract_emails on promising URLs to find contact info
3. Use qualify_lead to score the lead (only keep score >= 6)
4. If qualified AND has email, use write_outreach to craft a message
5. Keep searching until you have {target_leads} qualified leads with emails

RULES:
- Only include leads with actual email addresses found
- Skip leads with score < 6
- Use varied search queries to find diverse leads
- After collecting all leads, output a JSON summary in this EXACT format:

```json
{{
  "leads": [
    {{
      "company_name": "...",
      "contact_name": "...",
      "email": "...",
      "url": "...",
      "score": 8,
      "what_they_do": "...",
      "outreach_message": "..."
    }}
  ],
  "total_found": 5,
  "summary": "Brief summary of what was found"
}}
```

Sender context for outreach: {sender_context}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    leads_found = []
    iteration = 0
    max_iterations = 30

    console.print()
    console.print(Rule("[bold purple]🤖 Agent Starting[/bold purple]"))
    console.print()

    while iteration < max_iterations:
        iteration += 1

        with console.status(f"[cyan]Agent thinking... (iteration {iteration})[/cyan]", spinner="dots"):
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=4096
            )

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Add assistant message to history
        messages.append(message)

        # Check for text content
        if message.content and message.content.strip():
            text = message.content.strip()
            if '"leads"' in text or "```json" in text:
                leads_found = parse_final_output(text)
                if leads_found:
                    console.print()
                    console.print(Rule("[bold green]✅ Agent Complete[/bold green]"))
                    return leads_found
            else:
                if text:
                    console.print(f"[dim italic]Agent: {text[:200]}[/dim italic]")

        # Handle tool calls
        if message.tool_calls:
            tool_results = []
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except Exception:
                    tool_input = {}

                display_tool_call(tool_name, tool_input)
                result = run_tool(tool_name, tool_input)
                display_tool_result(tool_name, result)

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

            messages.extend(tool_results)

        # No tool calls + end → done
        if finish_reason == "stop" and not message.tool_calls:
            console.print("[yellow]Agent finished. Extracting results...[/yellow]")
            break

    return leads_found


def parse_final_output(text: str) -> list:
    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
        else:
            json_match = re.search(r'\{.*"leads".*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                return []
        return data.get("leads", [])
    except Exception as e:
        console.print(f"[red]Could not parse final output: {e}[/red]")
        return []


# ─── Results Display ──────────────────────────────────────────────────────────

def display_results_table(leads: list):
    console.print()
    console.print(Rule("[bold green]📊 LEADS FOUND[/bold green]"))
    console.print()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold purple",
                  border_style="dim", expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Company", style="bold", min_width=20)
    table.add_column("Email", style="cyan", min_width=25)
    table.add_column("Score", justify="center", width=7)
    table.add_column("URL", style="dim", min_width=25)

    for i, lead in enumerate(leads, 1):
        score = lead.get("score", 0)
        score_color = "green" if score >= 8 else "yellow" if score >= 6 else "red"
        url = lead.get("url", "")
        url_display = url[:40] + "..." if len(url) > 40 else url
        table.add_row(
            str(i),
            lead.get("company_name", "Unknown"),
            lead.get("email", "N/A"),
            f"[{score_color}]{score}/10[/{score_color}]",
            url_display
        )
    console.print(table)


def show_outreach_preview(leads: list):
    console.print()
    console.print(Rule("[bold cyan]✉️  OUTREACH MESSAGES PREVIEW[/bold cyan]"))
    for lead in leads[:3]:
        msg = lead.get("outreach_message", "")
        if msg:
            console.print()
            console.print(Panel(
                msg,
                title=f"[bold]{lead.get('company_name', 'Lead')}[/bold] — {lead.get('email', '')}",
                border_style="cyan", padding=(1, 2)
            ))
    if len(leads) > 3:
        console.print(f"\n  [dim]...and {len(leads) - 3} more in the CSV file.[/dim]")


def save_to_csv(leads: list, filename: str):
    fieldnames = ["company_name", "contact_name", "email", "url",
                  "score", "what_they_do", "outreach_message"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow({field: lead.get(field, "") for field in fieldnames})
    console.print(f"\n  [bold green]✅ CSV saved:[/bold green] [cyan]{filename}[/cyan]")


# ─── Banner ───────────────────────────────────────────────────────────────────

def show_banner():
    console.print(Panel(
        "[bold purple]👻  PHANTOM PROSPECTOR[/bold purple]\n\n"
        "[dim]Autonomous AI Lead Generation Agent · Powered by GPT-4o[/dim]",
        border_style="purple", padding=(1, 4)
    ))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    show_banner()
    console.print()

    if not os.environ.get("OPENAI_API_KEY"):
        console.print(Panel(
            "[red]❌ OPENAI_API_KEY not found!\n\n"
            "Set it with:\n"
            "[cyan]CMD:[/cyan]        set OPENAI_API_KEY=your-key-here\n"
            "[cyan]PowerShell:[/cyan] $env:OPENAI_API_KEY='your-key-here'[/red]",
            border_style="red"
        ))
        sys.exit(1)

    console.print("[bold cyan]Step 1 — Who are you looking for?[/bold cyan]")
    console.print("[dim]Example: 'AI agency owners in Delhi', 'SaaS startups in Bangalore'[/dim]")
    user_query = Prompt.ask("\n[bold]→ Your target[/bold]")

    console.print()
    console.print("[bold cyan]Step 2 — How many leads?[/bold cyan]")
    target_leads_str = Prompt.ask("[bold]→ Number of leads[/bold]", default="5")
    try:
        target_leads = int(target_leads_str)
    except ValueError:
        target_leads = 5

    console.print()
    console.print("[bold cyan]Step 3 — Who is reaching out?[/bold cyan]")
    console.print("[dim]Example: 'freelance AI developer offering automation services'[/dim]")
    sender_context = Prompt.ask("[bold]→ About you[/bold]", default="an AI automation consultant")

    console.print()
    console.print(Panel(
        f"[bold]Target:[/bold] {user_query}\n"
        f"[bold]Leads wanted:[/bold] {target_leads}\n"
        f"[bold]Sender:[/bold] {sender_context}",
        title="[bold purple]Mission Briefing[/bold purple]", border_style="purple"
    ))
    console.print()

    start = Prompt.ask("[bold]Ready to launch?[/bold]", choices=["yes", "no"], default="yes")
    if start.lower() != "yes":
        console.print("[yellow]Aborted.[/yellow]")
        sys.exit(0)

    start_time = time.time()
    leads = run_agent(
        user_query=f"Find {target_leads} leads: {user_query}. Sender context: {sender_context}",
        target_leads=target_leads,
        sender_context=sender_context
    )
    elapsed = time.time() - start_time

    if not leads:
        console.print(Panel(
            "[red]No leads collected. Try a different query or check your API key.[/red]",
            border_style="red"
        ))
        sys.exit(1)

    display_results_table(leads)
    show_outreach_preview(leads)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"leads_{timestamp}.csv"
    save_to_csv(leads, csv_filename)

    console.print()
    console.print(Panel(
        f"[bold green]✅ Mission Complete![/bold green]\n\n"
        f"  🎯 Leads found:  [bold]{len(leads)}[/bold]\n"
        f"  ⏱️  Time taken:   [bold]{elapsed:.1f}s[/bold]\n"
        f"  📁 Saved to:     [cyan]{csv_filename}[/cyan]",
        border_style="green", title="[bold green]Summary[/bold green]"
    ))


if __name__ == "__main__":
    main()
