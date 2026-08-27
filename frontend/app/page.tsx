'use client';

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowUpRight, Check, ChevronDown, CircleAlert, FileText, LoaderCircle, LogOut, Mic, Pause, Play, Search, Square, Trash2, Upload, UserRound } from 'lucide-react';
import { apiUrl, configurationError, supabase } from '@/lib/supabase';

type Screen = 'consultations' | 'new' | 'review' | 'profile';
type Status = 'processing' | 'ready_for_review' | 'failed';
type Consultation = { consultation_id: string; patient_id: string; patient_name: string; status: Status; error?: string | null; created_at: string };
type Segment = { segment_id: string; speaker_id: string; speaker_role: string; start_ms: number; end_ms: number; original_text: string; english_text?: string | null; edited_text?: string | null };
type Note = { chief_complaint: string; history: string; examination: string; assessment: string; plan: string };
type Detail = { consultation: Consultation; segments: Segment[]; opdNote: Note | null; audioUrl?: string };
type AppUser = { email: string; name: string };

const roles = ['doctor', 'patient', 'relative', 'nurse', 'unknown'];
const emptyNote: Note = { chief_complaint: '', history: '', examination: '', assessment: '', plan: '' };

const formatDate = (date: string) => new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }).format(new Date(date));
const formatTime = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;
const formatToday = () => new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Asia/Kolkata' }).format(new Date());

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!supabase || !apiUrl) throw new Error('Connect Supabase and the API first.');
  const { data } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (data.session?.access_token) headers.set('Authorization', `Bearer ${data.session.access_token}`);
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${apiUrl}/api/v1${path}`, { ...init, headers });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'Something went wrong.');
  return response.json();
}

async function fetchConsultationDetail(consultationId: string): Promise<Detail> {
  const data = await api<{ consultation: Consultation; segments: Segment[]; opdNote: Note | null }>(`/consultations/${consultationId}`);
  let audioUrl = '';
  try { audioUrl = (await api<{ audioUrl: string }>(`/consultations/${consultationId}/audio`)).audioUrl; } catch {}
  return { ...data, audioUrl };
}

function Logo({ onClick }: { onClick?: () => void }) {
  return <button className="brand" onClick={onClick}><span className="logo"><FileText size={18} /></span><span>DocScribe</span></button>;
}

function AuthLogo() {
  return <div className="auth-brand" aria-label="DocScribe"><svg className="auth-symbol" viewBox="0 0 64 64" aria-hidden="true"><path d="M18 9v13a10 10 0 0 0 20 0V9M14 9h8M34 9h8M28 32v7a10 10 0 0 0 10 10h4M38 17h12a8 8 0 0 1 8 8v16a8 8 0 0 1-8 8h-4l-8 7v-7M44 27h8M44 34h8M44 41h5" /></svg><span className="auth-wordmark">DocScribe</span></div>;
}

function Auth() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!supabase) return setMessage(configurationError || 'Authentication is not configured.');
    setBusy(true); setMessage('');
    const result = mode === 'signin' ? await supabase.auth.signInWithPassword({ email, password }) : await supabase.auth.signUp({ email, password, options: { data: { name } } });
    setBusy(false);
    if (result.error) setMessage(result.error.message);
    else if (mode === 'signup' && !result.data.session) setMessage('Check your email to continue.');
  }
  return <main className="auth-page"><section className="auth-intro"><AuthLogo /><div><h1>Listen fully.<br />Document clearly.</h1></div></section><section className="auth-panel"><form className="auth-card" onSubmit={submit}><div><h2>{mode === 'signin' ? 'Welcome back' : 'Create account'}</h2>{mode === 'signin' && <p>Sign in to continue.</p>}</div>{mode === 'signup' && <label>Name<input value={name} onChange={e => setName(e.target.value)} required /></label>}<label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength={6} required /></label>{message && <p className="form-message">{message}</p>}<button className="primary wide" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : mode === 'signin' ? 'Sign in' : 'Create account'}</button><button type="button" className="text-button" onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setMessage(''); }}>{mode === 'signin' ? 'New here? Create account' : 'Already have an account? Sign in'}</button></form></section></main>;
}

function Dashboard({ items, busy, onNew, onOpen }: { items: Consultation[]; busy: boolean; onNew: () => void; onOpen: (item: Consultation) => void }) {
  const [query, setQuery] = useState('');
  const filtered = items.filter(item => `${item.patient_name} ${item.patient_id}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="content"><div className="page-head"><div><p className="eyebrow" suppressHydrationWarning>{formatToday()}</p><h1>Consultations</h1></div><button className="primary" onClick={onNew}><Mic size={17} />New consultation</button></div><div className="panel list-panel"><div className="list-head"><div><h2>Recent</h2><p>{items.length} consultations</p></div><label className="search"><Search size={16} /><input aria-label="Search consultations" placeholder="Search" value={query} onChange={e => setQuery(e.target.value)} /></label></div><div className="consultation-list">{busy ? <div className="empty"><LoaderCircle className="spin" />Loading</div> : filtered.length ? filtered.map(item => <button className="consultation-row" key={item.consultation_id} onClick={() => onOpen(item)}><span><strong>{item.patient_name || 'Unnamed patient'}</strong><small>{item.patient_id || item.consultation_id}</small></span><time>{formatDate(item.created_at)}</time><span className={`status ${item.status}`}>{item.status === 'ready_for_review' ? 'Ready' : item.status === 'processing' ? 'Processing' : 'Failed'}</span><i><ArrowUpRight size={16} /></i></button>) : <div className="empty">No consultations found.</div>}</div></div></section>;
}

