"""
Main reasoning engine for Enterprise AI agents.
Implements adaptive reasoning flow with pattern selection and reflection.
"""

import asyncio
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.mcp.protocols.mcp_protocol import MCPMessage, MCPMessageType
from enterprise_ai.schema import ToolCall
from enterprise_ai.prompt import react, cot, swe, reflection, planning, browser

logger = get_optimized_logger("agent.reasoning.engine")


class ReasoningPattern(str, Enum):
    """Available reasoning patterns."""
    COT = "chain_of_thought"
    REACT = "react"
    SWE = "software_engineering"
    BROWSER = "browser"
    REFLECTION = "reflection"
    PLANNING = "planning"
    MULTI = "multi_pattern"


class ReasoningEngine:
    """Adaptive reasoning engine for individual agents."""
    
    def __init__(
        self,
        agent,
        max_iterations: int = 10,
        enable_reflection: bool = True,
        enable_planning: bool = True,
        verbose: bool = False
    ):
        self.agent = agent
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection
        self.enable_planning = enable_planning
        self.verbose = verbose
        
        self.current_iteration = 0
        self.reasoning_history: List[Dict[str, Any]] = []
        self.context_analysis: Optional[Dict[str, Any]] = None
        self.selected_patterns: List[ReasoningPattern] = []

    async def process(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Main entry point for reasoning-based task processing."""
        self.current_iteration = 0
        self.reasoning_history = []
        
        try:
            # Step 1: Context Analysis & Reasoning Type Selection
            await self._analyze_context(task, context or {})
            selected_patterns = await self._select_reasoning_patterns(task, self.context_analysis)
            
            # Step 2: Planning (if enabled and needed)
            plan = None
            if self.enable_planning and self._needs_planning():
                plan = await self._create_plan(task, self.context_analysis)
            
            # Step 3: Main reasoning loop
            result = await self._execute_reasoning_loop(task, selected_patterns, plan)
            
            # Step 4: Final reflection (if enabled)
            if self.enable_reflection:
                reflection = await self._final_reflection(result)
                result["reflection"] = reflection
            
            return {
                "success": True,
                "result": result,
                "reasoning_trace": self.reasoning_history,
                "patterns_used": [p.value for p in selected_patterns],
                "iterations": self.current_iteration
            }
            
        except Exception as e:
            logger.error(f"Reasoning process failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "reasoning_trace": self.reasoning_history,
                "iterations": self.current_iteration
            }
    
    async def _analyze_context(self, task: str, context: Dict[str, Any]) -> None:
        """Analyze task context to understand requirements."""
        analysis_prompt = f"""
        Analyze this task and context to understand the requirements:
        
        Task: {task}
        Context: {context}
        
        Determine:
        1. Task complexity (simple/moderate/complex)
        2. Required capabilities (coding, browsing, analysis, etc.)
        3. Expected output type (text, code, analysis, etc.)
        4. Time sensitivity (urgent/normal/extended)
        5. Risk level (low/medium/high)
        
        Provide a brief analysis in JSON format.
        """
        
        messages = [{"role": "user", "content": analysis_prompt}]
        response = await self.agent.llm.acomplete(messages)
        
        try:
            import json
            self.context_analysis = json.loads(response.content)
        except:
            # Fallback to simple analysis
            self.context_analysis = {
                "complexity": "moderate",
                "capabilities": ["general"],
                "output_type": "text",
                "time_sensitivity": "normal",
                "risk_level": "low"
            }

    async def _select_reasoning_patterns(
        self, 
        task: str, 
        analysis: Dict[str, Any]
    ) -> List[ReasoningPattern]:
        """Select optimal reasoning patterns based on task analysis."""
        patterns = []
        
        # Pattern selection logic based on context analysis
        complexity = analysis.get("complexity", "moderate")
        capabilities = analysis.get("capabilities", [])
        output_type = analysis.get("output_type", "text")
        
        # Primary pattern selection
        if "coding" in capabilities or output_type == "code":
            patterns.append(ReasoningPattern.SWE)
        elif "browsing" in capabilities or "research" in capabilities:
            patterns.append(ReasoningPattern.BROWSER)
        elif complexity == "complex":
            patterns.append(ReasoningPattern.COT)
        else:
            patterns.append(ReasoningPattern.REACT)
        
        # Add reflection for learning (if enabled)
        if self.enable_reflection:
            patterns.append(ReasoningPattern.REFLECTION)
        
        self.selected_patterns = patterns
        logger.info(f"Selected reasoning patterns: {[p.value for p in patterns]}")
        
        return patterns
    
    def _needs_planning(self) -> bool:
        """Determine if task needs explicit planning."""
        if not self.context_analysis:
            return False
        
        complexity = self.context_analysis.get("complexity", "moderate")
        return complexity == "complex"
    
    async def _create_plan(self, task: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create a plan for complex tasks."""
        system_prompt = planning.SYSTEM_PROMPT
        planning_prompt = f"""
        Task: {task}
        Analysis: {analysis}
        
        Create a step-by-step plan to accomplish this task.
        Focus on actionable steps and required tools.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": planning_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        
        plan = {
            "steps": response.content,
            "created_at": asyncio.get_event_loop().time()
        }
        
        self.reasoning_history.append({
            "step": "planning",
            "input": task,
            "output": plan,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return plan

    async def _execute_reasoning_loop(
        self,
        task: str,
        patterns: List[ReasoningPattern],
        plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute the main reasoning loop."""
        current_context = task
        if plan:
            current_context += f"\n\nPlan: {plan['steps']}"
        
        final_result = None
        
        for self.current_iteration in range(self.max_iterations):
            # Step 1: Think using primary pattern
            primary_pattern = patterns[0]
            thought = await self._think(current_context, primary_pattern)
            
            # Step 2: Decide on action
            action_decision = await self._decide_action(thought, primary_pattern)
            
            if action_decision.get("action_type") == "complete":
                final_result = action_decision.get("result", thought)
                break
            
            # Step 3: Execute action via MCP
            if action_decision.get("action_type") == "tool_call":
                action_result = await self._execute_action(action_decision)
                
                # Step 4: Observe results
                observation = await self._observe(action_result)
                
                # Step 5: Reflect and adapt (if reflection pattern is active)
                if ReasoningPattern.REFLECTION in patterns:
                    reflection_result = await self._reflect_and_adapt(
                        thought, action_decision, observation
                    )
                    current_context = reflection_result.get("adapted_context", current_context)
                else:
                    current_context = f"{current_context}\n\nObservation: {observation}"
                
                # Record reasoning step
                self.reasoning_history.append({
                    "iteration": self.current_iteration,
                    "thought": thought,
                    "action": action_decision,
                    "observation": observation,
                    "timestamp": asyncio.get_event_loop().time()
                })
            else:
                # No action needed, use thought as result
                final_result = thought
                break
        
        return final_result or current_context

    async def _think(self, context: str, pattern: ReasoningPattern) -> str:
        """Generate thoughts using the specified reasoning pattern."""
        if pattern == ReasoningPattern.COT:
            system_prompt = cot.SYSTEM_PROMPT
            next_prompt = cot.NEXT_STEP_PROMPT
        elif pattern == ReasoningPattern.REACT:
            system_prompt = react.SYSTEM_PROMPT
            next_prompt = react.NEXT_STEP_PROMPT
        elif pattern == ReasoningPattern.SWE:
            system_prompt = swe.SYSTEM_PROMPT
            next_prompt = swe.NEXT_STEP_PROMPT
        elif pattern == ReasoningPattern.BROWSER:
            system_prompt = browser.SYSTEM_PROMPT
            next_prompt = browser.NEXT_STEP_PROMPT
        else:
            # Default to ReAct
            system_prompt = react.SYSTEM_PROMPT
            next_prompt = react.NEXT_STEP_PROMPT
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}\n\n{next_prompt}"}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        return response.content
    
    async def _decide_action(self, thought: str, pattern: ReasoningPattern) -> Dict[str, Any]:
        """Decide what action to take based on thoughts."""
        decision_prompt = f"""
        Based on your thought: {thought}
        
        Decide what to do next:
        1. If you need to use a tool, specify the tool name and arguments
        2. If you have enough information to complete the task, provide the final result
        3. If you need more information, specify what you need
        
        Respond in JSON format:
        {{
            "action_type": "tool_call" | "complete" | "need_info",
            "tool_name": "tool_name_if_applicable",
            "arguments": {{}} if tool_call,
            "result": "final_result_if_complete",
            "reasoning": "why_this_action"
        }}
        """
        
        messages = [{"role": "user", "content": decision_prompt}]
        response = await self.agent.llm.acomplete(messages)
        
        try:
            import json
            return json.loads(response.content)
        except:
            # Fallback decision
            return {
                "action_type": "complete",
                "result": thought,
                "reasoning": "Could not parse action decision"
            }

    async def _execute_action(self, action_decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action via MCP."""
        if action_decision.get("action_type") != "tool_call":
            return {"success": False, "error": "Not a tool call action"}
        
        tool_name = action_decision.get("tool_name")
        arguments = action_decision.get("arguments", {})
        
        if not tool_name:
            return {"success": False, "error": "No tool name specified"}
        
        # Execute via agent's MCP integration
        return await self.agent.execute_tool(tool_name, arguments)
    
    async def _observe(self, action_result: Dict[str, Any]) -> str:
        """Observe and interpret action results."""
        if action_result.get("success", False):
            result_content = action_result.get("result", "Action completed")
            return f"Action successful: {result_content}"
        else:
            error_content = action_result.get("error", "Unknown error")
            return f"Action failed: {error_content}"
    
    async def _reflect_and_adapt(
        self,
        thought: str,
        action: Dict[str, Any],
        observation: str
    ) -> Dict[str, Any]:
        """Reflect on progress and adapt approach."""
        reflection_prompt = f"""
        Reflect on your recent reasoning:
        
        Thought: {thought}
        Action: {action}
        Observation: {observation}
        
        {reflection.NEXT_STEP_PROMPT}
        
        Provide adapted context for next iteration and key insights.
        """
        
        messages = [
            {"role": "system", "content": reflection.SYSTEM_PROMPT},
            {"role": "user", "content": reflection_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        
        return {
            "reflection": response.content,
            "adapted_context": f"Previous reflection: {response.content}\nContinuing with task...",
            "insights": response.content
        }
    
    async def _final_reflection(self, result: Any) -> str:
        """Perform final reflection on the complete reasoning process."""
        history_summary = "\n".join([
            f"Iteration {h.get('iteration', 0)}: {h.get('thought', '')[:100]}..."
            for h in self.reasoning_history[-3:]  # Last 3 iterations
        ])
        
        final_reflection_prompt = f"""
        Reflect on the complete reasoning process:
        
        Recent iterations:
        {history_summary}
        
        Final result: {str(result)[:200]}...
        
        What did you learn? How could the approach be improved?
        What worked well and what didn't?
        """
        
        messages = [
            {"role": "system", "content": reflection.SYSTEM_PROMPT},
            {"role": "user", "content": final_reflection_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        return response.content
