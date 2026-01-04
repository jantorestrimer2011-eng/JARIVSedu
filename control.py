"""
JARVIS System Control Module (Enhanced)
Handles system diagnostics, web search, and education features
control.py
"""

import psutil  # pip install psutil
import webbrowser
import urllib.parse
from education import EducationAssistant


class SystemController:
    def __init__(self):
        print(f"✓ System Controller initialized (Diagnostics & Search)")
        # Initialize Education Assistant
        self.education = EducationAssistant()
    
    def get_system_diagnostics(self):
        """
        Get comprehensive system diagnostics
        Returns: (success, diagnostics_dict)
        """
        try:
            diagnostics = {}
            
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=1)
            diagnostics['cpu_usage'] = f"{cpu_percent}%"
            
            # CPU Temperature
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try to get the most relevant temperature
                    if 'coretemp' in temps:
                        cpu_temp = temps['coretemp'][0].current
                    elif 'cpu_thermal' in temps:
                        cpu_temp = temps['cpu_thermal'][0].current
                    elif 'acpitz' in temps:
                        cpu_temp = temps['acpitz'][0].current
                    else:
                        # Get first available temperature
                        first_key = list(temps.keys())[0]
                        cpu_temp = temps[first_key][0].current
                    
                    diagnostics['cpu_temp'] = f"{cpu_temp}°C"
                else:
                    diagnostics['cpu_temp'] = "Not available"
            except (AttributeError, KeyError, IndexError):
                # Temperature sensors not available
                diagnostics['cpu_temp'] = "Not available"
            
            # RAM Usage
            memory = psutil.virtual_memory()
            ram_used_gb = memory.used / (1024**3)
            ram_total_gb = memory.total / (1024**3)
            ram_percent = memory.percent
            diagnostics['ram_usage'] = f"{ram_used_gb:.1f}GB / {ram_total_gb:.1f}GB ({ram_percent}%)"
            diagnostics['ram_percent'] = ram_percent
            
            # Battery Status
            try:
                battery = psutil.sensors_battery()
                if battery:
                    battery_percent = battery.percent
                    plugged = "Charging" if battery.power_plugged else "On Battery"
                    
                    # Time remaining
                    if battery.secsleft == -1:
                        time_left = "Calculating..."
                    elif battery.secsleft == -2:
                        time_left = "Unlimited (Plugged In)"
                    else:
                        hours = battery.secsleft // 3600
                        minutes = (battery.secsleft % 3600) // 60
                        time_left = f"{hours}h {minutes}m remaining"
                    
                    diagnostics['battery_percent'] = f"{battery_percent}%"
                    diagnostics['battery_status'] = plugged
                    diagnostics['battery_time'] = time_left
                else:
                    diagnostics['battery_percent'] = "No battery detected"
                    diagnostics['battery_status'] = "Desktop system"
                    diagnostics['battery_time'] = "N/A"
            except Exception:
                diagnostics['battery_percent'] = "No battery detected"
                diagnostics['battery_status'] = "Desktop system"
                diagnostics['battery_time'] = "N/A"
            
            # Disk Usage
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            disk_percent = disk.percent
            diagnostics['disk_usage'] = f"{disk_used_gb:.1f}GB / {disk_total_gb:.1f}GB ({disk_percent}%)"
            
            return True, diagnostics
            
        except Exception as e:
            return False, {"error": str(e)}
    
    def format_diagnostics_speech(self, diagnostics):
        """
        Format diagnostics data into natural speech
        Returns: formatted string for TTS
        """
        parts = []
        
        # Battery
        if diagnostics.get('battery_percent') != "No battery detected":
            parts.append(f"Battery is at {diagnostics['battery_percent']}, {diagnostics['battery_status']}")
        
        # CPU
        parts.append(f"CPU usage is {diagnostics['cpu_usage']}")
        if diagnostics.get('cpu_temp') != "Not available":
            parts.append(f"CPU temperature is {diagnostics['cpu_temp']}")
        
        # RAM
        parts.append(f"RAM usage is at {diagnostics.get('ram_percent', 0):.0f}%")
        
        # Join all parts
        return ". ".join(parts) + "."
    
    def format_diagnostics_display(self, diagnostics):
        """
        Format diagnostics data for console display
        Returns: formatted string
        """
        lines = [
            "\n" + "="*50,
            "SYSTEM DIAGNOSTICS",
            "="*50
        ]
        
        if diagnostics.get('battery_percent') != "No battery detected":
            lines.append(f"🔋 Battery:        {diagnostics['battery_percent']} ({diagnostics['battery_status']})")
            if diagnostics.get('battery_time') != "N/A":
                lines.append(f"   Time:          {diagnostics['battery_time']}")
        
        lines.append(f"🖥️  CPU Usage:      {diagnostics['cpu_usage']}")
        
        if diagnostics.get('cpu_temp') != "Not available":
            lines.append(f"🌡️  CPU Temp:       {diagnostics['cpu_temp']}")
        
        lines.append(f"💾 RAM Usage:      {diagnostics['ram_usage']}")
        lines.append(f"💿 Disk Usage:     {diagnostics['disk_usage']}")
        lines.append("="*50 + "\n")
        
        return "\n".join(lines)
    
    def web_search(self, query):
        """
        Open web browser with search query
        Returns: (success, message)
        """
        try:
            # Encode the query for URL
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            # Open in default browser
            webbrowser.open(search_url)
            
            return True, f"Searching for {query}"
        except Exception as e:
            return False, f"Error opening browser: {e}"
    
    def check_command(self, text):
        """
        Check if the text contains any command (system, education, or search)
        Returns: (command_type, details) or (None, None)
        Priority: Education > System > Search
        """
        text_lower = text.lower()
        
        # PRIORITY 1: Check Education Commands First
        edu_cmd, edu_details = self.education.check_command(text)
        if edu_cmd:
            return edu_cmd, edu_details
        
        # PRIORITY 2: System Diagnostics
        if any(phrase in text_lower for phrase in [
            "system diagnostics",
            "system diagnostic",
            "run diagnostics",
            "system status",
            "system check",
            "check system",
            "system report",
            "system info",
            "system information"
        ]):
            return "diagnostics", None
        
        # PRIORITY 3: Focus Mode Commands
        focus_keywords = ["focus mode", "focus", "focus timer", "study timer", "pomodoro"]
        
        # Turn on focus mode
        if any(phrase in text_lower for phrase in [
            "turn on focus mode", "start focus mode", "enable focus mode",
            "activate focus mode", "begin focus mode", "start focus",
            "turn on focus", "enable focus", "start study timer"
        ]):
            # Try to extract duration (e.g., "30 minutes", "1 hour")
            duration = None
            import re
            numbers = re.findall(r'\d+', text_lower)
            if numbers:
                num = int(numbers[0])
                if "hour" in text_lower or "hr" in text_lower:
                    duration = num * 60  # Convert to minutes
                elif "minute" in text_lower or "min" in text_lower:
                    duration = num
                else:
                    duration = num  # Default to minutes
            else:
                duration = 25  # Default 25 minutes (Pomodoro)
            
            return "focus_mode_start", {"duration": duration}
        
        # Turn off/stop focus mode
        if any(phrase in text_lower for phrase in [
            "turn off focus mode", "stop focus mode", "disable focus mode",
            "deactivate focus mode", "end focus mode", "stop focus",
            "turn off focus", "disable focus", "stop study timer"
        ]):
            return "focus_mode_stop", None
        
        # Pause focus mode
        if any(phrase in text_lower for phrase in [
            "pause focus mode", "pause focus", "pause timer",
            "pause study timer"
        ]):
            return "focus_mode_pause", None
        
        # Resume focus mode
        if any(phrase in text_lower for phrase in [
            "resume focus mode", "resume focus", "resume timer",
            "resume study timer", "continue focus mode"
        ]):
            return "focus_mode_resume", None
        
        # Extend focus mode
        if any(phrase in text_lower for phrase in [
            "extend focus mode", "extend focus", "extend timer",
            "add time", "extend study timer"
        ]):
            # Try to extract extension duration
            extension = 15  # Default 15 minutes
            import re
            numbers = re.findall(r'\d+', text_lower)
            if numbers:
                num = int(numbers[0])
                if "hour" in text_lower or "hr" in text_lower:
                    extension = num * 60
                elif "minute" in text_lower or "min" in text_lower:
                    extension = num
                else:
                    extension = num
            
            return "focus_mode_extend", {"minutes": extension}
        
        # PRIORITY 4: Music Commands
        music_keywords = ["music", "song", "play", "stop"]
        
        # Play music
        if any(phrase in text_lower for phrase in [
            "play music", "play the music", "start music", "play song"
        ]):
            # Try to detect which song
            music_file = "cornfieldchase.mp3"  # Default
            if "oppenheimer" in text_lower:
                music_file = "oppenheimer.mp3"
            elif "cornfield" in text_lower or "cornfield chase" in text_lower:
                music_file = "cornfieldchase.mp3"
            
            return "music_play", {"file": music_file}
        
        # Stop music
        if any(phrase in text_lower for phrase in [
            "stop music", "stop the music", "pause music", "stop song"
        ]):
            return "music_stop", None
        
        # PRIORITY 5: Web Search
        search_triggers = [
            "search for ",
            "search ",
            "google ",
            "look up ",
            "find information about ",
            "search the web for "
        ]
        
        for trigger in search_triggers:
            if trigger in text_lower:
                # Extract search query after trigger
                idx = text_lower.find(trigger)
                query = text[idx + len(trigger):].strip()
                
                # Remove common stop words at the end
                for word in [" please", " for me", " now"]:
                    if query.lower().endswith(word):
                        query = query[:-len(word)].strip()
                
                if query:
                    return "search", query
        
        return None, None
    
    def execute_command(self, command_type, details=None):
        """
        Execute any command (system, education, or search)
        Returns: (success, message, extra_data)
        """
        
        # EDUCATION COMMANDS
        if command_type in ["add_assignment_prompt", "view_assignments", 
                           "create_study_plan_prompt", "today_study_plan"]:
            return self.education.execute_command(command_type, details or {})
        
        # SYSTEM DIAGNOSTICS
        elif command_type == "diagnostics":
            success, diagnostics = self.get_system_diagnostics()
            if success:
                # Return both display and speech versions
                display = self.format_diagnostics_display(diagnostics)
                speech = self.format_diagnostics_speech(diagnostics)
                return True, speech, {"display": display, "diagnostics": diagnostics}
            else:
                return False, "Error getting system diagnostics", None
        
        # FOCUS MODE COMMANDS
        elif command_type in ["focus_mode_start", "focus_mode_stop", "focus_mode_pause", 
                            "focus_mode_resume", "focus_mode_extend"]:
            # These commands are handled by the frontend
            # Return command info for frontend to process
            return True, f"Focus mode command: {command_type}", {
                "command": command_type,
                "details": details
            }
        
        # MUSIC COMMANDS
        elif command_type in ["music_play", "music_stop"]:
            # These commands are handled by the frontend
            return True, f"Music command: {command_type}", {
                "command": command_type,
                "details": details
            }
        
        # WEB SEARCH
        elif command_type == "search":
            if details:
                success, msg = self.web_search(details)
                return success, msg, None
            else:
                return False, "No search query specified", None
        
        return False, "Unknown command", None
    
    def add_assignment_interactive(self, course, description, due_date):
        """Helper method for adding assignments from interactive conversation"""
        return self.education.add_assignment(course, description, due_date)
    
    def create_study_plan_interactive(self, subject, exam_date, hours_per_day, topics=None):
        """Helper method for creating study plans from interactive conversation"""
        return self.education.create_study_plan(subject, exam_date, hours_per_day, topics)


