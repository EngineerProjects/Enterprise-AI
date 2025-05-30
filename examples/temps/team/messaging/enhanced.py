"""
Enhanced messaging for large-scale team coordination.

This module provides scalable message routing and optimized 
communication patterns for large teams.
"""

import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, MessageProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.team.architecture.messaging import TeamMessage, MessagingManager
from enterprise_ai.team.core.types import TeamMessageType

logger = get_logger("team.messaging.enhanced")


class MessageRouterStrategy:
    """Base class for message routing strategies.
    
    Different strategies can be implemented to optimize
    message routing based on team size and structure.
    """
    
    def __init__(self, messaging_manager: MessagingManager):
        """Initialize the routing strategy.
        
        Args:
            messaging_manager: Messaging manager this strategy belongs to
        """
        self._messaging = messaging_manager
    
    async def route_message(
        self, 
        message: TeamMessage,
        members: List[AgentProtocol]
    ) -> Dict[str, Any]:
        """Route a message to appropriate recipients.
        
        Args:
            message: Message to route
            members: List of team members
            
        Returns:
            Routing results
        """
        # Default implementation: direct routing
        results = {
            "delivered": False,
            "recipients": 0,
            "errors": 0,
            "error_details": []
        }
        
        if message.receiver_id:
            # Direct message to specific recipient
            for agent in members:
                if agent.id == message.receiver_id:
                    try:
                        await agent.aprocess_message(message)
                        results["delivered"] = True
                        results["recipients"] = 1
                        break
                    except Exception as e:
                        results["errors"] = 1
                        results["error_details"].append({
                            "agent_id": agent.id,
                            "error": str(e)
                        })
        else:
            # Broadcast to all members
            delivered = 0
            errors = 0
            error_details = []
            
            for agent in members:
                try:
                    await agent.aprocess_message(message)
                    delivered += 1
                except Exception as e:
                    errors += 1
                    error_details.append({
                        "agent_id": agent.id,
                        "error": str(e)
                    })
            
            results["delivered"] = delivered > 0
            results["recipients"] = delivered
            results["errors"] = errors
            results["error_details"] = error_details
            
        return results


class DirectRoutingStrategy(MessageRouterStrategy):
    """Simple direct routing strategy.
    
    Routes messages directly to recipients without optimizations.
    Suitable for small teams.
    """
    pass  # Uses base implementation


class HierarchicalRoutingStrategy(MessageRouterStrategy):
    """Hierarchical routing strategy.
    
    Routes messages through the team hierarchy, with managers
    forwarding messages to their direct reports. This reduces
    the number of direct interactions needed.
    
    Suitable for large hierarchical teams.
    """
    
    async def route_message(
        self, 
        message: TeamMessage,
        members: List[AgentProtocol]
    ) -> Dict[str, Any]:
        """Route a message through the team hierarchy.
        
        Args:
            message: Message to route
            members: List of team members
            
        Returns:
            Routing results
        """
        # Get team for hierarchy information
        team = getattr(self._messaging, "_team", None)
        if not team or not hasattr(team, "_membership"):
            # Fall back to base implementation if team structure not available
            return await super().route_message(message, members)
        
        membership = team._membership
        manager = membership.manager
        
        results = {
            "delivered": False,
            "recipients": 0,
            "errors": 0,
            "error_details": []
        }
        
        if message.receiver_id:
            # Direct message - find if receiver is manager or direct report
            recipient = None
            for agent in members:
                if agent.id == message.receiver_id:
                    recipient = agent
                    break
            
            if recipient:
                try:
                    await recipient.aprocess_message(message)
                    results["delivered"] = True
                    results["recipients"] = 1
                except Exception as e:
                    results["errors"] = 1
                    results["error_details"].append({
                        "agent_id": recipient.id,
                        "error": str(e)
                    })
        else:
            # Broadcast message - send to manager first, then manager forwards to reports
            delivered = 0
            errors = 0
            error_details = []
            
            if manager:
                # Send to manager
                try:
                    await manager.aprocess_message(message)
                    delivered += 1
                    
                    # Get direct reports
                    reports = membership.get_direct_reports(manager.id)
                    
                    # Manager forwards to reports
                    for report in reports:
                        try:
                            forwarded_message = TeamMessage(
                                sender_id=manager.id,
                                receiver_id=report.id,
                                message_type=message.message_type,
                                content=message.content,
                                team_id=message.team_id,
                                team_message_type=message.team_message_type,
                                metadata={
                                    "original_sender": message.sender_id,
                                    "original_message_id": message.message_id,
                                    "forwarded": True
                                }
                            )
                            await report.aprocess_message(forwarded_message)
                            delivered += 1
                        except Exception as e:
                            errors += 1
                            error_details.append({
                                "agent_id": report.id,
                                "error": str(e)
                            })
                except Exception as e:
                    errors += 1
                    error_details.append({
                        "agent_id": manager.id,
                        "error": str(e)
                    })
            else:
                # No manager, fall back to direct broadcast
                for agent in members:
                    try:
                        await agent.aprocess_message(message)
                        delivered += 1
                    except Exception as e:
                        errors += 1
                        error_details.append({
                            "agent_id": agent.id,
                            "error": str(e)
                        })
            
            results["delivered"] = delivered > 0
            results["recipients"] = delivered
            results["errors"] = errors
            results["error_details"] = error_details
            
        return results


