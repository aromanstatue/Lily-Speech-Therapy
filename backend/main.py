from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import openai
from pydantic import BaseModel
from typing import Optional, List
import base64
import tempfile
import json
from pathlib import Path
import io
from elevenlabs import generate, set_api_key, Voice, VoiceSettings
from fastapi.responses import StreamingResponse

# Load environment variables
load_dotenv()

# Get API keys
openai_key = os.getenv("OPENAI_API_KEY")
elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")

if not openai_key:
    raise ValueError("No OpenAI API key found. Please set OPENAI_API_KEY in .env file")
if not elevenlabs_key:
    raise ValueError("No ElevenLabs API key found. Please set ELEVENLABS_API_KEY in .env file")

openai.api_key = openai_key
set_api_key(elevenlabs_key)

# Configure Scribe voice settings
scribe_voice = Voice(
    voice_id="pNInz6obpgDQGcFmaJgB",  # Scribe voice ID
    settings=VoiceSettings(
        stability=0.71,
        similarity_boost=0.5,
        style=0.0,
        use_speaker_boost=True
    )
)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    audio_data: Optional[str] = None  # Recognized text from Web Speech API

class TTSRequest(BaseModel):
    text: str

class PhonemeError(BaseModel):
    phoneme: str
    word: str
    confidence: float
    description: str
    practice_words: List[str]

class PronunciationFeedback(BaseModel):
    score: float
    phoneme_errors: List[PhonemeError]
    suggestions: List[str]

class ChatResponse(BaseModel):
    text: str
    pronunciation_feedback: Optional[PronunciationFeedback] = None

async def analyze_pronunciation(text: str, recognized_text: str) -> PronunciationFeedback:
    """Analyze pronunciation using OpenAI"""
    try:
        # Compare expected text with recognized text
        expected_words = text.lower().split()
        recognized_words = recognized_text.lower().split()
        
        # Initialize variables
        phoneme_errors = []
        overall_score = 0.0
        word_scores = []
        
        # Compare words and identify potential pronunciation issues
        for expected_word, recognized_word in zip(expected_words, recognized_words):
            # Calculate word similarity score
            confidence = 1.0 if expected_word == recognized_word else 0.5
            word_scores.append(confidence)
            
            if confidence < 0.8:  # If word was not pronounced correctly
                # Get phoneme analysis from OpenAI
                phoneme_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a pronunciation expert. Analyze the word and identify which phoneme might be challenging. Return response in format: phoneme|description"
                        },
                        {
                            "role": "user",
                            "content": f"Analyze this mispronounced word: {expected_word} (pronounced as: {recognized_word})"
                        }
                    ],
                    max_tokens=50,
                    temperature=0.7
                )
                
                phoneme_analysis = phoneme_response.choices[0].message.content.split("|")
                phoneme = phoneme_analysis[0].strip()
                description = phoneme_analysis[1].strip()
                
                # Get practice words from OpenAI
                practice_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a pronunciation expert. Provide 3 simple words that contain the given phoneme and are easier to pronounce."
                        },
                        {
                            "role": "user",
                            "content": f"Give me 3 simple words containing the phoneme '{phoneme}'. Respond with just the words separated by commas."
                        }
                    ],
                    max_tokens=50,
                    temperature=0.7
                )
                practice_words = [w.strip() for w in practice_response.choices[0].message.content.split(",")]
                
                phoneme_errors.append(PhonemeError(
                    phoneme=phoneme,
                    word=expected_word,
                    confidence=confidence,
                    description=description,
                    practice_words=practice_words
                ))
        
        # Calculate overall score
        overall_score = (sum(word_scores) / len(word_scores)) * 100 if word_scores else 100
        
        # Get suggestions from OpenAI if there are errors
        if phoneme_errors:
            suggestions_response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a pronunciation expert. Provide helpful tips for improving pronunciation."
                    },
                    {
                        "role": "user",
                        "content": f"Give me 3 specific tips for improving the pronunciation of these phonemes: {', '.join(error.phoneme for error in phoneme_errors)}"
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )
            suggestions = [s.strip() for s in suggestions_response.choices[0].message.content.split("\n") if s.strip()]
        else:
            suggestions = ["Great pronunciation! Keep practicing to maintain your skills."]
        
        return PronunciationFeedback(
            score=overall_score,
            phoneme_errors=phoneme_errors,
            suggestions=suggestions
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pronunciation analysis error: {str(e)}")

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        # First analyze pronunciation if audio was provided
        pronunciation_feedback = None
        if request.audio_data:
            # Since we're using Web Speech API, audio_data will now be the recognized text
            pronunciation_feedback = await analyze_pronunciation(request.message, request.audio_data)
            
        # Prepare the chat message
        messages = [
            {
                "role": "system",
                "content": "You are a helpful pronunciation tutor. When responding, focus on helping the user improve their pronunciation if errors were detected."
            },
            {
                "role": "user",
                "content": request.message
            }
        ]
        
        # Add pronunciation feedback to the chat context
        if pronunciation_feedback and pronunciation_feedback.phoneme_errors:
            error_context = "\n\nI noticed some pronunciation challenges:\n"
            for error in pronunciation_feedback.phoneme_errors:
                error_context += f"- The phoneme '{error.phoneme}' in '{error.word}': {error.description}\n"
            messages[1]["content"] += error_context
        
        # Get response from OpenAI
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        # Extract the response text
        response_text = response.choices[0].message.content
        
        return ChatResponse(
            text=response_text,
            pronunciation_feedback=pronunciation_feedback
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/text-to-speech")
async def text_to_speech(request: TTSRequest):
    try:
        # Generate audio using ElevenLabs
        audio = generate(
            text=request.text,
            voice=scribe_voice,
            model="eleven_monolingual_v1"
        )
        
        # Return audio as a streaming response
        return StreamingResponse(
            io.BytesIO(audio),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": "attachment; filename=speech.mp3"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text-to-speech error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
