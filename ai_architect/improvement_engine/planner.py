from typing import List
from ..data.models import AuditTicket, SprintDay

class SprintPlanner:
    def __init__(self, hours_per_day: float = 5.0, total_days: int = 5):
        self.hours_per_day = hours_per_day
        self.total_days = total_days
        self.days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    def plan_sprint(self, tickets: List[AuditTicket]) -> List[SprintDay]:
        """
        Greedy scheduling algorithm to distribute tickets across days based on priority and effort.
        """
        # Define priority weights
        priority_map = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        
        # Sort tickets by priority (highest first) and then effort (smallest first to fit more)
        sorted_tickets = sorted(
            tickets, 
            key=lambda x: (priority_map.get(x.priority, 2), x.effort_hours)
        )

        sprint_days = []
        ticket_index = 0
        total_tickets = len(sorted_tickets)

        for i in range(self.total_days):
            day_name = self.days_names[i] if i < len(self.days_names) else f"Day {i+1}"
            day_tickets = []
            remaining_hours = self.hours_per_day

            while ticket_index < total_tickets:
                ticket = sorted_tickets[ticket_index]
                # If the ticket fits OR the day is empty (prevents skipping large tasks)
                if ticket.effort_hours <= remaining_hours or not day_tickets:
                    day_tickets.append(ticket)
                    remaining_hours -= ticket.effort_hours
                    ticket_index += 1
                else:
                    # Not enough time today
                    break
            
            sprint_days.append(SprintDay(
                day=day_name,
                tickets=day_tickets,
                total_hours=float(self.hours_per_day - remaining_hours)
            ))

        return sprint_days