# Convenience function for easy import
def get_controller():
    """Get a SystemController instance"""
    return SystemController()


if __name__ == "__main__":
    # Test the controller
    print("Testing Enhanced System Controller...")
    controller = SystemController()
    
    print("\n" + "="*60)
    print("TEST 1: System Diagnostics")
    print("="*60)
    success, msg, extra = controller.execute_command("diagnostics")
    if success and extra:
        print(extra['display'])
        print(f"\nSpeech output: {msg}")
    
    print("\n" + "="*60)
    print("TEST 2: View Assignments")
    print("="*60)
    # First add a test assignment
    controller.education.add_assignment("Mathematics", "Chapter 5", "Friday")
    controller.education.add_assignment("Chemistry", "Lab report", "tomorrow")
    
    success, msg, extra = controller.execute_command("view_assignments", {"filter": "all"})
    if success and extra:
        print(extra['display'])
        print(f"\nSpeech output: {msg}")
    
    print("\n" + "="*60)
    print("TEST 3: Create Study Plan")
    print("="*60)
    success, msg, plan = controller.education.create_study_plan(
        "Biology", "next Monday", 2.0, ["Cells", "DNA", "Evolution"]
    )
    if success and plan:
        print(controller.education.format_study_plan_display(plan))
        print(f"\nSpeech output: {msg}")
    
    print("\n" + "="*60)
    print("TEST 4: Command Detection")
    print("="*60)
    test_commands = [
        "add my physics assignment",
        "what's due this week",
        "help me study for chemistry",
        "system diagnostics",
        "search for python tutorials",
        "what should I study today"
    ]
    
    for cmd in test_commands:
        cmd_type, details = controller.check_command(cmd)
        print(f"'{cmd}' -> Type: {cmd_type}, Details: {details}")