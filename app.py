"""
Flask Web Application for JARVIS
Connects the web interface (main.html) with the JARVIS backend (main.py, education.py, control.py)
"""

from flask import Flask, render_template, request, jsonify, session
from control import SystemController
from education import EducationAssistant
from conversation_state import ConversationState
from groq import Groq
import os
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Required for sessions

# Enable CORS if available (optional)
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    # CORS not installed, but not needed for same-origin requests
    pass

# Initialize JARVIS components
print("Initializing JARVIS backend...")
system_controller = SystemController()
education = EducationAssistant()

# GROQ API Configuration (for AI responses)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your-api-key-here")
GROQ_MODEL = "llama-3.1-8b-instant"

try:
    groq_client = Groq(api_key=GROQ_API_KEY)
    conversation_history = []
    
    # JARVIS personality
    jarvis_prompt = """You are JARVIS, the AI assistant from Iron Man. Personality:
- Professional, sophisticated, British accent personality
- Highly intelligent and helpful
- Calm and composed
- Speak concisely - 1-3 sentences max for normal conversation
- Occasionally show dry wit
- Refer to the user as "Sir" occasionally
- Be helpful and efficient
- Can joke if want to

Keep responses SHORT for natural conversation."""

    conversation_history.append({
        "role": "system",
        "content": jarvis_prompt
    })
    groq_available = True
except Exception as e:
    print(f"Warning: GROQ API not available: {e}")
    groq_available = False


@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('main.html')


