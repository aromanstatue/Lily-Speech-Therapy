# Lily Speech Therapy

A real-time pronunciation assistant that helps users improve their English pronunciation through speech recognition, analysis, and feedback.

## Core Features

- Real-time speech recognition using Web Speech API
- Pronunciation analysis with detailed phoneme-level feedback
- High-quality text-to-speech responses using ElevenLabs
- Interactive practice words for improving specific sounds

## Setup

### Backend Setup

1. Create a `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_key_here
   ELEVENLABS_API_KEY=your_elevenlabs_key_here
   ```

2. Install dependencies and run:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

### Frontend Setup

1. Install and run:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Environment Variables

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key
