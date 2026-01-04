"""
JARVIS Education Module
Feature 1: Assignment & Deadline Manager
Feature 2: Smart Study Planner
education.py
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


class EducationAssistant:
    def __init__(self, data_file="jarvis_education_data.json"):
        self.data_file = data_file
        self.data = self._load_data()
        print(f"✓ Education Assistant initialized (Assignments & Study Plans)")
    
    def _load_data(self) -> Dict:
        """Load data from JSON file or create new structure"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default structure
        return {
            "assignments": [],
            "study_plans": [],
            "courses": []
        }
    
    def _save_data(self):
        """Save data to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse natural language dates"""
        date_str = date_str.lower().strip()
        today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
        
        # Day of week
        days = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }
        
        # Relative dates
        if date_str in ['today', 'tonight']:
            return today
        elif date_str == 'tomorrow':
            return today + timedelta(days=1)
        elif 'next week' in date_str:
            return today + timedelta(days=7)
        
        # Check for day of week
        for day_name, day_num in days.items():
            if day_name in date_str:
                current_day = today.weekday()
                days_ahead = (day_num - current_day) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next occurrence
                return today + timedelta(days=days_ahead)
        
        # Try parsing specific formats
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m/%d', '%d/%m']:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # If no year specified, assume current year
                if parsed.year == 1900:
                    parsed = parsed.replace(year=today.year)
                parsed = parsed.replace(hour=23, minute=59, second=59)
                return parsed
            except:
                continue
        
        return None
    
    # ==================== FEATURE 1: ASSIGNMENT MANAGER ====================
    
    def add_assignment(self, course: str, description: str, due_date_str: str) -> Tuple[bool, str]:
        """Add a new assignment"""
        # Reload data from file to get latest state (in case multiple instances)
        self.data = self._load_data()
        
        due_date = self._parse_date(due_date_str)
        
        if not due_date:
            return False, "I couldn't understand that date. Try 'Friday', 'tomorrow', or '12/25'."
        
        assignment = {
            "id": len(self.data["assignments"]) + 1,
            "course": course,
            "description": description,
            "due_date": due_date.isoformat(),
            "completed": False,
            "added_date": datetime.now().isoformat()
        }
        
        self.data["assignments"].append(assignment)
        
        # Add course if new
        if course not in self.data["courses"]:
            self.data["courses"].append(course)
        
        self._save_data()
        
        days_until = (due_date - datetime.now()).days
        if days_until == 0:
            time_str = "today"
        elif days_until == 1:
            time_str = "tomorrow"
        else:
            time_str = f"in {days_until} days"
        
        return True, f"Added {course} assignment due {time_str}."
    
    def get_assignments(self, filter_type: str = "all") -> List[Dict]:
        """Get assignments with optional filtering"""
        assignments = [a for a in self.data["assignments"] if not a["completed"]]
        
        # Sort by due date
        assignments.sort(key=lambda x: x["due_date"])
        
        if filter_type == "all":
            return assignments
        
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if filter_type == "today":
            return [a for a in assignments if datetime.fromisoformat(a["due_date"]) < today + timedelta(days=1)]
        
        elif filter_type == "this_week":
            week_end = today + timedelta(days=7)
            return [a for a in assignments if datetime.fromisoformat(a["due_date"]) < week_end]
        
        elif filter_type == "urgent":
            three_days = today + timedelta(days=3)
            return [a for a in assignments if datetime.fromisoformat(a["due_date"]) < three_days]
        
        return assignments
    
    def format_assignments_speech(self, assignments: List[Dict]) -> str:
        """Format assignments for speech output"""
        if not assignments:
            return "You have no upcoming assignments. Well done!"
        
        parts = []
        now = datetime.now()
        
        for a in assignments[:5]:  # Limit to 5 for speech
            due = datetime.fromisoformat(a["due_date"])
            days_until = (due - now).days
            
            if days_until == 0:
                time_str = "today"
            elif days_until == 1:
                time_str = "tomorrow"
            elif days_until < 0:
                time_str = "overdue"
            else:
                time_str = f"in {days_until} days"
            
            parts.append(f"{a['course']}, {time_str}")
        
        if len(assignments) > 5:
            parts.append(f"and {len(assignments) - 5} more")
        
        return f"You have {len(assignments)} assignments: " + ", ".join(parts) + "."
    
    def format_assignments_display(self, assignments: List[Dict]) -> str:
        """Format assignments for console display"""
        if not assignments:
            return "\n📚 No upcoming assignments!\n"
        
        lines = [
            "\n" + "="*60,
            f"📚 UPCOMING ASSIGNMENTS ({len(assignments)})",
            "="*60
        ]
        
        now = datetime.now()
        
        for a in assignments:
            due = datetime.fromisoformat(a["due_date"])
            days_until = (due - now).days
            
            if days_until < 0:
                urgency = "🔴 OVERDUE"
            elif days_until == 0:
                urgency = "🔴 TODAY"
            elif days_until == 1:
                urgency = "🟡 TOMORROW"
            elif days_until <= 3:
                urgency = f"🟡 {days_until} DAYS"
            else:
                urgency = f"🟢 {days_until} DAYS"
            
            lines.append(f"{urgency:15} | {a['course']:15} | {a['description']}")
        
        lines.append("="*60 + "\n")
        return "\n".join(lines)
    
    def complete_assignment(self, assignment_id: int) -> Tuple[bool, str]:
        """Mark an assignment as completed"""
        for a in self.data["assignments"]:
            if a["id"] == assignment_id:
                a["completed"] = True
                a["completed_date"] = datetime.now().isoformat()
                self._save_data()
                return True, f"Marked {a['course']} assignment as complete. Well done!"
        
        return False, "Assignment not found."
    
    # ==================== FEATURE 2: STUDY PLANNER ====================
    
    def create_study_plan(self, exam_subject: str, exam_date_str: str, 
                         hours_per_day: float, topics: Optional[List[str]] = None) -> Tuple[bool, str, Optional[Dict]]:
        """Create a smart study plan"""
        exam_date = self._parse_date(exam_date_str)
        
        if not exam_date:
            return False, "I couldn't understand the exam date. Try 'Monday', 'next Friday', or '12/15'.", None
        
        now = datetime.now()
        days_until = (exam_date - now).days
        
        if days_until < 0:
            return False, "That exam date is in the past.", None
        
        if days_until == 0:
            return False, "Your exam is today! It's too late for a study plan.", None
        
        # Calculate study sessions
        total_hours = days_until * hours_per_day
        
        # Default topics if none provided
        if not topics:
            topics = [f"Topic {i+1}" for i in range(min(5, days_until))]
        
        # Distribute topics across days
        hours_per_topic = total_hours / len(topics)
        
        # Create daily schedule
        schedule = []
        current_date = now + timedelta(days=1)
        current_date = current_date.replace(hour=0, minute=0, second=0)
        
        topic_index = 0
        hours_on_current_topic = 0
        
        for day in range(days_until):
            day_date = current_date + timedelta(days=day)
            
            # What to study this day
            current_topic = topics[topic_index % len(topics)]
            hours_remaining_on_topic = hours_per_topic - hours_on_current_topic
            
            if hours_per_day <= hours_remaining_on_topic:
                # Full day on current topic
                schedule.append({
                    "day": day + 1,
                    "date": day_date.strftime("%A, %B %d"),
                    "topic": current_topic,
                    "hours": hours_per_day,
                    "completed": False
                })
                hours_on_current_topic += hours_per_day
            else:
                # Split day between topics
                schedule.append({
                    "day": day + 1,
                    "date": day_date.strftime("%A, %B %d"),
                    "topic": f"{current_topic} (finish)",
                    "hours": hours_per_day,
                    "completed": False
                })
                hours_on_current_topic = 0
                topic_index += 1
            
            # Move to next topic if current is done
            if hours_on_current_topic >= hours_per_topic:
                topic_index += 1
                hours_on_current_topic = 0
        
        # Last day is review
        if schedule:
            schedule[-1]["topic"] = "📋 Final Review"
        
        plan = {
            "id": len(self.data["study_plans"]) + 1,
            "subject": exam_subject,
            "exam_date": exam_date.isoformat(),
            "hours_per_day": hours_per_day,
            "topics": topics,
            "schedule": schedule,
            "created_date": now.isoformat(),
            "total_hours": total_hours,
            "days_until_exam": days_until
        }
        
        self.data["study_plans"].append(plan)
        self._save_data()
        
        speech = f"Study plan created for {exam_subject}. You have {days_until} days to prepare, studying {hours_per_day} hours per day. Let's start with {schedule[0]['topic']}."
        
        return True, speech, plan
    
    def get_today_study_plan(self) -> Optional[Dict]:
        """Get today's study tasks from active plans"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = today.strftime("%A, %B %d")
        
        active_plans = [p for p in self.data["study_plans"] 
                       if datetime.fromisoformat(p["exam_date"]) >= datetime.now()]
        
        today_tasks = []
        
        for plan in active_plans:
            for session in plan["schedule"]:
                if session["date"] == today_str and not session.get("completed", False):
                    today_tasks.append({
                        "subject": plan["subject"],
                        "topic": session["topic"],
                        "hours": session["hours"],
                        "plan_id": plan["id"],
                        "day": session["day"]
                    })
        
        return today_tasks if today_tasks else None
    
    def format_study_plan_display(self, plan: Dict) -> str:
        """Format study plan for console display"""
        lines = [
            "\n" + "="*60,
            f"📖 STUDY PLAN: {plan['subject']}",
            "="*60,
            f"Exam Date: {datetime.fromisoformat(plan['exam_date']).strftime('%A, %B %d')}",
            f"Days to prepare: {plan['days_until_exam']}",
            f"Total study hours: {plan['total_hours']:.1f}",
            f"Hours per day: {plan['hours_per_day']:.1f}",
            "",
            "Daily Schedule:",
            "-" * 60
        ]
        
        for session in plan["schedule"]:
            status = "✅" if session.get("completed") else "⏳"
            lines.append(f"{status} Day {session['day']} ({session['date']}): {session['topic']} - {session['hours']:.1f}h")
        
        lines.append("="*60 + "\n")
        return "\n".join(lines)
    
    def mark_study_session_complete(self, plan_id: int, day: int) -> Tuple[bool, str]:
        """Mark a study session as completed"""
        for plan in self.data["study_plans"]:
            if plan["id"] == plan_id:
                for session in plan["schedule"]:
                    if session["day"] == day:
                        session["completed"] = True
                        self._save_data()
                        
                        # Check if next session exists
                        if day < len(plan["schedule"]):
                            next_topic = plan["schedule"][day]["topic"]
                            return True, f"Great work! Next up: {next_topic}"
                        else:
                            return True, "Study plan completed! You're ready for the exam."
        
        return False, "Study session not found."
    
    # ==================== COMMAND DETECTION ====================
    
    def check_command(self, text: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Check if text contains an education command"""
        text_lower = text.lower().strip()
        
        # SMART QUESTION DETECTION (doesn't rely on punctuation!)
        # Check if sentence STARTS with question words
        question_starters = ["what", "which", "when", "where", "how", "do", "does", "is", "are", "can", "could", "show", "tell", "list"]
        starts_with_question = any(text_lower.startswith(word + " ") for word in question_starters)
        
        # Additional question patterns
        has_question_pattern = any(pattern in text_lower for pattern in [
            "do i have",
            "what assignment",
            "what homework",
            "what task",
            "which assignment",
            "which homework"
        ])
        
        is_question = starts_with_question or has_question_pattern
        
        # PRIORITY 1: VIEW ASSIGNMENTS - If it's a question about assignments
        view_keywords = ["assignment", "homework", "due", "deadline", "task"]
        has_view_keyword = any(keyword in text_lower for keyword in view_keywords)
        
        if is_question and has_view_keyword:
            # Check for time filters
            if "today" in text_lower:
                return "view_assignments", {"filter": "today"}
            elif "this week" in text_lower or "next week" in text_lower or "week" in text_lower:
                return "view_assignments", {"filter": "this_week"}
            elif "tomorrow" in text_lower:
                return "view_assignments", {"filter": "urgent"}
            elif "urgent" in text_lower:
                return "view_assignments", {"filter": "urgent"}
            else:
                return "view_assignments", {"filter": "all"}
        
        # PRIORITY 2: ADD ASSIGNMENT - Only if NOT a question
        if not is_question:
            add_keywords = ["add", "new", "create", "got", "i have"]
            assignment_keywords = ["assignment", "homework", "task", "project", "essay"]
            
            has_add_keyword = any(keyword in text_lower for keyword in add_keywords)
            has_assignment_keyword = any(keyword in text_lower for keyword in assignment_keywords)
            
            if has_add_keyword and has_assignment_keyword:
                return "add_assignment_prompt", {"original_text": text}
        
        # CREATE STUDY PLAN - Enhanced detection
        study_keywords = ["study", "prepare", "exam", "test", "quiz", "midterm", "final"]
        action_keywords = ["help", "plan", "create", "make", "need to"]
        
        has_study_keyword = any(keyword in text_lower for keyword in study_keywords)
        has_action_keyword = any(keyword in text_lower for keyword in action_keywords)
        
        if has_study_keyword and has_action_keyword:
            return "create_study_plan_prompt", {"original_text": text}
        
        # TODAY'S STUDY PLAN - Enhanced detection
        if any(keyword in text_lower for keyword in ["study", "studying"]):
            if "today" in text_lower or "now" in text_lower:
                return "today_study_plan", {}
        
        return None, None
    
    def execute_command(self, command_type: str, details: Dict) -> Tuple[bool, str, Optional[Dict]]:
        """Execute an education command"""
        
        if command_type == "add_assignment_prompt":
            # This will trigger a conversation with the AI to gather details
            return True, "I'll help you add that assignment. What course is it for?", {"needs_info": True, "type": "add_assignment"}
        
        elif command_type == "view_assignments":
            filter_type = details.get("filter", "all")
            assignments = self.get_assignments(filter_type)
            
            display = self.format_assignments_display(assignments)
            speech = self.format_assignments_speech(assignments)
            
            return True, speech, {"display": display, "assignments": assignments}
        
        elif command_type == "create_study_plan_prompt":
            return True, "I'll create a study plan for you. What subject is the exam on, and when is it?", {"needs_info": True, "type": "create_study_plan"}
        
        elif command_type == "today_study_plan":
            today_tasks = self.get_today_study_plan()
            
            if not today_tasks:
                return True, "You have no study sessions planned for today.", None
            
            # Format for speech
            parts = []
            for task in today_tasks:
                parts.append(f"{task['hours']} hours of {task['topic']} for {task['subject']}")
            
            speech = "Today you should study: " + ", and ".join(parts)
            
            # Format for display
            lines = ["\n📖 TODAY'S STUDY PLAN\n" + "="*40]
            for task in today_tasks:
                lines.append(f"• {task['subject']}: {task['topic']} ({task['hours']}h)")
            lines.append("="*40 + "\n")
            display = "\n".join(lines)
            
            return True, speech, {"display": display, "tasks": today_tasks}
        
        return False, "Unknown education command", None


