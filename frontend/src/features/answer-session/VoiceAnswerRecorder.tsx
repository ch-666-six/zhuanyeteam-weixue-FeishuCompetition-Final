import { useEffect, useRef, useState } from 'react'
import { Mic, RotateCcw, Square } from 'lucide-react'
import { Button } from '../../shared/ui/Button'
import { transcribeAnswer } from './api'

interface Props { token: string; sessionId: string; stage: 'initial' | 'final'; value: string; onTranscription: (text: string) => void; disabled?: boolean }
const MAX_SECONDS = 60

function downsample(samples: Float32Array, sourceRate: number): Float32Array {
  if (sourceRate === 16000) return samples
  const ratio = sourceRate / 16000
  const output = new Float32Array(Math.floor(samples.length / ratio))
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio), end = Math.min(Math.floor((index + 1) * ratio), samples.length)
    let sum = 0
    for (let source = start; source < end; source += 1) sum += samples[source]
    output[index] = sum / Math.max(1, end - start)
  }
  return output
}

function wavBlob(chunks: Float32Array[], sourceRate: number): Blob {
  const joined = new Float32Array(chunks.reduce((total, chunk) => total + chunk.length, 0))
  let offset = 0
  for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length }
  const pcm = downsample(joined, sourceRate)
  const buffer = new ArrayBuffer(44 + pcm.length * 2), view = new DataView(buffer)
  const text = (position: number, value: string) => [...value].forEach((char, index) => view.setUint8(position + index, char.charCodeAt(0)))
  text(0, 'RIFF'); view.setUint32(4, 36 + pcm.length * 2, true); text(8, 'WAVE'); text(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  text(36, 'data'); view.setUint32(40, pcm.length * 2, true)
  pcm.forEach((sample, index) => view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767), true))
  return new Blob([buffer], { type: 'audio/wav' })
}

export function VoiceAnswerRecorder({ token, sessionId, stage, value, onTranscription, disabled }: Props) {
  const [state, setState] = useState<'idle' | 'recording' | 'transcribing'>('idle')
  const [seconds, setSeconds] = useState(0), [error, setError] = useState('')
  const audioRef = useRef<{ context: AudioContext; stream: MediaStream; processor: ScriptProcessorNode; chunks: Float32Array[] } | null>(null)
  const timerRef = useRef<number | null>(null)

  async function stopRecording() {
    const active = audioRef.current
    if (!active) return
    audioRef.current = null
    if (timerRef.current) window.clearInterval(timerRef.current)
    active.processor.disconnect(); active.stream.getTracks().forEach((track) => track.stop())
    const sourceRate = active.context.sampleRate
    await active.context.close(); setState('transcribing')
    try { onTranscription(await transcribeAnswer(token, sessionId, stage, wavBlob(active.chunks, sourceRate))); setState('idle') }
    catch (reason) { setError(reason instanceof Error ? reason.message : '语音转写失败，请重新录制。'); setState('idle') }
  }

  async function startRecording() {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      const context = new AudioContext(), source = context.createMediaStreamSource(stream), processor = context.createScriptProcessor(4096, 1, 1), muted = context.createGain()
      muted.gain.value = 0
      const chunks: Float32Array[] = []
      processor.onaudioprocess = (event) => chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
      source.connect(processor); processor.connect(muted); muted.connect(context.destination)
      audioRef.current = { context, stream, processor, chunks }; setSeconds(0); setState('recording')
      timerRef.current = window.setInterval(() => setSeconds((current) => { if (current + 1 >= MAX_SECONDS) void stopRecording(); return Math.min(MAX_SECONDS, current + 1) }), 1000)
    } catch { setError('无法使用麦克风，请在浏览器中允许麦克风权限。') }
  }

  useEffect(() => () => { if (timerRef.current) window.clearInterval(timerRef.current); audioRef.current?.stream.getTracks().forEach((track) => track.stop()); void audioRef.current?.context.close() }, [])

  return <div className="voice-recorder">
    <div className={`voice-recorder-control ${state === 'recording' ? 'is-recording' : ''}`}>
      <div className="voice-status"><span><Mic size={22} aria-hidden="true" /></span><div><strong>{state === 'recording' ? '正在录音' : state === 'transcribing' ? '正在转成文字' : value ? '语音已转写' : '准备录音'}</strong><small>{state === 'recording' ? `${seconds} / ${MAX_SECONDS} 秒` : '单次最长 60 秒'}</small></div></div>
      {state === 'recording' ? <Button type="button" variant="quiet" onClick={() => void stopRecording()}><Square size={16} />停止</Button> : <Button type="button" onClick={() => void startRecording()} disabled={disabled || state === 'transcribing'}>{value ? <RotateCcw size={17} /> : <Mic size={17} />}{state === 'transcribing' ? '转写中…' : value ? '重新录制' : '开始录音'}</Button>}
    </div>
    {error && <p className="field-error" role="alert">{error}</p>}
  </div>
}