async function blobToWav(blob: Blob) {
  const context = new AudioContext();
  const audio = await context.decodeAudioData(await blob.arrayBuffer());
  const mono = audio.getChannelData(0);
  const buffer = new ArrayBuffer(44 + mono.length * 2);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)));
  write(0, 'RIFF'); view.setUint32(4, 36 + mono.length * 2, true); write(8, 'WAVE'); write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, audio.sampleRate, true); view.setUint32(28, audio.sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, mono.length * 2, true);
  mono.forEach((sample, index) => view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 0x8000 : 0x7fff), true));
  await context.close();
  return new File([buffer], 'consultation.wav', { type: 'audio/wav' });
}

function Recorder({ onBack, onSubmit }: { onBack: () => void; onSubmit: (audio: File, name: string, patientId: string) => Promise<void> }) {
  const [name, setName] = useState(''); const [patientId, setPatientId] = useState(''); const [recording, setRecording] = useState(false); const [paused, setPaused] = useState(false); const [seconds, setSeconds] = useState(0); const [audio, setAudio] = useState<File | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const recorder = useRef<MediaRecorder | null>(null); const stream = useRef<MediaStream | null>(null); const chunks = useRef<Blob[]>([]); const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); stream.current?.getTracks().forEach(track => track.stop()); }, []);
  async function start() {
    try { stream.current = await navigator.mediaDevices.getUserMedia({ audio: true }); recorder.current = new MediaRecorder(stream.current); chunks.current = []; recorder.current.ondataavailable = event => chunks.current.push(event.data); recorder.current.onstop = async () => { const file = await blobToWav(new Blob(chunks.current, { type: recorder.current?.mimeType })); setAudio(file); stream.current?.getTracks().forEach(track => track.stop()); }; recorder.current.start(); setRecording(true); setSeconds(0); timer.current = setInterval(() => setSeconds(value => value + 1), 1000); } catch { setError('Microphone access is required.'); }
  }
  function pause() { if (!recorder.current) return; if (paused) recorder.current.resume(); else recorder.current.pause(); setPaused(!paused); }
  function stop() { recorder.current?.stop(); setRecording(false); setPaused(false); if (timer.current) clearInterval(timer.current); }
  function selectFile(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (file) { setAudio(file); setError(''); } }
  async function submit() { if (!audio) return setError('Record or upload audio first.'); setBusy(true); setError(''); try { await onSubmit(audio, name, patientId); } catch (e) { setError(e instanceof Error ? e.message : 'Could not create consultation.'); setBusy(false); } }
  return <section className="content narrow"><button className="back" onClick={onBack}><ArrowLeft size={17} />Consultations</button><div className="page-head compact"><div><p className="eyebrow">New consultation</p><h1>Record</h1></div></div><div className="recorder-grid"><div className="panel patient-form"><label>Patient name<input placeholder="Optional" value={name} onChange={e => setName(e.target.value)} /></label><label>Patient ID<input placeholder="Optional" value={patientId} onChange={e => setPatientId(e.target.value)} /></label></div><div className={`panel recorder ${recording ? 'is-recording' : ''}`}><div className="wave" aria-hidden="true">{Array.from({ length: 34 }, (_, i) => <i key={i} style={{ height: recording && !paused ? `${22 + ((i * 17) % 56)}%` : '20%' }} />)}</div><strong>{recording ? paused ? 'Paused' : 'Recording' : audio ? 'Audio ready' : 'Ready to record'}</strong><span className="timer">{String(Math.floor(seconds / 60)).padStart(2, '0')}:{String(seconds % 60).padStart(2, '0')}</span><div className="record-actions">{!recording ? <button className="record-button" onClick={start} aria-label="Start recording"><Mic size={23} /></button> : <><button className="round-button" onClick={pause} aria-label={paused ? 'Resume' : 'Pause'}>{paused ? <Play size={19} /> : <Pause size={19} />}</button><button className="record-button small" onClick={stop} aria-label="Stop recording"><Square size={18} fill="currentColor" /></button></>}</div><label className="upload"><Upload size={16} />{audio ? audio.name : 'Upload audio'}<input type="file" accept=".mp3,.wav,.m4a,audio/*" onChange={selectFile} /></label></div></div>{error && <p className="inline-error">{error}</p>}<button className="primary submit" onClick={submit} disabled={busy}>{busy ? <><LoaderCircle className="spin" size={17} />Creating</> : <>Create consultation<ArrowUpRight size={17} /></>}</button></section>;
}

