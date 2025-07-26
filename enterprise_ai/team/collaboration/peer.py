"""
Peer-to-peer collaboration pattern.

Implements autonomous collaboration between equal team members.
"""

from typing import List, Dict, Optional, Any, Set
import asyncio
from enterprise_ai.team.core import TeamTask, TeamMember
from enterprise_ai.team.roles.base import SpecialistRole
from enterprise_ai.team.architecture.messaging import TeamMessaging, TeamMessage
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.peer")


class PeerCollaboration:
    """Implements peer-to-peer collaboration between team members."""
    
    def __init__(self):
        self.peers: Dict[str, SpecialistRole] = {}
        self.collaboration_history: List[Dict[str, Any]] = []
        self.messaging = TeamMessaging()
        self.active_collaborations: Dict[str, Set[str]] = {}  # task_id -> set of peer_names
        
    def add_peer(self, peer: SpecialistRole) -> None:
        """Add peer to collaboration network."""
        peer_name = self._get_agent_name(peer.agent)
        self.peers[peer_name] = peer
        logger.info(f"Added peer: {peer_name} ({peer.domain})")
    
    def remove_peer(self, peer_name: str) -> Optional[SpecialistRole]:
        """Remove peer from collaboration network."""
        return self.peers.pop(peer_name, None)
    
    async def execute_peer_task(self, task: TeamTask) -> str:
        """Execute task using peer-to-peer collaboration."""
        # Find suitable peers for the task
        suitable_peers = self._find_suitable_peers(task)
        
        if not suitable_peers:
            raise Exception("No suitable peers available for task")
        
        if len(suitable_peers) == 1:
            # Single peer execution
            return await suitable_peers[0].execute_task(task)
        
        # Multi-peer collaboration
        return await self._collaborative_execution(task, suitable_peers)
    
    async def _collaborative_execution(self, task: TeamTask, peers: List[SpecialistRole]) -> str:
        """Execute task through peer collaboration."""
        peer_names = [self._get_agent_name(peer.agent) for peer in peers]
        self.active_collaborations[task.id] = set(peer_names)
        
        try:
            # Phase 1: Individual peer analysis
            analyses = await self._gather_peer_analyses(task, peers)
            
            # Phase 2: Peer discussion and consensus building
            consensus = await self._build_consensus(task, peers, analyses)
            
            # Phase 3: Collaborative execution
            final_result = await self._execute_consensus(task, peers, consensus)
            
            self._record_collaboration(task.id, peer_names, "completed")
            return final_result
            
        finally:
            self.active_collaborations.pop(task.id, None)
    
    async def _gather_peer_analyses(self, task: TeamTask, peers: List[SpecialistRole]) -> Dict[str, str]:
        """Gather individual analyses from each peer."""
        async def peer_analysis(peer: SpecialistRole):
            peer_name = self._get_agent_name(peer.agent)
            analysis_prompt = f"""
            As a {peer.domain} specialist, analyze this task: {task.description}
            
            Provide:
            1. Your perspective on the task
            2. What you can contribute
            3. What expertise from other specialists you might need
            4. Your proposed approach
            """
            
            analysis = await peer.agent.process(analysis_prompt)
            return peer_name, analysis
        
        # Gather analyses concurrently
        analysis_tasks = [peer_analysis(peer) for peer in peers]
        results = await asyncio.gather(*analysis_tasks)
        
        return dict(results)
    
    async def _build_consensus(self, task: TeamTask, peers: List[SpecialistRole], analyses: Dict[str, str]) -> str:
        """Build consensus among peers."""
        # Create discussion prompt for each peer
        discussion_context = "\n".join([
            f"{peer_name}: {analysis}" for peer_name, analysis in analyses.items()
        ])
        
        async def peer_discussion(peer: SpecialistRole):
            peer_name = self._get_agent_name(peer.agent)
            discussion_prompt = f"""
            Peer discussion for task: {task.description}
            
            Initial analyses:
            {discussion_context}
            
            As {peer_name}, respond to your peers and help build consensus on:
            1. The best overall approach
            2. How to divide responsibilities
            3. How to coordinate execution
            
            Be collaborative and build on others' ideas.
            """
            
            response = await peer.agent.process(discussion_prompt)
            
            # Send message to other peers
            msg = TeamMessage(
                sender=peer_name,
                recipient=None,  # Broadcast
                content=f"Discussion input: {response}",
                message_type="collaboration"
            )
            self.messaging.send_message(msg)
            
            return peer_name, response
        
        # Conduct discussion rounds
        discussion_results = await asyncio.gather(*[peer_discussion(peer) for peer in peers])
        
        # Synthesize consensus
        all_discussions = "\n".join([f"{name}: {response}" for name, response in discussion_results])
        
        # Use first peer to synthesize (could be improved with voting mechanism)
        synthesizer = peers[0]
        consensus_prompt = f"""
        Synthesize the peer discussion into a consensus plan:
        
        Task: {task.description}
        Discussion:
        {all_discussions}
        
        Create a unified plan that incorporates the best ideas from all peers.
        """
        
        consensus = await synthesizer.agent.process(consensus_prompt)
        logger.info(f"Built consensus among {len(peers)} peers for task {task.id}")
        
        return consensus
    
    async def _execute_consensus(self, task: TeamTask, peers: List[SpecialistRole], consensus: str) -> str:
        """Execute the agreed consensus plan."""
        # Assign specific roles to each peer based on consensus
        async def peer_execution(peer: SpecialistRole):
            peer_name = self._get_agent_name(peer.agent)
            execution_prompt = f"""
            Execute your part of the consensus plan:
            
            Consensus Plan: {consensus}
            Original Task: {task.description}
            
            As {peer_name} ({peer.domain} specialist), execute your assigned responsibilities.
            Coordinate with other peers as needed.
            """
            
            result = await peer.agent.process(execution_prompt)
            return peer_name, result
        
        # Execute in parallel
        execution_results = await asyncio.gather(*[peer_execution(peer) for peer in peers])
        
        # Integrate results
        integration_prompt = f"""
        Integrate these peer execution results into a final answer:
        
        Original Task: {task.description}
        Consensus Plan: {consensus}
        
        Peer Results:
        {chr(10).join([f"{name}: {result}" for name, result in execution_results])}
        
        Provide a comprehensive final response.
        """
        
        # Use the first peer to integrate (could be improved with dedicated integrator)
        final_result = await peers[0].agent.process(integration_prompt)
        
        logger.info(f"Completed peer collaboration for task {task.id}")
        return final_result
    
    def _find_suitable_peers(self, task: TeamTask) -> List[SpecialistRole]:
        """Find peers suitable for the task."""
        suitable = []
        
        for peer in self.peers.values():
            if peer.is_available and peer.can_handle_task(task):
                suitable.append(peer)
        
        # If no perfect matches, use available peers (collaborative problem-solving)
        if not suitable:
            suitable = [peer for peer in self.peers.values() if peer.is_available]
        
        # Limit collaboration to 4 peers for manageable coordination
        return suitable[:4]
    
    def _record_collaboration(self, task_id: str, peer_names: List[str], status: str) -> None:
        """Record collaboration event."""
        record = {
            "task_id": task_id,
            "participants": peer_names,
            "status": status,
            "timestamp": self._get_timestamp()
        }
        self.collaboration_history.append(record)
    
    def get_collaboration_metrics(self) -> Dict[str, Any]:
        """Get peer collaboration metrics."""
        total_collaborations = len(self.collaboration_history)
        successful = len([r for r in self.collaboration_history if r["status"] == "completed"])
        
        return {
            "total_collaborations": total_collaborations,
            "success_rate": successful / total_collaborations if total_collaborations > 0 else 0,
            "active_collaborations": len(self.active_collaborations),
            "available_peers": len([p for p in self.peers.values() if p.is_available])
        }
    
    def _get_agent_name(self, agent) -> str:
        """Extract agent name consistently."""
        if hasattr(agent, 'profile') and agent.profile and hasattr(agent.profile, 'name'):
            return agent.profile.name
        if hasattr(agent, 'name'):
            return agent.name
        return agent.__class__.__name__.lower()
    
    def _get_timestamp(self):
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now()
