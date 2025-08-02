"""
Enterprise AI Agent - MetaCognitive Reasoning Engine

Natural human-like reasoning with planning, execution, monitoring, and reflection.
Integrates planning and terminate tools for sophisticated reasoning flow.
"""

from typing import List, Optional, Dict, Any, AsyncIterator, Tuple
from enum import Enum

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.agent.config import MAX_REACT_ITERATIONS
from enterprise_ai.schema import Message, ToolCall
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.metacognitive")


class ReasoningPhase(Enum):
    """Phases of metacognitive reasoning."""
    PLANNING = "planning"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    DECISION = "decision"
    REFLECTION = "reflection"
    TERMINATION = "termination"


class MetaCognitiveEngine:
    """
    Meta-cognitive reasoning engine with natural human-like reasoning flow.
    
    Phases:
    1. PLANNING: Break down task using planning tool
    2. EXECUTION: Execute steps with explicit thought/action/observation
    3. MONITORING: Check progress, update plan status
    4. DECISION: Decide next action (continue/re-plan/terminate)
    5. REFLECTION: Learn from results and adapt
    6. TERMINATION: Complete with success/failure status
    """
    
    def __init__(self):
        """Initialize the metacognitive engine."""
        self.llm = None
        self.mcp = None
        self.verbose = False
        self.current_phase = ReasoningPhase.PLANNING
        self.task_plan_id = None
        self.execution_step = 0
        self.reflection_count = 0
        
    def configure(self, llm: LLMProvider, mcp: ToolMCP, verbose: bool = False) -> None:
        """Configure the engine with LLM and MCP."""
        self.llm = llm
        self.mcp = mcp
        self.verbose = verbose
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process using metacognitive reasoning flow.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory
            
        Returns:
            Final response
        """
        if not self.llm or not self.mcp:
            raise ValueError("MetaCognitiveEngine not configured. Call configure() first.")
        
        # Initialize reasoning session
        self.current_phase = ReasoningPhase.PLANNING
        self.task_plan_id = f"task_{len(messages)}"
        self.execution_step = 0
        self.reflection_count = 0
        
        # Main reasoning loop
        max_phases = 20  # Prevent infinite loops
        phase_count = 0
        
        while self.current_phase != ReasoningPhase.TERMINATION and phase_count < max_phases:
            phase_count += 1
            
            if self.verbose:
                logger.info(f"Reasoning Phase {phase_count}: {self.current_phase.value}")
            
            if self.current_phase == ReasoningPhase.PLANNING:
                await self._planning_phase(messages, memory)
            elif self.current_phase == ReasoningPhase.EXECUTION:
                await self._execution_phase(messages, memory)
            elif self.current_phase == ReasoningPhase.MONITORING:
                await self._monitoring_phase(messages, memory)
            elif self.current_phase == ReasoningPhase.DECISION:
                await self._decision_phase(messages, memory)
            elif self.current_phase == ReasoningPhase.REFLECTION:
                await self._reflection_phase(messages, memory)
        
        # Final termination if not already done
        if self.current_phase != ReasoningPhase.TERMINATION:
            await self._termination_phase(memory, "success", "Maximum reasoning phases reached")
        
        # Return final response
        return self._get_final_response(memory)
    
    async def _planning_phase(self, messages: List[MessageProtocol], memory: ConversationMemory) -> None:
        """Phase 1: Create task plan using planning tool."""
        
        # Get the user's task
        user_task = messages[-1].content if messages else "No task specified"
        
        # Create planning prompt
        planning_prompt = f"""
PLANNING PHASE: Break down the user's task into a structured plan.

User Task: {user_task}

You need to:
1. Analyze the task complexity and requirements
2. Create a structured plan with specific steps
3. Use the planning tool to create the plan

Think step by step about what needs to be done, then create a plan.
"""
        
        # Add planning guidance to conversation
        planning_msg = Message(role="system", content=planning_prompt)
        current_messages = messages + [planning_msg]
        
        # Get tools (should include planning tool)
        tools = self.mcp.get_tool_definitions()
        
        # Generate response with tool calls
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=current_messages, 
            tools=tools
        )
        
        memory.add_message(response)
        
        # Execute planning tool if called
        if tool_calls:
            results = await self.mcp.execute_tool_calls(tool_calls)
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
        
        # Move to execution phase
        self.current_phase = ReasoningPhase.EXECUTION
    
    async def _execution_phase(self, messages: List[MessageProtocol], memory: ConversationMemory) -> None:
        """Phase 2: Execute plan steps with explicit thought/action/observation."""
        
        execution_prompt = f"""
EXECUTION PHASE: Execute the current step of your plan.

You MUST follow this exact format:

Thought: [Your reasoning about the current step and what you need to do]
Action: [Tool to use, or "None" if no tool needed]
Observation: [Results from the tool, or your direct analysis if no tool]

Be explicit about your thinking process. Show your reasoning clearly.

Current Step: {self.execution_step}
"""
        
        # Add execution guidance
        execution_msg = Message(role="system", content=execution_prompt)
        current_messages = memory.get_messages() + [execution_msg]
        
        tools = self.mcp.get_tool_definitions()
        
        # Generate response with explicit reasoning format
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=current_messages,
            tools=tools
        )
        
        memory.add_message(response)
        
        # Execute tools if called
        if tool_calls:
            results = await self.mcp.execute_tool_calls(tool_calls)
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
        
        self.execution_step += 1
        
        # Move to monitoring phase
        self.current_phase = ReasoningPhase.MONITORING
    
    async def _monitoring_phase(self, messages: List[MessageProtocol], memory: ConversationMemory) -> None:
        """Phase 3: Monitor progress and update plan status."""
        
        monitoring_prompt = f"""
