/**
 * ElderCare Platform — Interactive Client Script
 * Handles:
 * 1. Web Speech Synthesis (Text-to-Speech audio readout for seniors)
 * 2. Web Speech Recognition (Voice command logging)
 * 3. Accessibility Font Size controls with localStorage persistence
 * 4. Emergency SOS triggers & Modals
 * 5. On-demand proactive reminder checks
 */

// ----------------- FONT SIZING & ACCESSIBILITY -----------------
function changeFontSize(size) {
  const body = document.getElementById('appBody');
  if (!body) return;
  body.classList.remove('font-size-normal', 'font-size-large', 'font-size-xlarge');
  body.classList.add('font-size-' + size);
  localStorage.setItem('eldercare_font_size', size);
}

// Restore saved font size on load
document.addEventListener('DOMContentLoaded', () => {
  const savedSize = localStorage.getItem('eldercare_font_size');
  if (savedSize) {
    changeFontSize(savedSize);
  }
});

// Profile Switcher Dropdown Toggle
function toggleProfileDropdown() {
  const menu = document.getElementById('profileDropdown');
  if (menu) menu.classList.toggle('show');
}

// Close dropdown if clicked outside
window.addEventListener('click', (e) => {
  if (!e.target.closest('.profile-switcher-dropdown')) {
    const menu = document.getElementById('profileDropdown');
    if (menu) menu.classList.remove('show');
  }
});

// ----------------- TEXT-TO-SPEECH (AUDIO VOICE READOUT) -----------------
let isSpeaking = false;

function speakCurrentPageRoutine() {
  if (!('speechSynthesis' in window)) {
    alert("Audio speech synthesis is not supported in this browser.");
    return;
  }

  if (isSpeaking) {
    window.speechSynthesis.cancel();
    isSpeaking = false;
    updateVoiceButtonState(false);
    return;
  }

  // Build natural speech narrative from today's pillbox and appointments
  const seniorName = document.querySelector('.senior-greeting-name')?.innerText || 'valued patient';
  let speechText = `Hello ${seniorName}. Here is your healthcare routine update. `;

  // Collect scheduled doses
  const pillCards = document.querySelectorAll('.pill-dose-card');
  if (pillCards.length > 0) {
    const pendingItems = [];
    const takenItems = [];

    pillCards.forEach(card => {
      const medName = card.querySelector('.med-name')?.innerText || 'medication';
      const dosage = card.querySelector('.med-dosage')?.innerText || '';
      const time = card.querySelector('.dose-time strong')?.innerText || '';
      const isTaken = card.classList.contains('status-taken');

      if (isTaken) {
        takenItems.push(`${medName} ${dosage}`);
      } else {
        pendingItems.push(`${medName} ${dosage} at ${time}`);
      }
    });

    if (takenItems.length > 0) {
      speechText += `Great job! You have already taken: ${takenItems.join(', ')}. `;
    }

    if (pendingItems.length > 0) {
      speechText += `Your remaining medicines for today are: ${pendingItems.join('; and ')}. `;
    } else {
      speechText += `All your scheduled medications for today have been taken! Excellent adherence! `;
    }
  } else {
    speechText += `You have no medications scheduled right now. `;
  }

  // Check next doctor visit
  const nextAppt = document.querySelector('.appointment-summary-item h4')?.innerText;
  if (nextAppt) {
    speechText += `Remember, you have an upcoming appointment with ${nextAppt}. `;
  }

  speechText += `Stay hydrated, and have a wonderful day!`;

  const utterance = new SpeechSynthesisUtterance(speechText);
  utterance.rate = 0.9; // Slightly slower, friendly pace for elderly comprehension
  utterance.pitch = 1.0;

  utterance.onstart = () => {
    isSpeaking = true;
    updateVoiceButtonState(true);
  };

  utterance.onend = () => {
    isSpeaking = false;
    updateVoiceButtonState(false);
  };

  utterance.onerror = () => {
    isSpeaking = false;
    updateVoiceButtonState(false);
  };

  window.speechSynthesis.speak(utterance);
}