def get_education_assistant():
    """Get an EducationAssistant instance"""
    return EducationAssistant()


if __name__ == "__main__":
    # Test the education assistant
    print("Testing Education Assistant...")
    edu = EducationAssistant()
    
    print("\n" + "="*60)
    print("TEST 1: Add Assignment")
    print("="*60)
    success, msg = edu.add_assignment("Mathematics", "Chapter 5 homework", "Friday")
    print(f"Result: {msg}")
    
    print("\n" + "="*60)
    print("TEST 2: View Assignments")
    print("="*60)
    assignments = edu.get_assignments("all")
    print(edu.format_assignments_display(assignments))
    
    print("\n" + "="*60)
    print("TEST 3: Create Study Plan")
    print("="*60)
    success, msg, plan = edu.create_study_plan(
        "Chemistry", 
        "next Monday", 
        2.5,
        ["Atomic Structure", "Chemical Bonds", "Reactions", "Stoichiometry"]
    )
    if success and plan:
        print(edu.format_study_plan_display(plan))
    
    print("\n" + "="*60)
    print("TEST 4: Command Detection")
    print("="*60)
    test_commands = [
        "add my math assignment due Friday",
        "what's due this week",
        "help me study for my biology exam",
        "what should I study today"
    ]
    
    for cmd in test_commands:
        cmd_type, details = edu.check_command(cmd)
        print(f"'{cmd}' -> Type: {cmd_type}")