import { useState, useRef, useEffect } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState('')
  const [isPlayingAudio, setIsPlayingAudio] = useState(false)
  const messagesEndRef = useRef(null)
  const recognition = useRef(null)
  const audioPlayer = useRef(new Audio())

  // Initialize speech recognition
  useEffect(() => {
    if ('webkitSpeechRecognition' in window) {
      recognition.current = new webkitSpeechRecognition()
      recognition.current.continuous = false
      recognition.current.interimResults = false
      recognition.current.lang = 'en-US'

      recognition.current.onresult = async (event) => {
        const text = event.results[0][0].transcript
        setMessages(prev => [...prev, { type: 'user', text }])
        
        try {
          const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: text,
              audio_data: text // Send recognized text for pronunciation analysis
            })
          })

          if (!response.ok) throw new Error('Server error')
          
          const data = await response.json()
          const newMessage = {
            type: 'bot',
            text: data.text,
            pronunciation: data.pronunciation_feedback
          }
          
          setMessages(prev => [...prev, newMessage])
          
          // Get audio from ElevenLabs
          const audioResponse = await fetch('http://localhost:8000/text-to-speech', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: data.text })
          })

          if (!audioResponse.ok) throw new Error('TTS error')

          const audioBlob = await audioResponse.blob()
          const audioUrl = URL.createObjectURL(audioBlob)
          
          if (audioPlayer.current.src) {
            URL.revokeObjectURL(audioPlayer.current.src)
          }
          
          // Play the audio
          audioPlayer.current.src = audioUrl
          audioPlayer.current.play()
          setIsPlayingAudio(true)

        } catch (error) {
          console.error('Error:', error)
          setError(error.message)
        }
      }

      recognition.current.onerror = (event) => {
        console.error('Recognition error:', event.error)
        setError(`Speech recognition error: ${event.error}`)
        setIsRecording(false)
      }

      recognition.current.onend = () => setIsRecording(false)

      // Set up audio player event handlers
      audioPlayer.current.onended = () => setIsPlayingAudio(false)
      audioPlayer.current.onerror = () => {
        setError('Error playing audio response')
        setIsPlayingAudio(false)
      }
    } else {
      setError('Speech recognition is not supported in this browser')
    }

    return () => {
      if (recognition.current) {
        recognition.current.abort()
      }
      if (audioPlayer.current) {
        audioPlayer.current.pause()
        audioPlayer.current.src = ''
      }
    }
  }, [])

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Toggle recording
  const toggleRecording = async () => {
    if (isRecording) {
      recognition.current.stop()
      setIsRecording(false)
    } else {
      try {
        recognition.current.start()
        setIsRecording(true)
        setError('')
      } catch (error) {
        console.error('Error starting recording:', error)
        setError('Error starting recording')
      }
    }
  }

  // Practice a specific word
  const practiceWord = (word) => {
    // Get audio from ElevenLabs for the practice word
    fetch('http://localhost:8000/text-to-speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: word })
    })
      .then(response => {
        if (!response.ok) throw new Error('TTS error')
        return response.blob()
      })
      .then(audioBlob => {
        if (audioPlayer.current.src) {
          URL.revokeObjectURL(audioPlayer.current.src)
        }
        const audioUrl = URL.createObjectURL(audioBlob)
        audioPlayer.current.src = audioUrl
        audioPlayer.current.play()
        setIsPlayingAudio(true)
        
        // Start recording after the word is played
        audioPlayer.current.onended = () => {
          setIsPlayingAudio(false)
          setTimeout(toggleRecording, 500)
        }
      })
      .catch(error => {
        console.error('Error getting TTS:', error)
        setError('Error playing practice word')
      })
  }

  // Render pronunciation feedback
  const renderPronunciationFeedback = (pronunciation) => {
    if (!pronunciation) return null

    return (
      <div className="pronunciation-feedback">
        <h4>Pronunciation Analysis</h4>
        <div className="score">Score: {pronunciation.score.toFixed(1)}/100</div>
        {pronunciation.phoneme_errors.length > 0 && (
          <div className="errors">
            <h5>Pronunciation Challenges:</h5>
            {pronunciation.phoneme_errors.map((error, index) => (
              <div key={index} className="phoneme-error">
                <div className="error-details">
                  <strong>Phoneme '{error.phoneme}' in '{error.word}'</strong>
                  <p>{error.description}</p>
                  <div className="metrics">
                    <span>Confidence: {(error.confidence * 100).toFixed(1)}%</span>
                  </div>
                </div>
                <div className="practice-section">
                  <h6>Practice with these words:</h6>
                  <div className="practice-words">
                    {error.practice_words.map((word, wordIndex) => (
                      <button
                        key={wordIndex}
                        className="practice-word"
                        onClick={() => practiceWord(word)}
                        disabled={isPlayingAudio || isRecording}
                      >
                        {word}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {pronunciation.suggestions.length > 0 && (
          <div className="suggestions">
            <h5>Tips to Improve:</h5>
            <ul>
              {pronunciation.suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="app">
      <div className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome-message">
              Click the microphone and start speaking
            </div>
          )}
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.type}`}>
              <div className="text">{msg.text}</div>
              {msg.pronunciation && renderPronunciationFeedback(msg.pronunciation)}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div className="controls">
          <button
            className={`record-button ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording}
            disabled={isPlayingAudio}
          >
            {isRecording ? 'Stop' : 'Start'} Recording
          </button>
          {error && <div className="error">{error}</div>}
        </div>
      </div>
    </div>
  )
}

export default App
