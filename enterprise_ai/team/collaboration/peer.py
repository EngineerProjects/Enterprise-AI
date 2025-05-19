"""
Peer team implementation for Enterprise AI.

This module provides a team implementation with a flat, peer-to-peer structure,
supporting collaborative decision making and equal participation.
"""

import asyncio
import random
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, MessageProtocol, Task
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.types import TeamMemberRole, TeamMessageType

logger = get_logger("team.collaboration.peer")


class ConsensusMode(Enum):
    """Consensus modes for peer team decision making."""
    MAJORITY = auto()  # Simple majority (>50%)
    SUPER_MAJORITY = auto()  # Super majority (>66%)
    UNANIMOUS = auto()  # All members must agree
    QUORUM = auto()  # Designated quorum required
    WEIGHTED = auto()  # Decisions weighted by member expertise
    DELEGATED = auto()  # Decisions delegated to experts
    DELPHI = auto()  # Multi-round iterative consensus


class PeerTeam(BaseTeam):
    """Peer team implementation with flat structure.
    
    This team type implements a collaborative, peer-to-peer structure where
    all members have equal standing. Decisions are made through consensus
    rather than through a central authority.
    """
    
    def __init__(
        self,
        team_id: Optional[str] = None,
        name: Optional[str] = None,
        consensus_mode: Union[ConsensusMode, str] = ConsensusMode.MAJORITY,
        consensus_threshold: float = 0.51,
        quorum_size: int = 2,
        delphi_rounds: int = 3,
        **kwargs: Any,
    ):
        """Initialize a peer team.
        
        Args:
            team_id: Optional unique identifier
            name: Optional human-readable name
            consensus_mode: Mode for reaching consensus
            consensus_threshold: Threshold for agreement (0.0-1.0)
            quorum_size: Minimum number of members for a quorum
            delphi_rounds: Number of rounds for Delphi consensus
            **kwargs: Additional team-specific parameters
        """
        super().__init__(team_id=team_id, name=name, **kwargs)
        
        # Set consensus parameters
        self._consensus_mode = self._resolve_consensus_mode(consensus_mode)
        self._consensus_threshold = max(0.01, min(1.0, consensus_threshold))
        self._quorum_size = max(1, quorum_size)
        self._delphi_rounds = max(1, delphi_rounds)
        self._pending_votes: Dict[str, Dict[str, Any]] = {}
        self._delphi_sessions: Dict[str, Dict[str, Any]] = {}
        self._member_weights: Dict[str, float] = {}  # For weighted voting
        self._expertise_areas: Dict[str, Dict[str, float]] = {}  # agent_id -> {domain -> expertise_level}
        
        # In peer teams, we don't have a dedicated manager
        # but we may have a coordinator role for administrative tasks
        self._coordinator_id: Optional[str] = None
        
        logger.info(f"Initialized peer team {self.id} with {self._consensus_mode} consensus mode")
    
    @property
    def consensus_mode(self) -> ConsensusMode:
        """Get the team's consensus mode.
        
        Returns:
            ConsensusMode enum value
        """
        return self._consensus_mode
    
    @property
    def coordinator(self) -> Optional[AgentProtocol]:
        """Get the team coordinator if assigned.
        
        Returns:
            Coordinator agent or None if not set
        """
        if self._coordinator_id and self._coordinator_id in self._membership._members:
            return self._membership._members[self._coordinator_id]
        return None
    
    def set_consensus_mode(self, mode: Union[ConsensusMode, str], threshold: Optional[float] = None) -> None:
        """Set the team's consensus mode and optionally the threshold.
        
        Args:
            mode: New consensus mode
            threshold: Optional new threshold value
        """
        self._consensus_mode = self._resolve_consensus_mode(mode)
        
        if threshold is not None:
            self._consensus_threshold = max(0.01, min(1.0, threshold))
            
        logger.info(f"Changed consensus mode for team {self.id} to {self._consensus_mode}")
        if threshold is not None:
            logger.info(f"Changed consensus threshold to {self._consensus_threshold}")
            
    def set_member_weight(self, agent_id: str, weight: float) -> bool:
        """Set the voting weight for a team member.
        
        Used in weighted consensus mode.
        
        Args:
            agent_id: ID of the agent
            weight: Voting weight (0.0-10.0, where 1.0 is standard)
            
        Returns:
            True if weight was set, False if agent not in team
        """
        agent = self._team.get_member(agent_id)
        if not agent:
            logger.warning(f"Cannot set weight: agent {agent_id} not in team {self._team.id}")
            return False
            
        self._member_weights[agent_id] = max(0.0, min(10.0, weight))
        logger.info(f"Set voting weight of {weight} for agent {agent_id} in team {self._team.id}")
        return True
        
    def set_expertise(self, agent_id: str, domain: str, level: float) -> bool:
        """Set an agent's expertise level in a specific domain.
        
        Used for expertise-based delegated decision making.
        
        Args:
            agent_id: ID of the agent
            domain: Expertise domain (e.g., "finance", "engineering")
            level: Expertise level (0.0-10.0, where 10.0 is expert)
            
        Returns:
            True if expertise was set, False if agent not in team
        """
        agent = self._team.get_member(agent_id)
        if not agent:
            logger.warning(f"Cannot set expertise: agent {agent_id} not in team {self._team.id}")
            return False
            
        # Initialize expertise dict for this agent if needed
        if agent_id not in self._expertise_areas:
            self._expertise_areas[agent_id] = {}
            
        self._expertise_areas[agent_id][domain] = max(0.0, min(10.0, level))
        logger.info(f"Set {domain} expertise of {level} for agent {agent_id} in team {self._team.id}")
        return True
        
    def get_domain_experts(self, domain: str, min_level: float = 7.0) -> List[str]:
        """Get agents that are experts in a specific domain.
        
        Args:
            domain: Expertise domain to query
            min_level: Minimum expertise level to qualify as expert
            
        Returns:
            List of agent IDs of experts
        """
        experts = []
        for agent_id, domains in self._expertise_areas.items():
            if domain in domains and domains[domain] >= min_level:
                experts.append(agent_id)
                
        return experts
    
    def add_member(self, agent: AgentProtocol, role: Optional[Any] = None) -> bool:
        """Add an agent to the team.
        
        In peer teams, all members have the same role, but we may track
        a coordinator for administrative tasks.
        
        Args:
            agent: Agent to add to the team
            role: Optional role for the agent (ignored in peer teams)
            
        Returns:
            True if agent was added successfully, False otherwise
        """
        # In a peer team, we don't use role distinctions, but we do allow a coordinator
        if role and (role == TeamMemberRole.COORDINATOR or 
                     (isinstance(role, str) and role.upper() == "COORDINATOR")):
            result = super().add_member(agent, TeamMemberRole.MEMBER)
            if result:
                self._coordinator_id = agent.id
                logger.info(f"Set agent {agent.id} as coordinator for peer team {self.id}")
            return result
            
        # Always use MEMBER role regardless of what was passed
        return super().add_member(agent, TeamMemberRole.MEMBER)
    
    def assign_task(
        self, 
        task: Union[Task, Dict[str, Any]], 
        agent_id: Optional[str] = None
    ) -> bool:
        """Assign a task to the team or a specific team member.
        
        In peer teams, tasks can be assigned directly or through consensus.
        
        Args:
            task: Task to assign
            agent_id: Optional ID of the specific agent to assign the task to
            
        Returns:
            True if task was assigned successfully, False otherwise
        """
        # Create team task
        team_task = self._tasks.create_task(task)
        
        # If agent_id is provided, peer teams allow direct assignment
        if agent_id and agent_id in self._membership._members:
            logger.info(f"Directly assigning task {team_task.id} to agent {agent_id}")
            return self._tasks.assign_task(team_task.id, agent_id)
        
        # If no specific agent, use collaborative assignment
        # Task complexity determines approach - for now use a simple algorithm
        
        # If we have coordinator, they can suggest best agent 
        if self._coordinator_id:
            coordinator = self._membership._members[self._coordinator_id]
            # In reality would consult the coordinator AI
            logger.info(f"Coordinator suggesting agent for task {team_task.id}")
            
            # Simulated coordinator decision - pick random agent other than coordinator
            options = [
                agent_id for agent_id in self._membership._members.keys() 
                if agent_id != self._coordinator_id
            ]
            
            if options:
                selected_agent_id = random.choice(options)
                return self._tasks.assign_task(team_task.id, selected_agent_id)
            else:
                # If no other agents, coordinator takes it
                return self._tasks.assign_task(team_task.id, self._coordinator_id)
        
        # Otherwise distribute evenly across all members
        # Get agent with fewest tasks
        agent_counts = {}
        for agent_id in self._membership._members:
            agent_tasks = self._tasks.get_agent_tasks(agent_id)
            agent_counts[agent_id] = len(agent_tasks)
        
        if agent_counts:
            # Find agent with minimum task count
            min_count = min(agent_counts.values())
            candidates = [
                agent_id for agent_id, count in agent_counts.items() 
                if count == min_count
            ]
            selected_agent_id = random.choice(candidates)
            logger.info(f"Collaboratively assigning task {team_task.id} to agent {selected_agent_id}")
            return self._tasks.assign_task(team_task.id, selected_agent_id)
        
        return False
    
    async def hold_vote(
        self,
        proposal: str,
        options: List[str],
        required_voters: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Hold a team vote on a proposal.
        
        Args:
            proposal: Proposal description
            options: List of options to vote on
            required_voters: Optional list of agent IDs that must vote
            timeout_seconds: Timeout for voting process
            domain: Optional domain area for expertise-based voting
            
        Returns:
            Voting results dictionary
        """
        vote_id = f"vote-{self.id}-{len(self._pending_votes)}"
        
        # For Delphi consensus mode, use the specialized method
        if self._consensus_mode == ConsensusMode.DELPHI:
            return await self._run_delphi_consensus(proposal, options, required_voters, timeout_seconds)
            
        # For Delegated consensus mode, delegate to domain experts
        if self._consensus_mode == ConsensusMode.DELEGATED and domain:
            experts = self.get_domain_experts(domain)
            if experts:
                # Override required_voters with experts
                required_voters = experts
                logger.info(f"Delegating decision to {len(experts)} domain experts in {domain}")
        
        # Set up vote
        vote_data = {
            "id": vote_id,
            "proposal": proposal,
            "options": options,
            "required_voters": required_voters or [],
            "votes": {},
            "status": "in_progress",
            "result": None,
            "domain": domain
        }
        
        self._pending_votes[vote_id] = vote_data
        
        # In a real implementation, we would broadcast the proposal and collect votes
        # For now, simulate with random votes
        all_members = list(self._membership._members.keys())
        required = required_voters or all_members
        
        # Simulate async voting
        await asyncio.sleep(min(2.0, timeout_seconds))
        
        # Collect simulated votes
        for agent_id in all_members:
            if random.random() > 0.2:  # 80% chance of voting
                vote_data["votes"][agent_id] = random.choice(options)
        
        # Check if we have enough votes according to consensus mode
        result = self._evaluate_vote_results(vote_data)
        vote_data["result"] = result
        vote_data["status"] = "completed"
        
        logger.info(f"Vote {vote_id} completed with result: {result}")
        return vote_data
        
    async def _run_delphi_consensus(
        self,
        proposal: str,
        options: List[str],
        required_voters: Optional[List[str]] = None,
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """Run a Delphi method consensus process.
        
        The Delphi method involves multiple rounds of voting with feedback
        between rounds to help participants converge on a consensus.
        
        Args:
            proposal: Proposal description
            options: List of options to vote on
            required_voters: Optional list of agent IDs that must vote
            timeout_seconds: Timeout for voting process
            
        Returns:
            Results of the Delphi consensus process
        """
        delphi_id = f"delphi-{self.id}-{len(self._delphi_sessions)}"
        
        # Set up Delphi session
        delphi_data = {
            "id": delphi_id,
            "proposal": proposal,
            "options": options,
            "required_voters": required_voters or [],
            "rounds": [],
            "status": "in_progress",
            "result": None,
            "current_round": 0
        }
        
        self._delphi_sessions[delphi_id] = delphi_data
        
        # Get all members
        all_members = list(self._membership._members.keys())
        required = required_voters or all_members
        
        # Run multiple rounds
        for round_num in range(1, self._delphi_rounds + 1):
            # Update current round
            delphi_data["current_round"] = round_num
            
            # Initialize round data
            round_data = {
                "round": round_num,
                "votes": {},
                "comments": {},
                "summary": {}
            }
            
            # Simulate voting
            await asyncio.sleep(min(1.0, timeout_seconds / self._delphi_rounds))
            
            # In a real implementation, we would gather votes from agents
            # For simulation, create random votes that converge over rounds
            for agent_id in all_members:
                if random.random() > 0.1:  # 90% participation rate
                    # If later rounds, bias toward previous round consensus
                    if round_num > 1 and delphi_data["rounds"]:
                        prev_round = delphi_data["rounds"][-1]
                        vote_counts = {}
                        for opt in options:
                            vote_counts[opt] = sum(1 for v in prev_round["votes"].values() if v == opt)
                        
                        # Find most popular option from previous round
                        popular_option = max(vote_counts.items(), key=lambda x: x[1])[0]
                        
                        # Increasing convergence in later rounds
                        convergence_rate = 0.3 + (0.2 * round_num)  # 50%, 70%, 90%
                        
                        if random.random() < convergence_rate:
                            # Vote for popular option
                            round_data["votes"][agent_id] = popular_option
                        else:
                            # Random vote
                            round_data["votes"][agent_id] = random.choice(options)
                    else:
                        # First round - random votes
                        round_data["votes"][agent_id] = random.choice(options)
                    
                    # Add simulated comment
                    round_data["comments"][agent_id] = f"Comment from {agent_id} in round {round_num}"
            
            # Calculate summary for this round
            summary = {}
            for option in options:
                count = sum(1 for v in round_data["votes"].values() if v == option)
                percent = count / len(round_data["votes"]) if round_data["votes"] else 0
                summary[option] = {
                    "count": count,
                    "percentage": percent
                }
            
            round_data["summary"] = summary
            
            # Add round to session
            delphi_data["rounds"].append(round_data)
            
            # Check if we've reached consensus
            consensus_option = None
            for option, stats in summary.items():
                if stats["percentage"] >= self._consensus_threshold:
                    consensus_option = option
                    break
                    
            # If consensus reached, end early
            if consensus_option:
                delphi_data["result"] = consensus_option
                delphi_data["status"] = "completed"
                logger.info(f"Delphi process {delphi_id} reached consensus in round {round_num}: {consensus_option}")
                break
        
        # If we finished all rounds but no consensus, take highest option
        if delphi_data["status"] == "in_progress":
            final_round = delphi_data["rounds"][-1]
            
            # Find option with most votes
            vote_counts = {}
            for option in options:
                vote_counts[option] = sum(1 for v in final_round["votes"].values() if v == option)
                
            if vote_counts:
                top_option = max(vote_counts.items(), key=lambda x: x[1])[0]
                delphi_data["result"] = top_option
                delphi_data["status"] = "completed"
                logger.info(f"Delphi process {delphi_id} completed with majority option: {top_option}")
            else:
                logger.warning(f"Delphi process {delphi_id} failed to reach any decision")
                delphi_data["status"] = "failed"
        
        return delphi_data
    
    def _evaluate_vote_results(self, vote_data: Dict[str, Any]) -> Optional[str]:
        """Evaluate the results of a vote based on consensus mode.
        
        Args:
            vote_data: Voting data dictionary
            
        Returns:
            Winning option or None if no consensus
        """
        votes = vote_data["votes"]
        options = vote_data["options"]
        required_voters = vote_data["required_voters"]
        domain = vote_data.get("domain")
        
        # Check if required voters have voted
        for voter_id in required_voters:
            if voter_id not in votes:
                logger.info(f"Required voter {voter_id} has not voted")
                return None
        
        # Count votes
        vote_counts = {option: 0 for option in options}
        
        # For weighted voting, track weighted counts separately
        weighted_counts = {option: 0.0 for option in options}
        
        # Count votes based on consensus mode
        if self._consensus_mode == ConsensusMode.WEIGHTED:
            # Apply weights to votes
            for agent_id, vote in votes.items():
                # Get agent weight (default to 1.0)
                weight = self._member_weights.get(agent_id, 1.0)
                
                if vote in weighted_counts:
                    weighted_counts[vote] += weight
                    vote_counts[vote] += 1  # Also track raw count
                    
            # Calculate total weighted votes
            total_weighted = sum(weighted_counts.values())
            
            if total_weighted > 0:
                # Find option with highest weighted percentage
                for option, weighted_count in weighted_counts.items():
                    if weighted_count / total_weighted >= self._consensus_threshold:
                        return option
        
        # For delegated consensus with domain expertise
        elif self._consensus_mode == ConsensusMode.DELEGATED and domain:
            # Only count votes from experts in this domain
            expert_votes = {}
            domain_experts = self.get_domain_experts(domain)
            
            if domain_experts:
                # Only consider votes from domain experts
                for expert_id in domain_experts:
                    if expert_id in votes:
                        expert_vote = votes[expert_id]
                        if expert_vote in vote_counts:
                            # Weight by expertise level
                            expertise = self._expertise_areas.get(expert_id, {}).get(domain, 1.0)
                            weighted_counts[expert_vote] += expertise
                            expert_votes[expert_id] = expert_vote
                
                # If we have expert votes, use them
                if expert_votes:
                    total_weighted = sum(weighted_counts.values())
                    if total_weighted > 0:
                        # Find option with highest weighted percentage among experts
                        for option, weighted_count in weighted_counts.items():
                            if weighted_count / total_weighted >= self._consensus_threshold:
                                return option
                    
                    # If no clear winner, use plurality among experts
                    for option in options:
                        vote_counts[option] = sum(1 for v in expert_votes.values() if v == option)
                else:
                    # Fall back to regular voting if no experts voted
                    for agent_id, vote in votes.items():
                        if vote in vote_counts:
                            vote_counts[vote] += 1
            else:
                # No domain experts defined, use regular counting
                for agent_id, vote in votes.items():
                    if vote in vote_counts:
                        vote_counts[vote] += 1
        else:
            # Regular counting for other consensus modes
            for agent_id, vote in votes.items():
                if vote in vote_counts:
                    vote_counts[vote] += 1
        
        total_votes = len(votes)
        
        if total_votes == 0:
            logger.warning("No votes collected")
            return None
        
        # Apply consensus rules based on mode
        if self._consensus_mode == ConsensusMode.UNANIMOUS:
            # All members must agree and all must vote
            if total_votes < len(self._membership._members):
                return None
                
            if len(set(votes.values())) == 1:
                return next(iter(votes.values()))  # The unanimous choice
            return None
            
        elif self._consensus_mode == ConsensusMode.QUORUM:
            # Need minimum quorum size
            if total_votes < self._quorum_size:
                logger.info(f"Not enough votes for quorum ({total_votes} < {self._quorum_size})")
                return None
                
            # Find winner with threshold
            for option, count in vote_counts.items():
                if count / total_votes >= self._consensus_threshold:
                    return option
            return None
            
        elif self._consensus_mode == ConsensusMode.SUPER_MAJORITY:
            # Fixed 2/3 threshold
            for option, count in vote_counts.items():
                if count / total_votes >= 0.667:
                    return option
            return None
            
        elif self._consensus_mode in [ConsensusMode.DELEGATED, ConsensusMode.WEIGHTED]:
            # Already handled above, but check if no winner was found
            # In that case, use plurality (highest vote getter)
            return max(vote_counts.items(), key=lambda x: x[1])[0] if vote_counts else None
            
        elif self._consensus_mode == ConsensusMode.DELPHI:
            # Delphi handled in separate method
            return None
            
        else:  # Default MAJORITY
            # Find option with most votes, meeting threshold
            best_option = max(vote_counts.items(), key=lambda x: x[1]) if vote_counts else (None, 0)
            if best_option[0] and best_option[1] / total_votes >= self._consensus_threshold:
                return best_option[0]
            return None
    
    def decompose_task(self, task_id: str, subtasks: List[Any]) -> List[Any]:
        """Decompose a task into subtasks with collaborative assignment.
        
        Args:
            task_id: ID of the parent task
            subtasks: List of subtask descriptions or data
            
        Returns:
            List of created subtask objects
        """
        # Create subtasks using the BaseTeam implementation
        created_subtasks = super().decompose_task(task_id, subtasks)
        
        # In peer teams, subtasks can be claimed voluntarily or assigned collaboratively
        # Here we'll just distribute them evenly for simplicity
        
        if created_subtasks:
            members = list(self._membership._members.keys())
            if members:
                for i, subtask in enumerate(created_subtasks):
                    # Round-robin assignment
                    assigned_agent_id = members[i % len(members)]
                    self._tasks.assign_task(subtask.id, assigned_agent_id)
                    logger.info(f"Assigned subtask {subtask.id} to agent {assigned_agent_id}")
        
        return created_subtasks
    
    async def process_message(
        self, 
        message: Union[str, MessageProtocol], 
        **kwargs: Any
    ) -> MessageProtocol:
        """Process a message directed to the team.
        
        In peer teams, messages are processed collaboratively.
        
        Args:
            message: Message to process
            **kwargs: Additional parameters for processing
            
        Returns:
            Response message
        """
        # Convert string to message if needed
        if isinstance(message, str):
            message = Message.user_message(message)
        
        # In a peer team, we might:
        # 1. Send to coordinator (if we have one) for processing
        # 2. Send to all members and aggregate responses
        # 3. Select a member based on content expertise
        
        # For simplicity, if we have a coordinator, they process first
        if self._coordinator_id:
            coordinator = self._membership._members[self._coordinator_id]
            try:
                # Forward to coordinator
                logger.info(f"Forwarding message to coordinator {self._coordinator_id}")
                response = await self._process_agent_message(coordinator, message)
                return response
            except Exception as e:
                logger.error(f"Error processing message with coordinator: {e}")
                # Fall through to standard processing
        
        # Distribute to all members in parallel and combine responses
        # This is a simple implementation - a real system would be more sophisticated
        try:
            responses = await self.abroadcast_message(message)
            
            if not responses:
                return Message.assistant_message(
                    f"Team {self.name} currently has no members to process your message."
                )
                
            # Create combined response
            combined_content = f"Team {self.name} collaboration:\n\n"
            for i, response in enumerate(responses):
                agent_id = list(self._membership._members.keys())[i]
                agent_name = getattr(self._membership._members[agent_id], "name", agent_id)
                response_content = getattr(response, "content", str(response))
                combined_content += f"**{agent_name}**: {response_content}\n\n"
                
            combined_response = Message.assistant_message(combined_content)
            return combined_response
            
        except Exception as e:
            logger.error(f"Error in collaborative message processing: {e}")
            return Message.assistant_message(
                f"Team {self.name} encountered an error processing your message: {str(e)}"
            )
    
    def _resolve_consensus_mode(self, mode: Union[ConsensusMode, str]) -> ConsensusMode:
        """Resolve consensus mode from various input types.
        
        Args:
            mode: Consensus mode to resolve (enum or string)
            
        Returns:
            Resolved ConsensusMode enum value
        """
        if isinstance(mode, ConsensusMode):
            return mode
        
        # Convert string to enum
        try:
            mode_upper = mode.upper()
            if mode_upper == "UNANIMOUS":
                return ConsensusMode.UNANIMOUS
            elif mode_upper == "SUPER_MAJORITY":
                return ConsensusMode.SUPER_MAJORITY
            elif mode_upper == "QUORUM":
                return ConsensusMode.QUORUM
            else:
                return ConsensusMode.MAJORITY
        except (AttributeError, KeyError):
            logger.warning(f"Invalid consensus mode string: {mode}, defaulting to MAJORITY")
            return ConsensusMode.MAJORITY
    
    def get_status(self) -> Dict[str, Any]:
        """Get team status information with peer-specific details.
        
        Returns:
            Dictionary of status information
        """
        status = super().get_status()
        
        # Add peer-specific information
        peer_info = {
            "consensus_mode": self._consensus_mode.name,
            "consensus_threshold": self._consensus_threshold,
            "quorum_size": self._quorum_size,
            "pending_votes": len(self._pending_votes),
            "active_delphi_sessions": len([s for s in self._delphi_sessions.values() if s["status"] == "in_progress"]),
            "member_weights": len(self._member_weights),
            "expertise_domains": len(set(domain for domains in self._expertise_areas.values() for domain in domains))
        }
        
        if self._coordinator_id:
            peer_info["coordinator"] = self._coordinator_id
        
        status["peer"] = peer_info
        
        return status