class GroupRoutingStrategy(MessageRouterStrategy):
    """Group-based routing strategy.
    
    Routes messages through predefined groups, minimizing
    the number of message dispatches.
    
    Suitable for large teams with distinct groups.
    """
    
    def __init__(self, messaging_manager: MessagingManager):
        """Initialize the group routing strategy.
        
        Args:
            messaging_manager: Messaging manager this strategy belongs to
        """
        super().__init__(messaging_manager)
        self._groups: Dict[str, List[str]] = defaultdict(list)  # group_id -> list of member_ids
        self._member_groups: Dict[str, List[str]] = defaultdict(list)  # member_id -> list of group_ids
        self._group_leaders: Dict[str, str] = {}  # group_id -> leader_id
    
    def define_group(self, group_id: str, member_ids: List[str], leader_id: Optional[str] = None) -> None:
        """Define a message routing group.
        
        Args:
            group_id: ID for the group
            member_ids: List of member IDs in the group
            leader_id: Optional ID of the group leader
        """
        # Store group members
        self._groups[group_id] = member_ids.copy()
        
        # Update member group mappings
        for member_id in member_ids:
            if group_id not in self._member_groups[member_id]:
                self._member_groups[member_id].append(group_id)
        
        # Set group leader if provided
        if leader_id:
            if leader_id in member_ids:
                self._group_leaders[group_id] = leader_id
            else:
                logger.warning(f"Leader {leader_id} is not a member of group {group_id}")
    
    def remove_group(self, group_id: str) -> None:
        """Remove a routing group.
        
        Args:
            group_id: ID of the group to remove
        """
        if group_id in self._groups:
            # Get member IDs
            member_ids = self._groups[group_id]
            
            # Remove group from member mappings
            for member_id in member_ids:
                if group_id in self._member_groups[member_id]:
                    self._member_groups[member_id].remove(group_id)
            
            # Remove group
            del self._groups[group_id]
            
            # Remove leader if exists
            if group_id in self._group_leaders:
                del self._group_leaders[group_id]
    
    def add_member_to_group(self, group_id: str, member_id: str) -> None:
        """Add a member to a routing group.
        
        Args:
            group_id: ID of the group
            member_id: ID of the member to add
        """
        if group_id not in self._groups:
            # Create the group if it doesn't exist
            self._groups[group_id] = []
            
        if member_id not in self._groups[group_id]:
            self._groups[group_id].append(member_id)
            
        if group_id not in self._member_groups[member_id]:
            self._member_groups[member_id].append(group_id)
    
    def remove_member_from_group(self, group_id: str, member_id: str) -> None:
        """Remove a member from a routing group.
        
        Args:
            group_id: ID of the group
            member_id: ID of the member to remove
        """
        if group_id in self._groups and member_id in self._groups[group_id]:
            self._groups[group_id].remove(member_id)
            
        if member_id in self._member_groups and group_id in self._member_groups[member_id]:
            self._member_groups[member_id].remove(group_id)
            
        # If member was the leader, remove leader
        if group_id in self._group_leaders and self._group_leaders[group_id] == member_id:
            del self._group_leaders[group_id]
    
    def set_group_leader(self, group_id: str, leader_id: str) -> bool:
        """Set a leader for a routing group.
        
        Args:
            group_id: ID of the group
            leader_id: ID of the leader
            
        Returns:
            True if leader was set, False otherwise
        """
        if group_id not in self._groups:
            logger.warning(f"Cannot set leader: group {group_id} does not exist")
            return False
            
        if leader_id not in self._groups[group_id]:
            logger.warning(f"Cannot set leader: {leader_id} is not a member of group {group_id}")
            return False
            
        self._group_leaders[group_id] = leader_id
        return True
    
    def get_member_groups(self, member_id: str) -> List[str]:
        """Get all groups a member belongs to.
        
        Args:
            member_id: ID of the member
            
        Returns:
            List of group IDs
        """
        return self._member_groups.get(member_id, [])
    
    def get_group_members(self, group_id: str) -> List[str]:
        """Get all members of a group.
        
        Args:
            group_id: ID of the group
            
        Returns:
            List of member IDs
        """
        return self._groups.get(group_id, [])
    
    async def route_message(
        self, 
        message: TeamMessage,
        members: List[AgentProtocol]
    ) -> Dict[str, Any]:
        """Route a message through groups.
        
        Args:
            message: Message to route
            members: List of team members
            
        Returns:
            Routing results
        """
        results = {
            "delivered": False,
            "recipients": 0,
            "errors": 0,
            "error_details": []
        }
        
        # Create lookup for fast member access
        member_lookup = {agent.id: agent for agent in members}
        
        if message.receiver_id:
            # Direct message to specific recipient
            if message.receiver_id in member_lookup:
                agent = member_lookup[message.receiver_id]
                try:
                    await agent.aprocess_message(message)
                    results["delivered"] = True
                    results["recipients"] = 1
                except Exception as e:
                    results["errors"] = 1
                    results["error_details"].append({
                        "agent_id": agent.id,
                        "error": str(e)
                    })
        else:
            # Check if message specifies target group
            target_group = message.metadata.get("target_group")
            
            if target_group and target_group in self._groups:
                # Message targeted to specific group
                await self._route_to_group(message, target_group, member_lookup, results)
            else:
                # Broadcast to all groups
                delivered = 0
                errors = 0
                error_details = []
                
                # Get unique members across all groups
                processed_members = set()
                
                # First, route through group leaders
                for group_id, members in self._groups.items():
                    # Skip empty groups
                    if not members:
                        continue
                        
                    leader_id = self._group_leaders.get(group_id)
                    
                    if leader_id and leader_id in member_lookup:
                        # Route through leader
                        leader = member_lookup[leader_id]
                        processed_members.add(leader_id)
                        
                        try:
                            await leader.aprocess_message(message)
                            delivered += 1
                            
                            # Leader forwards to group members
                            for member_id in members:
                                if member_id != leader_id and member_id in member_lookup:
                                    processed_members.add(member_id)
                                    agent = member_lookup[member_id]
                                    
                                    try:
                                        forwarded_message = TeamMessage(
                                            sender_id=leader_id,
                                            receiver_id=member_id,
                                            message_type=message.message_type,
                                            content=message.content,
                                            team_id=message.team_id,
                                            team_message_type=message.team_message_type,
                                            metadata={
                                                "original_sender": message.sender_id,
                                                "original_message_id": message.message_id,
                                                "forwarded": True,
                                                "group_id": group_id
                                            }
                                        )
                                        await agent.aprocess_message(forwarded_message)
                                        delivered += 1
                                    except Exception as e:
                                        errors += 1
                                        error_details.append({
                                            "agent_id": member_id,
                                            "error": str(e)
                                        })
                        except Exception as e:
                            errors += 1
                            error_details.append({
                                "agent_id": leader_id,
                                "error": str(e)
                            })
                    else:
                        # No leader, direct routing to group members
                        for member_id in members:
                            if member_id not in processed_members and member_id in member_lookup:
                                processed_members.add(member_id)
                                agent = member_lookup[member_id]
                                
                                try:
                                    await agent.aprocess_message(message)
                                    delivered += 1
                                except Exception as e:
                                    errors += 1
                                    error_details.append({
                                        "agent_id": member_id,
                                        "error": str(e)
                                    })
                
                # Direct routing to any members not in groups
                for agent in members:
                    if agent.id not in processed_members:
                        try:
                            await agent.aprocess_message(message)
                            delivered += 1
                        except Exception as e:
                            errors += 1
                            error_details.append({
                                "agent_id": agent.id,
                                "error": str(e)
                            })
                
                results["delivered"] = delivered > 0
                results["recipients"] = delivered
                results["errors"] = errors
                results["error_details"] = error_details
            
        return results
    
    async def _route_to_group(
        self,
        message: TeamMessage,
        group_id: str,
        member_lookup: Dict[str, AgentProtocol],
        results: Dict[str, Any]
    ) -> None:
        """Route a message to a specific group.
        
        Args:
            message: Message to route
            group_id: ID of the target group
            member_lookup: Dictionary of member_id -> agent
            results: Results dictionary to update
        """
        members = self._groups.get(group_id, [])
        leader_id = self._group_leaders.get(group_id)
        
        delivered = 0
        errors = 0
        error_details = []
        
        if leader_id and leader_id in member_lookup:
            # Route through leader
            leader = member_lookup[leader_id]
            
            try:
                await leader.aprocess_message(message)
                delivered += 1
                
                # Leader forwards to group members
                for member_id in members:
                    if member_id != leader_id and member_id in member_lookup:
                        agent = member_lookup[member_id]
                        
                        try:
                            forwarded_message = TeamMessage(
                                sender_id=leader_id,
                                receiver_id=member_id,
                                message_type=message.message_type,
                                content=message.content,
                                team_id=message.team_id,
                                team_message_type=message.team_message_type,
                                metadata={
                                    "original_sender": message.sender_id,
                                    "original_message_id": message.message_id,
                                    "forwarded": True,
                                    "group_id": group_id
                                }
                            )
                            await agent.aprocess_message(forwarded_message)
                            delivered += 1
                        except Exception as e:
                            errors += 1
                            error_details.append({
                                "agent_id": member_id,
                                "error": str(e)
                            })
            except Exception as e:
                errors += 1
                error_details.append({
                    "agent_id": leader_id,
                    "error": str(e)
                })
        else:
            # No leader, direct routing to group members
            for member_id in members:
                if member_id in member_lookup:
                    agent = member_lookup[member_id]
                    
                    try:
                        await agent.aprocess_message(message)
                        delivered += 1
                    except Exception as e:
                        errors += 1
                        error_details.append({
                            "agent_id": member_id,
                            "error": str(e)
                        })
        
        results["delivered"] = delivered > 0
        results["recipients"] = delivered
        results["errors"] = errors
        results["error_details"] = error_details


