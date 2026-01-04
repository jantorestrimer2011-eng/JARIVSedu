"""
Enhanced JARVIS with Conversation Mode
- Detects when you stop speaking (no fixed duration!)
- Multi-turn conversations with wake word between exchanges
- High accuracy, low latency
- Works offline
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import queue
import sys
from scipy.io import wavfile
import tempfile
import os
import time
import asyncio
import edge_tts
import pygame
from groq import Groq
import pvporcupine
import torch

# Import Silero VAD
torch.set_num_threads(1)
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

# Import the system controller and conversation state
from control import SystemController
from conversation_state import ConversationState

# ==================== CONFIGURATION ====================
PICOVOICE_ACCESS_KEY = "your-picovoice-access-key-here"
GROQ_API_KEY = "your-api-key-here"
GROQ_MODEL = "llama-3.1-8b-instant"
WHISPER_MODEL = "base"
DEVICE = "cpu"

WAKE_WORD = "jarvis"

TTS_VOICE = "en-GB-RyanNeural"
TTS_RATE = "+5%"
MUSIC_FILE = "cornfieldchase.mp3"

# VAD Configuration
VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512
SILENCE_DURATION = 0.5
MIN_SPEECH_DURATION = 0.5
MAX_RECORDING_DURATION = 30
# =======================================================


class TarsVoiceAssistant:
    def __init__(self):
        print("Initializing JARVIS with Conversation Mode...")
        
        # Initialize Conversation State
        self.conversation = ConversationState()
        
        # Initialize System Controller
        print("Loading System Controller...")
        self.system_controller = SystemController()
        
        # Initialize Silero VAD
        print("Loading Silero VAD model...")
        self.vad_model = load_silero_vad()
        self.vad_model.eval()
        
        # Initialize Porcupine
        print(f"Loading Porcupine wake word engine (keyword: '{WAKE_WORD}')...")
        try:
            self.porcupine = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keywords=[WAKE_WORD]
            )
            self.porcupine_sample_rate = self.porcupine.sample_rate
            self.porcupine_frame_length = self.porcupine.frame_length
            print(f"✓ Porcupine initialized (sample rate: {self.porcupine_sample_rate}Hz)")
        except Exception as e:
            print(f"ERROR: Failed to initialize Porcupine: {e}")
            sys.exit(1)
        
        # Speech-to-Text
        print("Loading Whisper model...")
        self.whisper_model = WhisperModel(WHISPER_MODEL, device=DEVICE)
        self.whisper_sample_rate = VAD_SAMPLE_RATE
        
        # Audio queues
        self.wake_word_queue = queue.Queue()
        self.command_queue = queue.Queue()
        self.is_running = False
        self.is_listening_for_command = False
        
        # AI Chat
        print("Connecting to GROQ AI...")
        self.groq_client = Groq(api_key=GROQ_API_KEY)
        self.conversation_history = []
        
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

        self.conversation_history.append({
            "role": "system",
            "content": jarvis_prompt
        })
        
        # TTS
        print("Initializing TTS...")
        self.tts_voice = TTS_VOICE
        self.tts_rate = TTS_RATE
        self.tts_temp_file = os.path.join(tempfile.gettempdir(), "jarvis_speech.mp3")
        pygame.mixer.init()
        
        # Music
        self.music_file = MUSIC_FILE
        self.music_playing = False
        
        if os.path.exists(self.music_file):
            print(f"✓ Music file found: {self.music_file}")
        else:
            print(f"⚠️  Warning: Music file not found: {self.music_file}")
        
        print("✓ JARVIS fully initialized with Conversation Mode!")
        print(f"✓ Wake word: '{WAKE_WORD.upper()}'")
        print(f"✓ Voice: {TTS_VOICE}")
        print(f"✓ AI Model: {GROQ_MODEL}")
    
    def wake_word_callback(self, indata, frames, time, status):
        """Callback for wake word detection"""
        if status:
            print(status, file=sys.stderr)
        self.wake_word_queue.put(indata.copy())
    
    def command_callback(self, indata, frames, time, status):
        """Callback for command audio stream"""
        if status:
            print(status, file=sys.stderr)
        self.command_queue.put(indata.copy())
    
    def is_speech(self, audio_chunk):
        """Use Silero VAD to detect speech"""
        audio_tensor = torch.from_numpy(audio_chunk).float()
        with torch.no_grad():
            speech_prob = self.vad_model(audio_tensor, VAD_SAMPLE_RATE).item()
        return speech_prob
    
    def listen_for_command_vad(self):
        """Listen with real-time VAD"""
        print("🎤 Listening... (speak naturally, I'll detect when you're done)")
        self.is_listening_for_command = True
        
        audio_buffer = np.array([], dtype=np.float32)
        
        # Clear queue
        while not self.command_queue.empty():
            self.command_queue.get()
        
        start_time = time.time()
        last_speech_time = start_time
        speech_started = False
        consecutive_silence_chunks = 0
        silence_threshold_chunks = int((SILENCE_DURATION * VAD_SAMPLE_RATE) / VAD_CHUNK_SIZE)
        
        with sd.InputStream(
            samplerate=VAD_SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            callback=self.command_callback,
            blocksize=VAD_CHUNK_SIZE
        ):
            while True:
                current_time = time.time()
                
                if current_time - start_time > MAX_RECORDING_DURATION:
                    print("\n⏱️  Maximum duration reached")
                    break
                
                if not self.command_queue.empty():
                    chunk = self.command_queue.get()
                    chunk_flat = chunk.flatten()
                    audio_buffer = np.append(audio_buffer, chunk_flat)
                    
                    speech_prob = self.is_speech(chunk_flat)
                    
                    if speech_prob > 0.5:
                        consecutive_silence_chunks = 0
                        last_speech_time = current_time
                        
                        if not speech_started:
                            speech_started = True
                            print("🗣️  Speaking...", end="", flush=True)
                        else:
                            print("█", end="", flush=True)
                    else:
                        if speech_started:
                            consecutive_silence_chunks += 1
                            print("░", end="", flush=True)
                    
                    if speech_started and consecutive_silence_chunks >= silence_threshold_chunks:
                        print(f"\n✅ Finished speaking (detected {SILENCE_DURATION}s silence)")
                        break
                
                time.sleep(0.001)
        
        self.is_listening_for_command = False
        
        duration = len(audio_buffer) / VAD_SAMPLE_RATE
        
        if duration < MIN_SPEECH_DURATION:
            print(f"⚠️  Recording too short ({duration:.1f}s)")
            return None
        
        print(f"📊 Recorded {duration:.1f}s of audio, transcribing...")
        
        audio_int16 = (audio_buffer * 32767).astype(np.int16)
        return self.transcribe_audio(audio_int16, VAD_SAMPLE_RATE)
    
    def transcribe_audio(self, audio_data, sample_rate):
        """Transcribe audio to text"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_filename = tmp_file.name
            wavfile.write(tmp_filename, sample_rate, audio_data)
        
        try:
            segments, info = self.whisper_model.transcribe(
                tmp_filename,
                beam_size=5,
                language="en",
                vad_filter=True
            )
            
            text = " ".join([segment.text.strip() for segment in segments])
            return text
        finally:
            os.unlink(tmp_filename)
    
    def check_music_command(self, text):
        """Check if user wants to control music"""
        text_lower = text.lower()
        
        if any(phrase in text_lower for phrase in ["play music", "play the music", "start music"]):
            return "play"
        
        if any(phrase in text_lower for phrase in ["stop music", "stop the music", "pause music"]):
            return "stop"
        
        return None
    
    def play_music(self):
        """Play music"""
        if not os.path.exists(self.music_file):
            return False
        
        try:
            pygame.mixer.music.load(self.music_file)
            pygame.mixer.music.play(-1)
            self.music_playing = True
            return True
        except Exception as e:
            print(f"Error playing music: {e}")
            return False
    
    def stop_music(self):
        """Stop music"""
        try:
            pygame.mixer.music.stop()
            self.music_playing = False
            return True
        except Exception as e:
            print(f"Error stopping music: {e}")
            return False
    
    def get_ai_response(self, user_message):
        """Get AI response"""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=self.conversation_history,
                model=GROQ_MODEL,
                temperature=0.7,
                max_tokens=200,
            )
            
            assistant_message = chat_completion.choices[0].message.content
            
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except Exception as e:
            return f"Error communicating with AI: {e}"
    
    async def speak_async(self, text):
        """Generate and play speech"""
        try:
            music_was_playing = self.music_playing
            if music_was_playing:
                pygame.mixer.music.pause()
            
            await asyncio.sleep(0.1)
            
            communicate = edge_tts.Communicate(text, self.tts_voice, rate=self.tts_rate)
            await communicate.save(self.tts_temp_file)
            
            sound = pygame.mixer.Sound(self.tts_temp_file)
            channel = sound.play()
            
            while channel.get_busy():
                await asyncio.sleep(0.1)
            
            if music_was_playing:
                pygame.mixer.music.unpause()
                
        except Exception as e:
            print(f"TTS Error: {e}")
            if music_was_playing:
                pygame.mixer.music.unpause()
    
    def speak(self, text):
        """Speak text"""
        asyncio.run(self.speak_async(text))
    
    def process_conversation_response(self, response):
        """Handle response when in conversation mode"""
        print(f"💬 Conversation response: {response}")
        
        # Add the response to conversation state
        self.conversation.add_response(response)
        
        # Check if conversation is complete
        if self.conversation.is_complete():
            # We have all the data, execute the action
            print("✅ Got all information, processing...")
            
            if self.conversation.context_type == 'add_assignment':
                data = self.conversation.get_data()
                success, message = self.system_controller.add_assignment_interactive(
                    data['course'],
                    data['description'],
                    data['due_date']
                )
                
                if success:
                    print(f"✅ {message}")
                    self.speak(message)
                else:
                    print(f"❌ {message}")
                    self.speak(f"Sorry, {message}")
            
            elif self.conversation.context_type == 'create_study_plan':
                data = self.conversation.get_data()
                
                # Parse hours
                hours_text = data['hours_per_day'].lower()
                try:
                    # Extract number from text like "2 hours", "3", "two"
                    import re
                    numbers = re.findall(r'\d+\.?\d*', hours_text)
                    if numbers:
                        hours = float(numbers[0])
                    else:
                        hours = 2.0  # Default
                except:
                    hours = 2.0
                
                success, message, plan = self.system_controller.create_study_plan_interactive(
                    data['subject'],
                    data['exam_date'],
                    hours
                )
                
                if success and plan:
                    display = self.system_controller.education.format_study_plan_display(plan)
                    print(display)
                    self.speak(message)
                else:
                    print(f"❌ {message}")
                    self.speak(f"Sorry, {message}")
            
            # Reset conversation
            self.conversation.reset()
            print(f"💤 Ready for next '{WAKE_WORD.upper()}'...")
            
        else:
            # Ask next question
            next_question = self.conversation.get_question()
            print(f"❓ JARVIS asks: {next_question}")
            self.speak(next_question)
            print(f"💤 Say '{WAKE_WORD.upper()}' then answer...")
    
    def process_command(self):
        """Process voice command"""
        # Check if we're in conversation mode
        if self.conversation.is_waiting_for_response():
            print("📝 Continuing conversation...")
            # Listen immediately (already past wake word)
            response = self.listen_for_command_vad()
            
            if not response or len(response.strip()) < 1:
                print("⚠️  Didn't catch that")
                # Ask the question again
                question = self.conversation.get_question()
                self.speak("Sorry, I didn't catch that. " + question)
                print(f"💤 Say '{WAKE_WORD.upper()}' then answer...")
                return
            
            # Process the response
            self.process_conversation_response(response)
            return
        
        # Normal command processing
        command = self.listen_for_command_vad()
        
        if not command or len(command.strip()) < 3:
            print("⚠️  No clear command detected")
            self.speak("I didn't catch that, sir.")
            print(f"💤 Ready for next '{WAKE_WORD.upper()}'...")
            return
        
        print(f"📝 You: {command}")
        
        # Check for system/education commands
        cmd_type, details = self.system_controller.check_command(command)
        
        if cmd_type:
            print(f"🖥️  Command detected: {cmd_type}")
            
            # Check if this command needs conversation
            if cmd_type == "add_assignment_prompt":
                # Start conversation
                self.conversation.start_conversation('add_assignment')
                question = self.conversation.get_question()
                self.speak("I'll help you add that assignment. " + question)
                print(f"💤 Say '{WAKE_WORD.upper()}' then answer...")
                return
            
            elif cmd_type == "create_study_plan_prompt":
                # Start conversation
                self.conversation.start_conversation('create_study_plan')
                question = self.conversation.get_question()
                self.speak("I'll create a study plan for you. " + question)
                print(f"💤 Say '{WAKE_WORD.upper()}' then answer...")
                return
            
            # Execute other commands normally
            result = self.system_controller.execute_command(cmd_type, details)
            
            if len(result) == 3:
                success, message, extra_data = result
            else:
                success, message = result
                extra_data = None
            
            if success:
                print(f"✅ {message}")
                
                if extra_data and 'display' in extra_data:
                    print(extra_data['display'])
                
                self.speak(message)
            else:
                print(f"❌ {message}")
                self.speak(f"Sorry, {message}")
            
            print(f"💤 Ready for next '{WAKE_WORD.upper()}'...")
            return
        
        # Check music commands
        music_cmd = self.check_music_command(command)
        
        if music_cmd == "play":
            print("🎵 Playing music...")
            if self.play_music():
                self.speak("Playing music now.")
            else:
                self.speak("Sorry, couldn't find the music file.")
        elif music_cmd == "stop":
            print("⏹️  Stopping music...")
            self.stop_music()
            self.speak("Music stopped.")
        else:
            # Regular AI response
            print("🤔 JARVIS thinking...")
            response = self.get_ai_response(command)
            print(f"🤖 JARVIS: {response}\n")
            self.speak(response)
        
        print(f"💤 Ready for next '{WAKE_WORD.upper()}'...")
    
    def start(self):
        """Start JARVIS"""
        print(f"\n{'='*60}")
        print("🤖 JARVIS VOICE ASSISTANT ONLINE (Conversation Mode)")
        print(f"{'='*60}")
        print(f"💤 Say '{WAKE_WORD.upper()}' to wake JARVIS")
        print("   For multi-turn conversations:")
        print("   - JARVIS asks a question")
        print(f"   - Say '{WAKE_WORD.upper()}' again")
        print("   - Answer the question")
        print("\nPress Ctrl+C to stop\n")
        
        self.speak("JARVIS online with conversation mode, sir.")
        
        self.is_running = True
        audio_buffer = np.array([], dtype=np.int16)
        
        try:
            with sd.InputStream(
                samplerate=self.porcupine_sample_rate,
                channels=1,
                dtype='int16',
                callback=self.wake_word_callback,
                blocksize=self.porcupine_frame_length
            ):
                print(f"🎧 Listening for '{WAKE_WORD.upper()}'...\n")
                
                while self.is_running:
                    # Collect audio
                    while not self.wake_word_queue.empty():
                        chunk = self.wake_word_queue.get()
                        audio_buffer = np.append(audio_buffer, chunk.flatten())
                    
                    # Process frames
                    while len(audio_buffer) >= self.porcupine_frame_length:
                        frame = audio_buffer[:self.porcupine_frame_length]
                        audio_buffer = audio_buffer[self.porcupine_frame_length:]
                        
                        keyword_index = self.porcupine.process(frame)
                        
                        if keyword_index >= 0:
                            print(f"\n🎯 '{WAKE_WORD.upper()}' detected!")
                            
                            # Process command (handles both normal and conversation mode)
                            self.process_command()
                            
                            # Clear buffer
                            audio_buffer = np.array([], dtype=np.int16)
                    
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down JARVIS...")
            self.stop_music()
            self.speak("JARVIS shutting down. Goodbye, sir.")
            self.is_running = False
        finally:
            self.porcupine.delete()
            self.stop_music()
            pygame.mixer.quit()
            if os.path.exists(self.tts_temp_file):
                try:
                    os.remove(self.tts_temp_file)
                except:
                    pass


if __name__ == "__main__":
    if not GROQ_API_KEY or GROQ_API_KEY == "your-api-key-here":
        print("ERROR: Please set your GROQ API key!")
        sys.exit(1)
    
    if not PICOVOICE_ACCESS_KEY or PICOVOICE_ACCESS_KEY == "your-picovoice-access-key-here":
        print("ERROR: Please set your Picovoice access key!")
        sys.exit(1)
    
    jarvis = TarsVoiceAssistant()
    jarvis.start()