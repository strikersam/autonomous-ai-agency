/**
 * SAM tap-to-speak on iOS: audio must not be touched on the start tap (it
 * breaks iOS speech recognition), must be unlocked on the stop tap, and each
 * recording's AudioContext must be closed (iOS caps open contexts).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import SamVoiceScreen from '../v5/screens/SamVoiceScreen';

jest.mock('../api', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
  fmtErr: (e) => String(e),
}));

const API = require('../api').default;

let ctxClose;
let audioPlay;
let recognition;

function installBrowserMocks() {
  HTMLCanvasElement.prototype.getContext = () => ({
    clearRect: () => {}, fillRect: () => {}, beginPath: () => {}, fill: () => {},
    roundRect: () => {}, createLinearGradient: () => ({ addColorStop: () => {} }),
  });
  window.requestAnimationFrame = () => 0;
  window.cancelAnimationFrame = () => {};
  ctxClose = jest.fn(() => Promise.resolve());
  window.AudioContext = jest.fn(() => ({
    state: 'running',
    close: ctxClose,
    createMediaStreamSource: () => ({ connect: () => {} }),
    createAnalyser: () => ({ fftSize: 0, frequencyBinCount: 0, getByteFrequencyData: () => {} }),
  }));

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: jest.fn(() => Promise.resolve({ getTracks: () => [{ stop: () => {} }] })) },
  });

  class FakeRecorder {
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/mp4'; }
    static isTypeSupported(t) { return t === 'audio/mp4'; }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      this.ondataavailable({ data: new Blob([new Uint8Array(500)]) });
      this.onstop();
    }
  }
  window.MediaRecorder = FakeRecorder;

  audioPlay = jest.fn(() => Promise.resolve());
  window.Audio = jest.fn(() => ({ play: audioPlay }));
  window.speechSynthesis = { speak: jest.fn(), cancel: jest.fn() };
  window.SpeechSynthesisUtterance = jest.fn();

  window.webkitSpeechRecognition = jest.fn(() => {
    recognition = {
      start: jest.fn(),
      stop: jest.fn(() => {
        recognition.onresult({ resultIndex: 0, results: [
          Object.assign([{ transcript: 'fix the alerts' }], { isFinal: true }),
          Object.assign([{ transcript: 'fix the alerts' }], { isFinal: true }), // iOS repeat
        ] });
        recognition.onend();
      }),
    };
    return recognition;
  });
}

beforeEach(() => {
  installBrowserMocks();
  API.get.mockResolvedValue({ data: {} });
  API.post.mockImplementation((url) => Promise.resolve({
    data: url === '/agent/sam/chat' ? { text: 'Queued 2 fix tasks.' } : { audio_b64: 'AAAA', format: 'mp3' },
  }));
});

test('start tap leaves audio alone; stop tap unlocks it and sends one clean transcript', async () => {
  render(<SamVoiceScreen />);

  await act(async () => { fireEvent.click(screen.getByLabelText('Speak to SAM')); });
  await screen.findByLabelText('Stop and send to SAM');

  expect(window.Audio).not.toHaveBeenCalled();
  expect(window.speechSynthesis.speak).not.toHaveBeenCalled();
  expect(recognition.start).toHaveBeenCalled();

  await act(async () => { fireEvent.click(screen.getByLabelText('Stop and send to SAM')); });

  await waitFor(() => expect(API.post).toHaveBeenCalledWith(
    '/agent/sam/chat', expect.objectContaining({ text: 'fix the alerts' }), expect.anything(),
  ));
  expect(recognition.stop).toHaveBeenCalled();
  expect(ctxClose).toHaveBeenCalled();
  await waitFor(() => expect(audioPlay).toHaveBeenCalledTimes(2)); // unlock + reply
});

test('an empty transcript tells the user instead of going silently idle', async () => {
  window.webkitSpeechRecognition = jest.fn(() => {
    recognition = { start: jest.fn(), stop: jest.fn(() => recognition.onend()) };
    return recognition;
  });
  API.post.mockImplementation((url) => Promise.resolve({ data: url === '/agent/voice/transcribe' ? { text: '' } : {} }));
  render(<SamVoiceScreen />);

  await act(async () => { fireEvent.click(screen.getByLabelText('Speak to SAM')); });
  await screen.findByLabelText('Stop and send to SAM');
  await act(async () => { fireEvent.click(screen.getByLabelText('Stop and send to SAM')); });

  expect(await screen.findByText(/Didn't catch that/)).toBeTruthy();
  expect(API.post).not.toHaveBeenCalledWith('/agent/sam/chat', expect.anything(), expect.anything());
});