class EnhancedMessagingManager:
    """Enhanced messaging manager for large teams.
    
    This component extends the basic messaging manager with 
    optimized routing strategies for large teams.
    """
    
    def __init__(self, messaging_manager: MessagingManager):
        """Initialize the enhanced messaging manager.
        
        Args:
            messaging_manager: Base messaging manager to enhance
        """
        self._messaging = messaging_manager
        self._team = getattr(messaging_manager, "_team", None)
        self._routing_strategy: MessageRouterStrategy = DirectRoutingStrategy(messaging_manager)
        self._message_cache: Dict[str, TeamMessage] = {}  # cache of recent messages by id
        self._cache_size = 100  # maximum number of messages to keep in cache
    
    def set_routing_strategy(self, strategy_type: str) -> None:
        """Set the message routing strategy.
        
        Args:
            strategy_type: Type of strategy to use (direct, hierarchical, group)
        """
        if strategy_type.lower() == "direct":
            self._routing_strategy = DirectRoutingStrategy(self._messaging)
        elif strategy_type.lower() == "hierarchical":
            self._routing_strategy = HierarchicalRoutingStrategy(self._messaging)
        elif strategy_type.lower() == "group":
            self._routing_strategy = GroupRoutingStrategy(self._messaging)
        else:
            logger.warning(f"Unknown routing strategy: {strategy_type}, using direct")
            self._routing_strategy = DirectRoutingStrategy(self._messaging)
            
        logger.info(f"Set routing strategy to {strategy_type} for team {self._team.id}")
    
    def get_routing_strategy(self) -> MessageRouterStrategy:
        """Get the current routing strategy.
        
        Returns:
            Current routing strategy
        """
        return self._routing_strategy
    
    async def route_message(self, message: TeamMessage) -> Dict[str, Any]:
        """Route a message using the current strategy.
        
        Args:
            message: Message to route
            
        Returns:
            Routing results
        """
        # Cache the message for potential reuse
        self._cache_message(message)
        
        # Get team members
        if not self._team:
            return {
                "delivered": False,
                "error": "No team associated with messaging manager"
            }
            
        members = self._team.get_members()
        
        # Use current routing strategy
        return await self._routing_strategy.route_message(message, members)
    
    async def broadcast(
        self,
        message: Union[str, TeamMessage],
        sender_id: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Broadcast a message to team members.
        
        Args:
            message: Message to broadcast
            sender_id: Optional sender ID
            **kwargs: Additional message parameters
            
        Returns:
            Broadcast results
        """
        # Convert string to message if needed
        if isinstance(message, str):
            # Create broadcast message
            resolved_sender_id = sender_id or self._team.id
            
            from enterprise_ai.team.architecture.messaging import TeamBroadcastMessage
            msg = TeamBroadcastMessage(
                sender_id=resolved_sender_id,
                content=message,
                team_id=self._team.id,
                **kwargs
            )
        else:
            # Use existing message
            msg = message
            
            # Update sender if specified
            if sender_id:
                msg.sender_id = sender_id
        
        # Record in message history (delegated to base messaging manager)
        self._messaging._record_message(msg)
        
        # Route using strategy
        return await self.route_message(msg)
    
    async def batch_route_messages(self, messages: List[TeamMessage]) -> List[Dict[str, Any]]:
        """Route multiple messages efficiently.
        
        Args:
            messages: List of messages to route
            
        Returns:
            List of routing results
        """
        results = []
        
        # Batch messages by receiver for efficiency
        batched_messages: Dict[Optional[str], List[TeamMessage]] = defaultdict(list)
        
        for msg in messages:
            batched_messages[msg.receiver_id].append(msg)
            
            # Cache the message
            self._cache_message(msg)
        
        # Route each batch
        for receiver_id, msgs in batched_messages.items():
            if receiver_id:
                # Direct messages - route individually
                for msg in msgs:
                    result = await self.route_message(msg)
                    results.append(result)
            else:
                # Broadcasts - combine when possible
                if len(msgs) == 1:
                    # Single broadcast
                    result = await self.route_message(msgs[0])
                    results.append(result)
                else:
                    # Multiple broadcasts - route in parallel
                    batch_tasks = [self.route_message(msg) for msg in msgs]
                    batch_results = await asyncio.gather(*batch_tasks)
                    results.extend(batch_results)
        
        return results
    
    def _cache_message(self, message: TeamMessage) -> None:
        """Cache a message for potential reuse.
        
        Args:
            message: Message to cache
        """
        # Add to cache
        self._message_cache[message.message_id] = message
        
        # Trim cache if needed
        if len(self._message_cache) > self._cache_size:
            # Remove oldest messages
            overflow = len(self._message_cache) - self._cache_size
            oldest_keys = list(self._message_cache.keys())[:overflow]
            
            for key in oldest_keys:
                del self._message_cache[key]
    
    def get_cached_message(self, message_id: str) -> Optional[TeamMessage]:
        """Get a message from the cache.
        
        Args:
            message_id: ID of the message to retrieve
            
        Returns:
            Cached message or None if not found
        """
        return self._message_cache.get(message_id)
    
    def configure_group_routing(self) -> Optional[GroupRoutingStrategy]:
        """Configure group-based routing.
        
        Returns:
            Group routing strategy or None if not available
        """
        if not isinstance(self._routing_strategy, GroupRoutingStrategy):
            self.set_routing_strategy("group")
            
        if isinstance(self._routing_strategy, GroupRoutingStrategy):
            return self._routing_strategy
            
        return None