function Review({ detail, onBack, onChange, onSaveTranscript, onSaveNote, onDelete, onRetry }: { detail: Detail; onBack: () => void; onChange: (detail: Detail) => void; onSaveTranscript: () => Promise<void>; onSaveNote: () => Promise<void>; onDelete: () => Promise<void>; onRetry: () => void }) {
  const [tab, setTab] = useState<'transcript' | 'note'>('transcript'); const [saving, setSaving] = useState(false); const [deleting, setDeleting] = useState(false); const [actionError, setActionError] = useState('');
  const save = async () => { setSaving(true); setActionError(''); try { await (tab === 'transcript' ? onSaveTranscript() : onSaveNote()); } catch (error) { setActionError(error instanceof Error ? error.message : 'Could not save changes.'); } finally { setSaving(false); } };
  const remove = async () => { setDeleting(true); setActionError(''); try { await onDelete(); } catch (error) { setActionError(error instanceof Error ? error.message : 'Could not delete consultation.'); } finally { setDeleting(false); } };
  const setSegment = (index: number, patch: Partial<Segment>) => onChange({ ...detail, segments: detail.segments.map((item, i) => i === index ? { ...item, ...patch } : item) });
  const setSpeaker = (speakerId: string, speakerRole: string) => onChange({ ...detail, segments: detail.segments.map(item => item.speaker_id === speakerId ? { ...item, speaker_role: speakerRole } : item) });
  const setNote = (key: keyof Note, value: string) => onChange({ ...detail, opdNote: { ...(detail.opdNote || emptyNote), [key]: value } });
  if (detail.consultation.status === 'processing') return <section className="content narrow"><button className="back" onClick={onBack}><ArrowLeft size={17} />Consultations</button><div className="panel processing-card"><span><LoaderCircle className="spin" /></span><h1>Preparing your note</h1><p>This page updates automatically when processing finishes.</p></div></section>;
  if (detail.consultation.status === 'failed') return <section className="content narrow"><button className="back" onClick={onBack}><ArrowLeft size={17} />Consultations</button><div className="panel processing-card failed-card"><span><CircleAlert /></span><h1>Processing failed</h1><p>{detail.consultation.error || 'The audio could not be processed. Please upload it again.'}</p><div className="failure-actions"><button className="primary" onClick={onRetry}><Upload size={17} />Upload again</button><button className="delete-button" onClick={remove} disabled={deleting}>{deleting ? <LoaderCircle className="spin" size={17} /> : <Trash2 size={17} />}Delete</button></div>{actionError && <p className="inline-error">{actionError}</p>}</div></section>;
  return <section className="content"><button className="back" onClick={onBack}><ArrowLeft size={17} />Consultations</button><div className="review-head"><div><span className="status ready_for_review">Ready</span><h1>{detail.consultation.patient_name || 'Consultation'}</h1><p>{detail.consultation.patient_id || detail.consultation.consultation_id} · {formatDate(detail.consultation.created_at)}</p></div><button className="danger-icon" aria-label="Delete consultation" onClick={remove} disabled={deleting}>{deleting ? <LoaderCircle className="spin" size={18} /> : <Trash2 size={18} />}</button></div>{detail.audioUrl && <audio className="audio" controls src={detail.audioUrl} />}<div className="review-tabs"><button className={tab === 'transcript' ? 'active' : ''} onClick={() => setTab('transcript')}>Transcript</button><button className={tab === 'note' ? 'active' : ''} onClick={() => setTab('note')}>OPD note</button></div>{tab === 'transcript' ? <div className="panel transcript">{detail.segments.map((segment, index) => { const firstOccurrence = detail.segments.findIndex(item => item.speaker_id === segment.speaker_id) === index; return <article className="segment" key={segment.segment_id}><time>{formatTime(segment.start_ms)}</time><div>{firstOccurrence ? <label className="role-select"><select value={segment.speaker_role} onChange={e => setSpeaker(segment.speaker_id, e.target.value)}>{roles.map(role => <option value={role} key={role}>{role[0].toUpperCase() + role.slice(1)}</option>)}</select><ChevronDown size={14} /></label> : <span className="role-label">{segment.speaker_role}</span>}<textarea value={segment.edited_text ?? segment.english_text ?? segment.original_text} onChange={e => setSegment(index, { edited_text: e.target.value })} rows={2} /></div></article>; })}</div> : <div className="panel note-form">{(Object.keys(emptyNote) as (keyof Note)[]).map(key => <label key={key}><span>{key.replaceAll('_', ' ')}</span><textarea rows={key === 'history' || key === 'plan' ? 4 : 3} value={(detail.opdNote || emptyNote)[key]} onChange={e => setNote(key, e.target.value)} /></label>)}</div>}{actionError && <p className="inline-error">{actionError}</p>}<div className="save-bar"><span>Changes are saved to this consultation.</span><button className="primary" onClick={save} disabled={saving}>{saving ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}Save</button></div></section>;
}