MONITORING PHASE: Assess your progress on the current task.

You need to:
1. Evaluate what you just accomplished
2. Check if the current step is complete, blocked, or needs more work
3. Update the plan status using the planning tool
4. Determine if you're making progress toward the goal

Current execution step: {self.execution_step}

Be honest about your progress and any obstacles you're facing.
"""
        
        monitoring_msg = Message(role="system", content=monitoring_prompt)
        current_messages = memory.get_messages() + [monitoring_msg]
        
        tools = self.mcp.get_tool_definitions()
        
        # Monitor progress
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=current_messages,
            tools=tools
        )
        
        memory.add_message(response)
        
        # Execute monitoring tools (likely planning updates)
        if tool_calls:
            results = await self.mcp.execute_tool_calls(tool_calls)
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
        
        # Move to decision phase
        self.current_phase = ReasoningPhase.DECISION
    
    async def _decision_phase(self, messages: List[MessageProtocol], memory: ConversationMemory) -> None:
        """Phase 4: Decide next action based on progress."""
        
        decision_prompt = f"""
DECISION PHASE: Decide what to do next based on your progress.

Your options:
1. CONTINUE: Continue execution with the next step
2. REFLECT: Take time to reflect and potentially adjust strategy  
3. TERMINATE_SUCCESS: Task is complete and successful
4. TERMINATE_FAILURE: Task cannot be completed due to obstacles

Consider:
- Have you completed the user's task successfully?
- Are you making meaningful progress?
- Are you stuck or blocked?
- Do you need to adjust your approach?

Execution steps so far: {self.execution_step}
Reflections so far: {self.reflection_count}

Make a clear decision and explain your reasoning.
"""
        
        decision_msg = Message(role="system", content=decision_prompt)
        current_messages = memory.get_messages() + [decision_msg]
        
        # Make decision (no tools needed, just reasoning)
        response = await self.llm.acomplete(current_messages)
        memory.add_message(response)
        
        # Parse decision from response (simplified)
        decision_text = response.content.lower()
        
        if "terminate_success" in decision_text or "task is complete" in decision_text:
            await self._termination_phase(memory, "success", "Task completed successfully")
        elif "terminate_failure" in decision_text or "cannot be completed" in decision_text:
            await self._termination_phase(memory, "failure", "Task could not be completed")
        elif "reflect" in decision_text and self.reflection_count < 3:
            self.current_phase = ReasoningPhase.REFLECTION
        elif self.execution_step < MAX_REACT_ITERATIONS:
            self.current_phase = ReasoningPhase.EXECUTION
        else:
            await self._termination_phase(memory, "success", "Maximum execution steps reached")
    
    async def _reflection_phase(self, messages: List[MessageProtocol], memory: ConversationMemory) -> None:
        """Phase 5: Reflect on approach and adapt strategy."""
        
        reflection_prompt = f"""
REFLECTION PHASE: Reflect on your approach and consider improvements.

Reflect on:
1. What has worked well so far?
2. What challenges have you encountered?
3. Are there better approaches you could try?
4. Should you adjust your plan or strategy?
5. What have you learned that could help?

This is reflection #{self.reflection_count + 1}. Use this time to think deeply about your approach.

After reflection, you'll return to execution with any insights gained.
"""
        
        reflection_msg = Message(role="system", content=reflection_prompt)
        current_messages = memory.get_messages() + [reflection_msg]
        
        # Reflect (might use planning tool to adjust plan)
        tools = self.mcp.get_tool_definitions()
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=current_messages,
            tools=tools
        )
        
        memory.add_message(response)
        
        # Execute reflection tools (plan updates)
        if tool_calls:
            results = await self.mcp.execute_tool_calls(tool_calls)
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
        
        self.reflection_count += 1
        
        # Return to execution with new insights
        self.current_phase = ReasoningPhase.EXECUTION
    
    async def _termination_phase(self, memory: ConversationMemory, status: str, message: str) -> None:
        """Phase 6: Terminate with final status."""
        
        termination_prompt = f"""
TERMINATION PHASE: Complete the task and provide final response.

Status: {status}
Message: {message}

Use the terminate tool to formally end the reasoning process, then provide a clear final response to the user.
"""
        
        termination_msg = Message(role="system", content=termination_prompt)
        current_messages = memory.get_messages() + [termination_msg]
        
        tools = self.mcp.get_tool_definitions()
        
        # Terminate formally
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=current_messages,
            tools=tools
        )
        
        memory.add_message(response)
        
        # Execute terminate tool
        if tool_calls:
            results = await self.mcp.execute_tool_calls(tool_calls)
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
        
        self.current_phase = ReasoningPhase.TERMINATION
    
    def _get_final_response(self, memory: ConversationMemory) -> str:
        """Extract final response from conversation."""
        messages = memory.get_messages()
        
        # Find the last assistant message that's not a system message
        for msg in reversed(messages):
            if msg.role == "assistant" and not msg.content.startswith("PLANNING PHASE"):
                return msg.content
        
        return "Task processing completed."