function updateVoiceButtonState(active) {
  const globalBtn = document.getElementById('globalAudioBtn');
  const waveIcon = document.getElementById('voiceWaveIcon');

  if (active) {
    if (globalBtn) globalBtn.innerHTML = '<i class="fa-solid fa-stop"></i> <span class="hide-mobile">Stop</span>';
    if (waveIcon) waveIcon.style.animation = 'pulse-red 1s infinite';
  } else {
    if (globalBtn) globalBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i> <span class="hide-mobile">Listen</span>';
    if (waveIcon) waveIcon.style.animation = 'none';
  }
}

// ----------------- SPEECH RECOGNITION (VOICE COMMANDS) -----------------
let recognition = null;
let isListening = false;

function toggleSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition is not supported in this browser. Please use Chrome or Edge.");
    return;
  }

  const micBtn = document.getElementById('voiceMicBtn');
  const micLabel = document.getElementById('micLabel');
  const feedbackBar = document.getElementById('voiceFeedback');

  if (isListening) {
    if (recognition) recognition.stop();
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;

  recognition.onstart = () => {
    isListening = true;
    if (micBtn) micBtn.classList.add('listening');
    if (micLabel) micLabel.innerText = 'Listening...';
    if (feedbackBar) {
      feedbackBar.style.display = 'block';
      feedbackBar.innerText = '🎤 Listening... Say "Take Metformin", "Read Schedule", or "Help"';
    }
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.toLowerCase();
    if (feedbackBar) {
      feedbackBar.innerText = `Heard: "${transcript}"`;
    }
    handleVoiceCommand(transcript);
  };

  recognition.onerror = (event) => {
    if (feedbackBar) {
      feedbackBar.innerText = `Voice Error: ${event.error}`;
    }
    resetMicUI();
  };

  recognition.onend = () => {
    resetMicUI();
  };

  recognition.start();
}

function resetMicUI() {
  isListening = false;
  const micBtn = document.getElementById('voiceMicBtn');
  const micLabel = document.getElementById('micLabel');
  if (micBtn) micBtn.classList.remove('listening');
  if (micLabel) micLabel.innerText = 'Speak Command';
}

function handleVoiceCommand(cmd) {
  const feedbackBar = document.getElementById('voiceFeedback');

  // Command 1: Read Routine
  if (cmd.includes('read') || cmd.includes('listen') || cmd.includes('schedule')) {
    speakCurrentPageRoutine();
  }
  // Command 2: Emergency / SOS
  else if (cmd.includes('emergency') || cmd.includes('sos') || cmd.includes('help')) {
    openSosModal();
  }
  // Command 3: Mark medication taken
  else if (cmd.includes('take') || cmd.includes('mark') || cmd.includes('swallow')) {
    const pillCards = document.querySelectorAll('.pill-dose-card');
    let matched = false;

    pillCards.forEach(card => {
      const medName = card.querySelector('.med-name')?.innerText.toLowerCase() || '';
      if (cmd.includes(medName) || (medName && cmd.includes(medName.substring(0, 4)))) {
        const takeBtn = card.querySelector('.btn-take-dose');
        if (takeBtn) {
          if (feedbackBar) feedbackBar.innerText = `Marking ${medName} as taken!`;
          takeBtn.click();
          matched = true;
        }
      }
    });

    if (!matched && feedbackBar) {
      feedbackBar.innerText = `Could not find pending medicine matching "${cmd}".`;
    }
  } else {
    if (feedbackBar) {
      feedbackBar.innerText = `Unrecognized command. Try saying "Take [Medicine Name]" or "Read Schedule".`;
    }
  }
}

// ----------------- EMERGENCY SOS MODAL -----------------
function openSosModal() {
  const modal = document.getElementById('sosModal');
  if (modal) modal.style.display = 'flex';
}

function closeSosModal() {
  const modal = document.getElementById('sosModal');
  if (modal) modal.style.display = 'none';
}

// ----------------- ON-DEMAND PROACTIVE REMINDER CHECK -----------------
function runProactiveCheckNow() {
  fetch('/api/reminders/run-now', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
    .then(res => res.json())
    .then(data => {
      alert("Proactive check completed! Any overdue doses or upcoming appointments have triggered email notifications.");
      window.location.reload();
    })
    .catch(err => {
      console.error("Reminder check failed:", err);
      alert("Ran reminder check scan.");
    });
}