function Profile({ user, onBack, onUpdate, onLogout }: { user: AppUser; onBack: () => void; onUpdate: (name: string) => Promise<void>; onLogout: () => void }) {
  const [name, setName] = useState(user.name); const [saved, setSaved] = useState(false);
  return <section className="content narrow"><button className="back" onClick={onBack}><ArrowLeft size={17} />Consultations</button><div className="page-head compact"><div><p className="eyebrow">Account</p><h1>Profile</h1></div></div><div className="panel profile-card"><div className="avatar"><UserRound size={26} /></div><label>Name<input value={name} onChange={e => setName(e.target.value)} /></label><label>Email<input value={user.email} disabled /></label><button className="primary" onClick={async () => { await onUpdate(name); setSaved(true); setTimeout(() => setSaved(false), 1600); }}>{saved ? <><Check size={17} />Saved</> : 'Save profile'}</button><button className="logout" onClick={onLogout}><LogOut size={17} />Sign out</button></div></section>;
}

export default function Home() {
  const [user, setUser] = useState<AppUser | null>(null); const [ready, setReady] = useState(false); const [screen, setScreen] = useState<Screen>('consultations'); const [items, setItems] = useState<Consultation[]>([]); const [detail, setDetail] = useState<Detail | null>(null); const [busy, setBusy] = useState(false); const [toast, setToast] = useState('');
  useEffect(() => { if (!supabase) return; supabase.auth.getUser().then(({ data }) => { if (data.user) setUser({ email: data.user.email || '', name: data.user.user_metadata?.name || 'Doctor' }); setReady(true); }); const { data } = supabase.auth.onAuthStateChange((_event, session) => setUser(session?.user ? { email: session.user.email || '', name: session.user.user_metadata?.name || 'Doctor' } : null)); return () => data.subscription.unsubscribe(); }, []);
  useEffect(() => { if (!user || screen !== 'consultations') return; api<{ consultations: Consultation[] }>('/consultations/').then(data => setItems(data.consultations)).catch(e => notify(e.message)).finally(() => setBusy(false)); }, [user, screen]);
  const processingId = screen === 'review' && detail?.consultation.status === 'processing' ? detail.consultation.consultation_id : null;
  useEffect(() => {
    if (!processingId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const result = await api<{ consultationId: string; status: Status; error: string | null }>(`/consultations/${processingId}/status`);
        if (cancelled) return;
        if (result.status === 'ready_for_review') {
          const loaded = await fetchConsultationDetail(processingId);
          if (!cancelled) { setDetail(loaded); setItems(current => current.map(item => item.consultation_id === processingId ? loaded.consultation : item)); }
          return;
        }
        if (result.status === 'failed') {
          setDetail(current => current ? { ...current, consultation: { ...current.consultation, status: 'failed', error: result.error } } : current);
          setItems(current => current.map(item => item.consultation_id === processingId ? { ...item, status: 'failed', error: result.error } : item));
          return;
        }
      } catch {}
      if (!cancelled) timer = setTimeout(poll, 3000);
    };
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [processingId]);
  function notify(message: string) { setToast(message); setTimeout(() => setToast(''), 2200); }
  async function open(item: Consultation) { setScreen('review'); setBusy(true); try { setDetail(await fetchConsultationDetail(item.consultation_id)); } catch (e) { notify(e instanceof Error ? e.message : 'Could not load consultation.'); setScreen('consultations'); } finally { setBusy(false); } }
  async function create(audio: File, name: string, patientId: string) { const body = new FormData(); body.append('audio', audio); body.append('patient_name', name); body.append('patient_id', patientId); const result = await api<{ consultationId: string; status: Status }>('/consultations/', { method: 'POST', body }); const consultation = { consultation_id: result.consultationId, patient_name: name, patient_id: patientId, status: result.status, created_at: new Date().toISOString() }; setDetail({ consultation, segments: [], opdNote: null }); setScreen('review'); }
  async function saveTranscript() { if (!detail) return; await api(`/consultations/${detail.consultation.consultation_id}/transcript`, { method: 'PATCH', body: JSON.stringify({ segments: detail.segments.map(({ segment_id, speaker_role, edited_text }) => ({ segment_id, speaker_role, edited_text })) }) }); notify('Transcript saved.'); }
  async function saveNote() { if (!detail || !detail.opdNote) return; await api(`/consultations/${detail.consultation.consultation_id}/opd-note`, { method: 'PATCH', body: JSON.stringify(detail.opdNote) }); notify('OPD note saved.'); }
  async function remove() { if (!detail || !window.confirm('Delete this consultation?')) return; await api(`/consultations/${detail.consultation.consultation_id}`, { method: 'DELETE' }); setItems(items.filter(item => item.consultation_id !== detail.consultation.consultation_id)); setDetail(null); setScreen('consultations'); }
  async function updateProfile(name: string) { if (supabase) await supabase.auth.updateUser({ data: { name } }); setUser(user ? { ...user, name } : user); }
  async function logout() { if (supabase) await supabase.auth.signOut(); setUser(null); setScreen('consultations'); }
  if (configurationError) return <main className="loading"><Logo /><p className="inline-error">{configurationError}</p></main>;
  if (!ready) return <main className="loading"><Logo /><LoaderCircle className="spin" /></main>;
  if (!user) return <Auth />;
  return <main className="app-shell"><header className="topbar"><div className="topbar-inner"><Logo onClick={() => setScreen('consultations')} /><button className="profile-button" onClick={() => setScreen('profile')}><span>{user.name.split(' ').map(value => value[0]).join('').slice(0, 2)}</span><div><strong>{user.name}</strong><small>{user.email}</small></div></button></div></header>{screen === 'consultations' && <Dashboard items={items} busy={busy} onNew={() => setScreen('new')} onOpen={open} />}{screen === 'new' && <Recorder onBack={() => setScreen('consultations')} onSubmit={create} />}{screen === 'review' && (detail ? <Review detail={detail} onBack={() => setScreen('consultations')} onChange={setDetail} onSaveTranscript={saveTranscript} onSaveNote={saveNote} onDelete={remove} onRetry={() => { setDetail(null); setScreen('new'); }} /> : <section className="loading-section"><LoaderCircle className="spin" /></section>)}{screen === 'profile' && <Profile user={user} onBack={() => setScreen('consultations')} onUpdate={updateProfile} onLogout={logout} />}{toast && <div className="toast"><Check size={16} />{toast}</div>}</main>;
}
