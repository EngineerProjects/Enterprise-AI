"""
Workflow factory for Enterprise AI.

This module provides factory functions for creating common workflow patterns.
"""

from typing import Any, Callable, Dict, List, Optional

from enterprise_ai.agent.types import AgentProtocol
from enterprise_ai.flow.builder import WorkflowBuilder
from enterprise_ai.flow.workflow import BaseWorkflow, SequentialWorkflow
from enterprise_ai.flow.types import FlowTeamProtocol
from enterprise_ai.logger import get_logger

logger = get_logger("flow.factory")


class WorkflowFactory:
    """Factory for creating common workflow patterns."""

    @staticmethod
    def create_sequential_agent_workflow(
        name: str,
        agent: AgentProtocol,
        tasks: List[str],
        workflow_id: Optional[str] = None,
    ) -> BaseWorkflow:
        """Create a workflow with sequential tasks for a single agent.

        Args:
            name: Name of the workflow
            agent: Agent to assign tasks to
            tasks: List of task descriptions
            workflow_id: Optional workflow ID

        Returns:
            Sequential workflow with tasks for the agent
        """
        builder = WorkflowBuilder(name, workflow_id)

        for i, task in enumerate(tasks):
            task_name = f"Task {i + 1}"
            builder.add_agent_task(
                name=task_name,
                agent=agent,
                task_description=task,
                result_key=f"result_{i + 1}",
            )

        return builder.build()

    @staticmethod
    def create_team_collaboration_workflow(
        name: str,
        research_team: FlowTeamProtocol,
        development_team: FlowTeamProtocol,
        research_task: str,
        development_task: str,
        workflow_id: Optional[str] = None,
    ) -> BaseWorkflow:
        """Create a workflow for team collaboration.

        Args:
            name: Name of the workflow
            research_team: Team for research tasks
            development_team: Team for development tasks
            research_task: Research task description
            development_task: Development task description (can use {research_result})
            workflow_id: Optional workflow ID

        Returns:
            Workflow for team collaboration
        """
        return (
            WorkflowBuilder(name, workflow_id)
            .add_team_task(
                name="Research Phase",
                team=research_team,
                task_description=research_task,
                result_key="research_result",
            )
            .add_team_task(
                name="Development Phase",
                team=development_team,
                task_description=development_task,
                result_key="development_result",
            )
            .build()
        )

    @staticmethod
    def create_data_processing_workflow(
        name: str,
        data_prep_agent: AgentProtocol,
        analysis_agent: AgentProtocol,
        reporting_agent: AgentProtocol,
        data_prep_task: str,
        analysis_task: str,
        reporting_task: str,
        workflow_id: Optional[str] = None,
    ) -> BaseWorkflow:
        """Create a data processing workflow.

        Args:
            name: Name of the workflow
            data_prep_agent: Agent for data preparation
            analysis_agent: Agent for data analysis
            reporting_agent: Agent for reporting
            data_prep_task: Data preparation task description
            analysis_task: Data analysis task description (can use {prepared_data})
            reporting_task: Reporting task description (can use {analysis_result})
            workflow_id: Optional workflow ID

        Returns:
            Data processing workflow
        """
        return (
            WorkflowBuilder(name, workflow_id)
            .add_agent_task(
                name="Data Preparation",
                agent=data_prep_agent,
                task_description=data_prep_task,
                result_key="prepared_data",
            )
            .add_agent_task(
                name="Data Analysis",
                agent=analysis_agent,
                task_description=analysis_task,
                result_key="analysis_result",
            )
            .add_agent_task(
                name="Reporting",
                agent=reporting_agent,
                task_description=reporting_task,
                result_key="final_report",
            )
            .build()
        )
