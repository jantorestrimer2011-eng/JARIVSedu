"""
Conversation State Manager for JARVIS
Handles multi-turn conversations with wake word between each exchange
"""


class ConversationState:
    def __init__(self):
        self.active = False
        self.context_type = None  # 'add_assignment' or 'create_study_plan'
        self.gathered_data = {}
        self.current_question = None
        self.next_field = None
    
    def start_conversation(self, context_type, initial_data=None):
        """Start a new conversation"""
        self.active = True
        self.context_type = context_type
        self.gathered_data = initial_data or {}
        
        # Determine what to ask first
        if context_type == 'add_assignment':
            self.next_field = self._get_next_assignment_field()
        elif context_type == 'create_study_plan':
            self.next_field = self._get_next_study_plan_field()
    
    def _get_next_assignment_field(self):
        """Determine next field needed for assignment"""
        if 'course' not in self.gathered_data:
            return 'course'
        elif 'description' not in self.gathered_data:
            return 'description'
        elif 'due_date' not in self.gathered_data:
            return 'due_date'
        return None
    
    def _get_next_study_plan_field(self):
        """Determine next field needed for study plan"""
        if 'subject' not in self.gathered_data:
            return 'subject'
        elif 'exam_date' not in self.gathered_data:
            return 'exam_date'
        elif 'hours_per_day' not in self.gathered_data:
            return 'hours_per_day'
        return None
    
    def get_question(self):
        """Get the question to ask based on next_field"""
        if self.context_type == 'add_assignment':
            questions = {
                'course': "What course is it for?",
                'description': "What's the assignment about?",
                'due_date': "When is it due?"
            }
            return questions.get(self.next_field, "")
        
        elif self.context_type == 'create_study_plan':
            questions = {
                'subject': "What subject is the exam on?",
                'exam_date': "When is the exam?",
                'hours_per_day': "How many hours per day can you study?"
            }
            return questions.get(self.next_field, "")
        
        return ""
    
    def add_response(self, response):
        """Add user's response and update state"""
        if not self.active or not self.next_field:
            return False
        
        # Store the response
        self.gathered_data[self.next_field] = response.strip()
        
        # Move to next field
        if self.context_type == 'add_assignment':
            self.next_field = self._get_next_assignment_field()
        elif self.context_type == 'create_study_plan':
            self.next_field = self._get_next_study_plan_field()
        
        return True
    
    def is_complete(self):
        """Check if we have all required data"""
        return self.active and self.next_field is None
    
    def is_waiting_for_response(self):
        """Check if we're waiting for user to respond"""
        return self.active and self.next_field is not None
    
    def get_data(self):
        """Get the gathered data"""
        return self.gathered_data.copy()
    
    def reset(self):
        """Reset conversation state"""
        self.active = False
        self.context_type = None
        self.gathered_data = {}
        self.current_question = None
        self.next_field = None
    
    def __repr__(self):
        return f"ConversationState(active={self.active}, type={self.context_type}, field={self.next_field})"