@app.route('/api/message', methods=['POST'])
def handle_message():
    """Handle user messages/commands"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'success': False, 'error': 'No message provided'}), 400
        
        # Initialize conversation state in session if not exists
        if 'conversation' not in session:
            session['conversation'] = {
                'active': False,
                'context_type': None,
                'gathered_data': {},
                'next_field': None
            }
        
        # Create ConversationState object from session
        conv_state = ConversationState()
        conv_state.active = session['conversation']['active']
        conv_state.context_type = session['conversation']['context_type']
        conv_state.gathered_data = session['conversation']['gathered_data']
        conv_state.next_field = session['conversation']['next_field']
        
        # Check if we're in an active conversation (waiting for response)
        if conv_state.is_waiting_for_response():
            # This is a response to a question in an ongoing conversation
            print(f"📝 Continuing conversation... Response: {user_message}")
            
            # Try to extract multiple pieces of information from the message
            # (users often provide all info in one message like "physics topic acceleration deadline next week")
            if conv_state.context_type == 'add_assignment':
                # Extract course, description, and due_date from the message if possible
                user_lower = user_message.lower()
                
                # Extract due date FIRST (it's usually at the end with keywords like "deadline", "due")
                if 'due_date' not in conv_state.gathered_data:
                    due_patterns = ['deadline ', 'due ', 'due date ', 'by ', 'on ']
                    for pattern in due_patterns:
                        if pattern in user_lower:
                            idx = user_lower.find(pattern)
                            due_part = user_message[idx + len(pattern):].strip()
                            # Take everything after the keyword as the date
                            conv_state.gathered_data['due_date'] = due_part
                            break
                    # Also check for date words directly (tomorrow, next week, etc.)
                    if 'due_date' not in conv_state.gathered_data:
                        date_phrases = ['next week', 'this week', 'tomorrow', 'today']
                        for phrase in date_phrases:
                            if phrase in user_lower:
                                conv_state.gathered_data['due_date'] = phrase
                                break
                        # Check for day names
                        if 'due_date' not in conv_state.gathered_data:
                            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                            for day in days:
                                if day in user_lower:
                                    conv_state.gathered_data['due_date'] = day
                                    break
                
                # Extract description/topic (look for "topic", "about", etc.)
                if 'description' not in conv_state.gathered_data:
                    topic_keywords = ['topic ', 'about ', 'assignment ', 'homework ', 'project ']
                    for keyword in topic_keywords:
                        if keyword in user_lower:
                            idx = user_lower.find(keyword)
                            topic_part = user_message[idx + len(keyword):].strip()
                            # Remove due date part if present
                            for due_pattern in ['deadline ', 'due ', 'due date ', 'by ', 'on ']:
                                if due_pattern in topic_part.lower():
                                    topic_part = topic_part.split(due_pattern)[0].strip()
                            # Remove date phrases
                            for date_phrase in ['next week', 'this week', 'tomorrow', 'today', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                                if date_phrase in topic_part.lower():
                                    topic_part = topic_part.split(date_phrase)[0].strip()
                            if topic_part:
                                conv_state.gathered_data['description'] = topic_part
                                break
                
                # Extract course (usually first word or after "for")
                if 'course' not in conv_state.gathered_data:
                    course_keywords = ['for ', 'course ', 'class ', 'subject ']
                    course_found = False
                    for keyword in course_keywords:
                        if keyword in user_lower:
                            parts = user_lower.split(keyword, 1)
                            if len(parts) > 1:
                                course_part = parts[1].strip().split()[0]
                                conv_state.gathered_data['course'] = course_part.title()
                                course_found = True
                                break
                    # If no keyword, assume first word is the course (if not a keyword itself)
                    if not course_found:
                        first_word = user_lower.split()[0]
                        if first_word not in ['topic', 'about', 'assignment', 'homework', 'deadline', 'due', 'by', 'on', 'the', 'a', 'an']:
                            conv_state.gathered_data['course'] = first_word.title()
                
                # Fallback: If we're waiting for a specific field and haven't extracted it yet,
                # assume the whole message is the answer (for simple responses like just "acceleration")
                if conv_state.next_field == 'course' and 'course' not in conv_state.gathered_data:
                    # Simple answer to "What course?"
                    if len(user_message.split()) <= 2:
                        conv_state.gathered_data['course'] = user_message.strip().title()
                elif conv_state.next_field == 'description' and 'description' not in conv_state.gathered_data:
                    # Simple answer to "What's the assignment about?"
                    # If message doesn't look like a date, treat it as description
                    date_keywords = ['deadline', 'due', 'by', 'on', 'tomorrow', 'today', 'next week', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    if not any(kw in user_lower for kw in date_keywords):
                        conv_state.gathered_data['description'] = user_message.strip()
                elif conv_state.next_field == 'due_date' and 'due_date' not in conv_state.gathered_data:
                    # Simple answer to "When is it due?"
                    conv_state.gathered_data['due_date'] = user_message.strip()
                
                # Determine next field to ask for
                if 'course' not in conv_state.gathered_data:
                    conv_state.next_field = 'course'
                elif 'description' not in conv_state.gathered_data:
                    conv_state.next_field = 'description'
                elif 'due_date' not in conv_state.gathered_data:
                    conv_state.next_field = 'due_date'
                else:
                    conv_state.next_field = None
            
            else:
                # For other conversation types, use normal flow
                conv_state.add_response(user_message)
            
            # Update session
            session['conversation']['gathered_data'] = conv_state.gathered_data
            session['conversation']['next_field'] = conv_state.next_field
            
            # Check if conversation is complete
            if conv_state.is_complete():
                # We have all the data, execute the action
                print("✅ Got all information, processing...")
                data = conv_state.get_data()
                
                if conv_state.context_type == 'add_assignment':
                    success, message = system_controller.add_assignment_interactive(
                        data['course'],
                        data['description'],
                        data['due_date']
                    )
                    
                    # Reset conversation
                    conv_state.reset()
                    session['conversation'] = {
                        'active': False,
                        'context_type': None,
                        'gathered_data': {},
                        'next_field': None
                    }
                    
                    return jsonify({
                        'success': success,
                        'message': message if success else f"Sorry, {message}",
                        'command_type': 'add_assignment_complete',
                        'conversation_complete': True
                    })
            else:
                # Ask next question
                next_question = conv_state.get_question()
                print(f"❓ JARVIS asks: {next_question}")
                
                return jsonify({
                    'success': True,
                    'message': next_question,
                    'command_type': 'conversation_question',
                    'conversation_active': True,
                    'waiting_for': conv_state.next_field
                })
        
        # Normal command processing (not in conversation)
        cmd_type, details = system_controller.check_command(user_message)
        
        if cmd_type:
            # Check if this command needs conversation
            if cmd_type == "add_assignment_prompt":
                # Start conversation
                conv_state.start_conversation('add_assignment')
                session['conversation'] = {
                    'active': conv_state.active,
                    'context_type': conv_state.context_type,
                    'gathered_data': conv_state.gathered_data,
                    'next_field': conv_state.next_field
                }
                
                question = conv_state.get_question()
                return jsonify({
                    'success': True,
                    'message': f"I'll help you add that assignment. {question}",
                    'command_type': 'add_assignment_prompt',
                    'conversation_active': True,
                    'waiting_for': conv_state.next_field
                })
            
            # Execute other commands normally
            result = system_controller.execute_command(cmd_type, details)
            
            if len(result) == 3:
                success, message, extra_data = result
            else:
                success, message = result
                extra_data = None
            
            response_data = {
                'success': success,
                'message': message,
                'command_type': cmd_type,
                'extra_data': extra_data
            }
            
            # Add conversation history for AI context
            if success and groq_available:
                conversation_history.append({
                    "role": "user",
                    "content": user_message
                })
                conversation_history.append({
                    "role": "assistant",
                    "content": message
                })
            
            return jsonify(response_data)
        
        # Regular AI conversation
        if groq_available:
            conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=conversation_history,
                    model=GROQ_MODEL,
                    temperature=0.7,
                    max_tokens=200,
                )
                
                ai_response = chat_completion.choices[0].message.content
                
                conversation_history.append({
                    "role": "assistant",
                    "content": ai_response
                })
                
                return jsonify({
                    'success': True,
                    'message': ai_response,
                    'command_type': 'ai_chat'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'AI service error: {str(e)}',
                    'message': "I'm having trouble processing that right now. Please try again."
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'AI service not available',
                'message': "I'm currently unavailable. Please check my configuration."
            }), 503
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/assignments', methods=['GET'])
def get_assignments():
    """Get assignments with optional filter"""
    try:
        # Reload data from file to ensure we have the latest assignments
        education.data = education._load_data()
        
        filter_type = request.args.get('filter', 'all')
        assignments = education.get_assignments(filter_type)
        
        # Format assignments for JSON response
        formatted_assignments = []
        now = datetime.now()
        
        for a in assignments:
            due = datetime.fromisoformat(a["due_date"])
            days_until = (due - now).days
            
            # Determine priority
            if days_until < 0:
                priority = 'high'
            elif days_until == 0:
                priority = 'high'
            elif days_until == 1:
                priority = 'medium'
            elif days_until <= 3:
                priority = 'medium'
            else:
                priority = 'low'
            
            formatted_assignments.append({
                'id': a['id'],
                'course': a['course'],
                'description': a['description'],
                'due_date': a['due_date'],
                'days_until': days_until,
                'priority': priority,
                'completed': a.get('completed', False)
            })
        
        return jsonify({
            'success': True,
            'assignments': formatted_assignments,
            'count': len(formatted_assignments)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/diagnostics', methods=['GET'])
def get_diagnostics():
    """Get system diagnostics"""
    try:
        success, diagnostics = system_controller.get_system_diagnostics()
        
        if success:
            return jsonify({
                'success': True,
                'diagnostics': diagnostics
            })
        else:
            return jsonify({
                'success': False,
                'error': diagnostics.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/daily-brief', methods=['GET'])
def get_daily_brief():
    """Get daily brief statistics"""
    try:
        # Reload data from file to ensure we have the latest assignments
        education.data = education._load_data()
        
        # Get assignments
        all_assignments = education.get_assignments('all')
        urgent_assignments = education.get_assignments('urgent')
        
        # Count classes (courses with assignments)
        courses = set(a['course'] for a in all_assignments)
        classes_count = len(courses)
        
        # Count due soon (within 3 days)
        due_soon_count = len(urgent_assignments)
        
        # Get today's study plan
        today_study_plan = education.get_today_study_plan()
        study_hours = 0
        if today_study_plan:
            study_hours = sum(task['hours'] for task in today_study_plan)
        
        return jsonify({
            'success': True,
            'brief': {
                'classes': classes_count,
                'due_soon': due_soon_count,
                'study_hours': study_hours
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/study-plans', methods=['GET'])
def get_study_plans():
    """Get active study plans"""
    try:
        # Get today's study plan
        today_tasks = education.get_today_study_plan()
        
        return jsonify({
            'success': True,
            'today_tasks': today_tasks or [],
            'has_tasks': today_tasks is not None and len(today_tasks) > 0
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/music/<filename>')
def serve_music(filename):
    """Serve music files"""
    from flask import send_from_directory
    import os
    
    # Security: Only allow specific music files
    allowed_files = ['cornfieldchase.mp3', 'oppenheimer.mp3']
    if filename not in allowed_files:
        return jsonify({'error': 'File not allowed'}), 403
    
    # Check if file exists
    if not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404
    
    return send_from_directory('.', filename, mimetype='audio/mpeg')


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 JARVIS Web Interface Starting...")
    print("="*60)
    print("📍 Server: http://localhost:5000")
    print("📚 API Endpoints:")
    print("   - POST /api/message - Send message to JARVIS")
    print("   - GET  /api/assignments - Get assignments")
    print("   - GET  /api/diagnostics - Get system diagnostics")
    print("   - GET  /api/daily-brief - Get daily brief stats")
    print("   - GET  /api/study-plans - Get study plans")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)