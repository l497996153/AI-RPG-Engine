import { useState, useEffect, useRef } from 'react';
import {
  Box, Paper, TextField, Button, Typography, Stack,
  Divider, Fab, SwipeableDrawer, ToggleButton, ToggleButtonGroup,
  Card, CardContent, CardActions,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import CasinoIcon from '@mui/icons-material/Casino';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';

// ---------------------------------------------------------------------------
// Types — driven by the backend module schema
// ---------------------------------------------------------------------------

interface LocalizedText {
  zh: string;
  en: string;
}

interface BarDef {
  key: string;
  max_key: string;
  label: string;
  color: string;
}

interface GameSchema {
  bars: BarDef[];
  attributes: string[];
  has_inventory: boolean;
  default_dice: string;
}

interface Terminology {
  gm_name: string;
  gm_short: string;
  player_name: string;
  welcome: LocalizedText;
  ready: LocalizedText;
  thinking: LocalizedText;
  no_response: LocalizedText;
  input_placeholder: LocalizedText;
  enter_room: LocalizedText;
  death_message: LocalizedText;
}

interface ModuleSchema {
  id: string;
  name: string;
  system: string;
  description: string;
  terminology: Terminology;
  game_schema: GameSchema;
}

interface ModuleSummary {
  id: string;
  name: string;
  system: string;
  description: string;
}

interface Message {
  role: 'kp' | 'player' | 'system';
  content: string;
  meta?: 'options' | 'narrative' | 'loading';
}

type Language = 'zh' | 'en';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loc(t: LocalizedText | undefined, lang: Language): string {
  if (!t) return '';
  return lang === 'zh' ? (t.zh || t.en) : (t.en || t.zh);
}

// ---------------------------------------------------------------------------
// LoadingBubble
// ---------------------------------------------------------------------------

function LoadingBubble({ baseText }: { baseText: string }) {
  const [dots, setDots] = useState('');
  useEffect(() => {
    const id = setInterval(() => setDots(prev => (prev.length >= 3 ? '' : prev + '.')), 500);
    return () => clearInterval(id);
  }, []);
  return <Typography variant="body1">{baseText}{dots}</Typography>;
}

// ---------------------------------------------------------------------------
// CharacterPanel — fully schema-driven
// ---------------------------------------------------------------------------

interface CharacterPanelProps {
  backendStatus: 'loading' | 'active' | 'error';
  language: Language;
  onLanguageChange: (e: React.MouseEvent<HTMLElement>, v: Language | null) => void;
  schema: ModuleSchema | null;
  gameState: Record<string, any>;
}

function CharacterPanel({ backendStatus, language, onLanguageChange, schema, gameState }: CharacterPanelProps) {
  const term = schema?.terminology;
  const gs = schema?.game_schema;

  return (
    <Paper sx={{ p: 2, bgcolor: '#2d2d2d', color: '#fff' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6" gutterBottom>
          {term ? loc(term.welcome, language).split('.')[0] || term.player_name : 'Character'}
          {' — '}{term?.player_name ?? 'Player'}
        </Typography>
        <ToggleButtonGroup
          value={language}
          exclusive
          onChange={onLanguageChange}
          size="small"
          sx={{ height: 30 }}
        >
          <ToggleButton value="zh" sx={{ '&.Mui-selected': { color: '#f44336' } }}>中</ToggleButton>
          <ToggleButton value="en" sx={{ '&.Mui-selected': { color: '#f44336' } }}>EN</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Backend status */}
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
        <Box sx={{
          width: 8, height: 8, borderRadius: '50%',
          bgcolor: backendStatus === 'active' ? '#4caf50' : backendStatus === 'loading' ? '#ff9800' : '#f44336',
          boxShadow: backendStatus === 'active' ? '0 0 6px #4caf50' : 'none',
          transition: 'all 0.3s ease',
        }} />
        <Typography variant="caption" sx={{ color: '#bdbdbd', fontWeight: 'bold', letterSpacing: '0.5px' }}>
          BACKEND: {backendStatus === 'active' ? 'ACTIVE' : backendStatus === 'loading' ? 'AWAKENING...' : 'OFFLINE'}
        </Typography>
      </Stack>
      <Divider sx={{ mb: 2, bgcolor: '#444' }} />

      {/* Dynamic bars */}
      {gs?.bars.map(bar => {
        const val = gameState[bar.key];
        const maxVal = gameState[bar.max_key];
        const pct = val != null && maxVal ? Math.max(0, Math.min(100, Math.round((val / Math.max(1, maxVal)) * 100))) : 0;
        return (
          <Box key={bar.key} sx={{ mb: 1 }}>
            <Typography variant="body2">
              {bar.label}: {val ?? '--'}/{maxVal ?? '--'}
            </Typography>
            <Box sx={{ width: '100%', height: 8, bgcolor: '#555', borderRadius: 4 }}>
              <Box sx={{ width: `${pct}%`, height: '100%', bgcolor: bar.color, borderRadius: 4 }} />
            </Box>
          </Box>
        );
      })}

      {/* Dynamic attributes */}
      {gs && gs.attributes.length > 0 && (
        <>
          <Typography variant="subtitle2" sx={{ mt: 2, color: '#ff5252' }}>
            {language === 'zh' ? '基础属性' : 'Attributes'}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mt: 1 }}>
            {gs.attributes.map(attr => (
              <Typography key={attr} variant="caption" sx={{ borderBottom: '1px solid #444' }}>
                {attr}: {gameState.attributes?.[attr] ?? '--'}
              </Typography>
            ))}
          </Box>
        </>
      )}

      {/* Dynamic inventory */}
      {gs?.has_inventory && (
        <>
          <Typography variant="subtitle2" sx={{ mt: 2, color: '#ff5252' }}>
            {language === 'zh' ? '随身物品' : 'Inventory'}
          </Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
            {(!gameState.inventory || gameState.inventory.length === 0) ? (
              <Typography variant="body2" sx={{ color: '#999' }}>
                {language === 'zh' ? '无物品' : 'Empty'}
              </Typography>
            ) : (
              gameState.inventory.map((item: string, i: number) => (
                <Typography key={i} variant="body2" sx={{ bgcolor: '#424242', px: 1, borderRadius: 1 }}>
                  {item}
                </Typography>
              ))
            )}
          </Stack>
        </>
      )}

      {/* Module info */}
      {schema && (
        <Box sx={{ mt: 2, pt: 1, borderTop: '1px solid #444' }}>
          <Typography variant="caption" sx={{ color: '#888' }}>
            {schema.system} — {schema.name}
          </Typography>
        </Box>
      )}
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// ModuleSelector — pick a module before entering a room
// ---------------------------------------------------------------------------

interface ModuleSelectorProps {
  modules: ModuleSummary[];
  onSelect: (id: string) => void;
  language: Language;
  backendStatus: 'loading' | 'active' | 'error';
  roomMsg: string;
}

function ModuleSelector({ modules, onSelect, language, backendStatus, roomMsg }: ModuleSelectorProps) {
  if (modules.length === 0) {
    return (
      <Box sx={{ display: 'flex', height: '100vh', width: '100vw', bgcolor: '#111', color: '#e0e0e0', alignItems: 'center', justifyContent: 'center' }}>
        <Typography variant="h6">{roomMsg}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{
      display: 'flex', flexDirection: 'column', minHeight: '100vh', width: '100vw',
      bgcolor: '#111', color: '#e0e0e0', alignItems: 'center', justifyContent: 'center', p: 3, gap: 3,
    }}>
      <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold', textAlign: 'center' }}>
        {language === 'zh' ? '选择冒险模组' : 'Choose Your Adventure'}
      </Typography>
      <Typography variant="body1" sx={{ color: '#999', mb: 2, textAlign: 'center' }}>
        {language === 'zh' ? '选择一个TTRPG模组开始游戏' : 'Select a TTRPG module to begin'}
      </Typography>

      {backendStatus !== 'active' && (
        <Typography variant="body2" sx={{ color: '#ff9800', mb: 1 }}>
          {backendStatus === 'loading'
            ? (language === 'zh' ? '后端正在唤醒中...' : 'Backend is waking up...')
            : (language === 'zh' ? '后端离线' : 'Backend is offline')}
        </Typography>
      )}

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'center', maxWidth: 900 }}>
        {modules.map(mod => (
          <Card key={mod.id} sx={{
            width: 360, bgcolor: '#1e1e1e', color: '#e0e0e0',
            border: '1px solid #333', transition: 'all 0.3s',
            '&:hover': { borderColor: '#9c27b0', boxShadow: '0 0 12px rgba(156,39,176,0.4)' },
          }}>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>{mod.name}</Typography>
              <Typography variant="caption" sx={{ color: '#aaa' }}>{mod.system}</Typography>
              <Typography variant="body2" sx={{ mt: 1, color: '#ccc' }}>{mod.description}</Typography>
            </CardContent>
            <CardActions>
              <Button
                size="small"
                variant="outlined"
                disabled={backendStatus !== 'active'}
                onClick={() => onSelect(mod.id)}
                sx={{
                  color: '#e0e0e0', borderColor: 'rgba(224,224,224,0.5)',
                  '&:hover': { borderColor: '#9c27b0', bgcolor: 'rgba(156,39,176,0.1)' },
                }}
              >
                {language === 'zh' ? '开始冒险' : 'Start Adventure'}
              </Button>
            </CardActions>
          </Card>
        ))}
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// VTTPage — main page component
// ---------------------------------------------------------------------------

export default function VTTPage() {
  const apiBaseUrl = (import.meta as any).env?.VITE_VTT_API_BASE_URL as string || '';

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [statsOpen, setStatsOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'loading' | 'active' | 'error'>('loading');
  const [language, setLanguage] = useState<Language>('en');
  const [messages, setMessages] = useState<Message[]>([]);
  const [userToken, setUserToken] = useState<string | null>(null);
  const [inRoom, setInRoom] = useState(false);
  const [roomId, setRoomId] = useState<string | null>(null);
  const [roomMsg, setRoomMsg] = useState('Loading...');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Module system
  const [availableModules, setAvailableModules] = useState<ModuleSummary[]>([]);
  const [moduleSchema, setModuleSchema] = useState<ModuleSchema | null>(null);

  // Generic game state
  const [gameState, setGameState] = useState<Record<string, any>>({});

  const term = moduleSchema?.terminology;

  // ------------------------------- Helpers --------------------------------

  async function checkStatus() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/awaken`, { method: 'POST' });
      setBackendStatus(response.ok ? 'active' : 'error');
    } catch {
      setBackendStatus('error');
    }
  }

  async function fetchModules() {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/modules`);
      if (resp.ok) {
        const data = await resp.json();
        setAvailableModules(data.modules || []);
      }
    } catch (e) {
      console.error('Failed to fetch modules:', e);
    }
  }

  async function handleLanguageChange(_e: React.MouseEvent<HTMLElement>, newLang: Language | null) {
    if (!newLang) return;
    setLanguage(newLang);
    const confirmMsg = newLang === 'zh' ? '切换语言会重置当前游戏进度，确定要切换吗？' : 'Switching language will reset current game progress, are you sure?';
    performRoomAction('/api/game/restart', confirmMsg, () => {
      const w = term ? loc(term.welcome, newLang) : (newLang === 'zh' ? '欢迎' : 'Welcome');
      const r = term ? loc(term.ready, newLang) : (newLang === 'zh' ? '准备就绪' : 'Ready');
      setMessages([
        { role: 'system', content: w },
        { role: 'system', content: r, meta: 'options' },
      ]);
      setGameState({});
    }, 'Restart');
  }

  async function handleRoll() {
    if (loading || !roomId) return;
    const formula = moduleSchema?.game_schema.default_dice || '1d20';
    setLoading(true);
    try {
      const params = new URLSearchParams({ formula });
      if (roomId) params.set('room_id', roomId);
      if (userToken) params.set('user_token', userToken);
      const resp = await fetch(`${apiBaseUrl}/api/roll?${params.toString()}`);
      const json = await resp.json();
      if (json.existing) {
        setMessages(prev => [...prev, {
          role: 'system',
          content: language === 'zh' ? `已有结果: ${formula}=${json.total}` : `Already rolled: ${formula}=${json.total}`,
        }]);
      } else if (!resp.ok) {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `${language === 'zh' ? '掷骰失败: ' : 'Roll failed: '}${json.detail || JSON.stringify(json)}`,
        }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'system',
          content: language === 'zh' ? `掷骰结果: ${formula}=${json.total}` : `Roll result: ${formula}=${json.total}`,
        }]);
      }
    } catch {
      const noResp = term ? loc(term.no_response, language) : 'Connection lost.';
      setMessages(prev => [...prev, { role: 'system', content: noResp }]);
    } finally {
      setLoading(false);
    }
  }

  async function refreshState(ridArg?: string, tokenArg?: string) {
    const rid = ridArg || roomId;
    const token = tokenArg || userToken;
    if (!rid || !token) return;
    try {
      const resp = await fetch(`${apiBaseUrl}/api/room/state?room_id=${rid}&user_token=${token}`);
      if (!resp.ok) return;
      const data = await resp.json();
      const state = data.state || {};
      setGameState(state);
    } catch (e) {
      console.error('Failed to refresh state:', e);
    }
  }

  async function refreshHistory(ridArg?: string, tokenArg?: string) {
    const rid = ridArg || roomId;
    const token = tokenArg || userToken;
    if (!rid || !token) return;
    try {
      const resp = await fetch(`${apiBaseUrl}/api/room/history?room_id=${rid}&user_token=${token}`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (Array.isArray(data.messages) && data.messages.length > 0) {
        setMessages(data.messages.map((item: any) => ({
          role: item.role === 'assistant' ? 'kp' : item.role,
          content: item.content,
          meta: item.role === 'assistant' ? 'narrative' : undefined,
        })));
      }
    } catch (e) {
      console.error('Failed to refresh history:', e);
    }
  }

  async function refreshRoomState(rid?: string, token?: string) {
    await Promise.all([refreshState(rid, token), refreshHistory(rid, token)]);
  }

  // ------------------------------- Room actions ---------------------------

  async function enterRoom(moduleId: string) {
    if (!userToken) return;
    if (backendStatus === 'loading') {
      setRoomMsg(language === 'zh' ? '系统正在唤醒，请稍等。' : 'Backend is waking up, please wait.');
      return;
    }
    try {
      const resp = await fetch(`${apiBaseUrl}/api/room/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_token: userToken, module_id: moduleId }),
      });
      if (!resp.ok) {
        setRoomMsg(language === 'zh' ? '房间已满，请稍后再试。' : 'Room is full, please try again later.');
        return;
      }
      const data = await resp.json();
      if (data.room_id) {
        setRoomId(data.room_id);
        localStorage.setItem('vtt_room_id', data.room_id);

        if (data.module_schema) {
          setModuleSchema(data.module_schema);
          localStorage.setItem('vtt_module_schema', JSON.stringify(data.module_schema));
        }

        setInRoom(true);
        const t = data.module_schema?.terminology as Terminology | undefined;
        const welcome = t ? loc(t.welcome, language) : (language === 'zh' ? '欢迎' : 'Welcome');
        const ready = t ? loc(t.ready, language) : (language === 'zh' ? '准备就绪' : 'Ready');
        setMessages([
          { role: 'system', content: welcome },
          { role: 'system', content: ready, meta: 'options' },
        ]);
        setGameState({});
        await refreshRoomState(data.room_id, userToken);
      }
    } catch (e) {
      console.error('Failed to create room:', e);
    }
  }

  async function performRoomAction(
    apiPath: string, confirmText: string, onSuccess: () => void, errorPrefix: string,
  ) {
    if (!roomId || !userToken) return;
    if (!window.confirm(confirmText)) return;
    setLoading(true);
    try {
      const resp = await fetch(`${apiBaseUrl}${apiPath}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_id: roomId, user_token: userToken }),
      });
      if (resp.ok) {
        onSuccess();
      } else {
        const err = await resp.json();
        setMessages(prev => [...prev, { role: 'system', content: `${errorPrefix} failed: ${err.detail || 'unknown error'}` }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'system', content: language === 'zh' ? '网络连接异常。' : 'Network error.' }]);
    } finally {
      setLoading(false);
    }
  }

  async function restartGame() {
    const msg = language === 'zh' ? '确定要重置吗？' : 'Are you sure to restart?';
    const newWelcome = term ? loc(term.welcome, language) : (language === 'zh' ? '世界线已重置。' : 'Timeline reset.');
    const ready = term ? loc(term.ready, language) : (language === 'zh' ? '准备就绪' : 'Ready');
    await performRoomAction('/api/game/restart', msg, () => {
      setMessages([
        { role: 'system', content: newWelcome },
        { role: 'system', content: ready, meta: 'options' },
      ]);
      setGameState({});
    }, 'Restart');
  }

  async function leaveRoom() {
    const msg = language === 'zh' ? '确定退出吗？' : 'Are you sure to leave?';
    await performRoomAction('/api/room/leave', msg, () => {
      localStorage.removeItem('vtt_room_id');
      localStorage.removeItem('vtt_module_schema');
      setRoomId(null);
      setInRoom(false);
      setModuleSchema(null);
      setMessages([]);
      setGameState({});
    }, 'Leave');
  }

  async function sendMsg(command: string, newRoomId?: string) {
    const text = command.trim();
    const rid = newRoomId || roomId;
    if (!text || loading || !rid) return;

    const gmShort = term?.gm_short ?? 'GM';
    const thinkingText = term ? loc(term.thinking, language) : `${gmShort} is thinking`;

    const userMsg: Message = { role: 'player', content: text };
    const loadingMsg: Message = { role: 'kp', content: thinkingText, meta: 'loading' };
    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setLoading(true);

    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: rid, language, user_token: userToken }),
      });
      const data = await response.json();
      const noResp = term ? loc(term.no_response, language) : 'No response.';
      const narrative = data.narrative || noResp;
      const options = data.options || '';

      setMessages(prev => {
        const base = prev.slice(0, -1);
        const next: Message[] = [...base, { role: 'kp', content: narrative, meta: 'narrative' }];
        if (options) next.push({ role: 'kp', content: options, meta: 'options' });
        return next;
      });
      await refreshState(rid);
    } catch {
      setMessages(prev => {
        const base = prev.slice(0, -1);
        const noResp = term ? loc(term.no_response, language) : 'Connection lost.';
        return [...base, { role: 'system', content: noResp }];
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleSend() {
    await sendMsg(input);
    setInput('');
  }

  // ------------------------------- Effects --------------------------------

  useEffect(() => {
    let token = localStorage.getItem('vtt_user_token');
    if (!token) {
      try {
        token = crypto.randomUUID();
      } catch {
        token = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      }
      localStorage.setItem('vtt_user_token', token);
    }
    setUserToken(token);

    const storedRoom = localStorage.getItem('vtt_room_id');
    const storedSchema = localStorage.getItem('vtt_module_schema');

    if (storedSchema) {
      try {
        setModuleSchema(JSON.parse(storedSchema));
      } catch {}
    }

    if (storedRoom && token) {
      (async () => {
        try {
          const resp = await fetch(`${apiBaseUrl}/api/room/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_id: storedRoom, user_token: token }),
          });
          if (resp.ok) {
            const data = await resp.json();
            setRoomId(storedRoom);
            setInRoom(true);
            if (data.module_schema) {
              setModuleSchema(data.module_schema);
              localStorage.setItem('vtt_module_schema', JSON.stringify(data.module_schema));
            }
            setMessages(prev => [...prev, { role: 'system', content: 'Connected to your previous room.' }]);
            await refreshRoomState(storedRoom, token);
          } else {
            localStorage.removeItem('vtt_room_id');
            localStorage.removeItem('vtt_module_schema');
          }
        } catch {
          localStorage.removeItem('vtt_room_id');
          localStorage.removeItem('vtt_module_schema');
        }
      })();
    }

    checkStatus();
    fetchModules();
  }, []);

  useEffect(() => {
    const delay = backendStatus === 'active' ? 600000 : 30000;
    const id = setInterval(checkStatus, delay);
    return () => clearInterval(id);
  }, [backendStatus]);

  useEffect(() => {
    requestAnimationFrame(() => {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
    });
  }, [messages]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (backendStatus === 'active' && availableModules.length === 0) {
      fetchModules();
    }
  }, [backendStatus]);

  useEffect(() => {
    const handleTabClose = () => {
      if (roomId && userToken) {
        try {
          const payload = JSON.stringify({ room_id: roomId, user_token: userToken });
          navigator.sendBeacon(`${apiBaseUrl}/api/room/leave`, new Blob([payload], { type: 'application/json' }));
        } catch {}
      }
    };
    window.addEventListener('beforeunload', handleTabClose);
    window.addEventListener('pagehide', handleTabClose);
    return () => {
      window.removeEventListener('beforeunload', handleTabClose);
      window.removeEventListener('pagehide', handleTabClose);
    };
  }, [roomId, userToken]);

  // ------------------------------- Render ---------------------------------

  const gmShort = term?.gm_short ?? 'GM';
  const playerName = term?.player_name ?? 'Player';
  const placeholderText = term ? loc(term.input_placeholder, language) : (language === 'zh' ? '你要做什么？' : 'What will you do?');

  if (!inRoom) {
    return (
      <ModuleSelector
        modules={availableModules}
        onSelect={enterRoom}
        language={language}
        backendStatus={backendStatus}
        roomMsg={roomMsg}
      />
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: '#1a1a1a', color: '#e0e0e0', p: 1, position: 'relative' }}>
      {/* Chat column */}
      <Box sx={{ flex: 2, display: 'flex', flexDirection: 'column', mr: { md: 1 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mb: 1 }}>
          <Button variant="outlined" color="warning" size="small" onClick={restartGame}>
            {language === 'zh' ? '重新开始' : 'Restart'}
          </Button>
          <Button variant="outlined" color="error" size="small" onClick={leaveRoom}>
            {language === 'zh' ? '退出房间' : 'Leave Room'}
          </Button>
        </Box>

        <Paper sx={{ flex: 1, mb: 1, p: 2, bgcolor: '#2d2d2d', overflowY: 'auto', borderRadius: 2 }} ref={scrollRef}>
          <Stack spacing={2}>
            {messages.map((m, i) => (
              <Box key={i} sx={{ alignSelf: m.role === 'player' ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
                <Typography variant="caption" sx={{ color: m.role === 'kp' ? '#ff5252' : '#4fc3f7', ml: 1 }}>
                  {m.role === 'kp' ? gmShort.toUpperCase() : m.role === 'player' ? playerName.toUpperCase() : 'SYSTEM'}
                </Typography>
                <Paper sx={{
                  p: 1.5,
                  bgcolor: m.role === 'player' ? '#37474f' : '#424242',
                  color: '#fff',
                  borderLeft: m.role === 'kp' ? '4px solid #ff5252' : 'none',
                }}>
                  {m.meta === 'options' ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {m.content.split(/\r?\n/).map(l => l.trim()).filter(Boolean).map((line, idx) => {
                        const isHistorical = i !== messages.length - 1;
                        const formulaMatch = line.match(/\[Formula:\s*(.*?)\]/i);
                        const hasFormula = !!formulaMatch;
                        const text = line.replace(/\[Formula:\s*.*?\]/i, '').trim();
                        return (
                          <Button key={idx} variant="outlined" size="small"
                            disabled={loading || isHistorical}
                            onClick={async () => {
                              if (hasFormula && formulaMatch) {
                                const f = formulaMatch[1].trim();
                                try {
                                  const params = new URLSearchParams({ formula: f });
                                  if (roomId) params.set('room_id', roomId);
                                  if (userToken) params.set('user_token', userToken);
                                  await fetch(`${apiBaseUrl}/api/roll?${params.toString()}`);
                                } catch {}
                              }
                              sendMsg(text);
                            }}
                            sx={{
                              justifyContent: 'flex-start', textTransform: 'none', textAlign: 'left',
                              color: isHistorical ? 'rgba(255,255,255,0.3)' : '#ffd54f',
                              borderColor: isHistorical ? 'rgba(255,255,255,0.1)' : 'rgba(255,213,79,0.5)',
                              '&:hover': {
                                backgroundColor: isHistorical ? 'transparent' : 'rgba(255,213,79,0.1)',
                                borderColor: isHistorical ? 'rgba(255,255,255,0.1)' : '#ffd54f',
                              },
                              '&.Mui-disabled': { color: 'rgba(255,255,255,0.3)', borderColor: 'rgba(255,255,255,0.1)' },
                            }}
                          >
                            {text}
                            {hasFormula && <CasinoIcon sx={{ ml: 1, fontSize: 18, color: isHistorical ? 'rgba(255,82,82,0.3)' : '#ff5252' }} />}
                          </Button>
                        );
                      })}
                    </Box>
                  ) : m.meta === 'loading' ? (
                    <LoadingBubble baseText={m.content} />
                  ) : (
                    <Typography variant="body1">{m.content}</Typography>
                  )}
                </Paper>
              </Box>
            ))}
          </Stack>
        </Paper>

        {/* Input bar */}
        <Box sx={{ display: 'flex', gap: 1, p: 1, bgcolor: '#2d2d2d', borderTop: '1px solid #444' }}>
          <TextField
            fullWidth variant="outlined"
            placeholder={placeholderText}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
            sx={{ bgcolor: '#fff', borderRadius: 1 }}
          />
          <Button variant="contained" color="primary" onClick={handleSend} disabled={loading}>
            <SendIcon />
          </Button>
          <Button variant="contained" color="secondary" sx={{ minWidth: '50px' }} onClick={handleRoll} disabled={loading}>
            <CasinoIcon />
          </Button>
        </Box>
      </Box>

      {/* Right column: character sheet (desktop) */}
      <Box sx={{ display: { xs: 'none', md: 'flex' }, flex: 1, flexDirection: 'column', gap: 1 }}>
        <CharacterPanel
          backendStatus={backendStatus}
          language={language}
          onLanguageChange={handleLanguageChange}
          schema={moduleSchema}
          gameState={gameState}
        />
      </Box>

      {/* Mobile FAB */}
      <Fab
        color="primary" aria-label="stats"
        onClick={() => setStatsOpen(true)}
        sx={{
          position: 'fixed', bottom: 80, right: 16,
          display: { md: 'none' }, bgcolor: '#2d2d2d',
          '&:hover': { bgcolor: '#424242' },
        }}
      >
        <AccountCircleIcon />
      </Fab>

      {/* Mobile drawer */}
      <SwipeableDrawer
        anchor="bottom"
        open={statsOpen}
        onClose={() => setStatsOpen(false)}
        onOpen={() => setStatsOpen(true)}
        slotProps={{
          paper: {
            sx: {
              bgcolor: '#2d2d2d', color: '#fff',
              borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '80vh',
            },
          },
        }}
      >
        <Box sx={{ p: 3 }}>
          <Box sx={{ width: 40, height: 4, bgcolor: '#555', borderRadius: 2, mx: 'auto', mb: 2 }} />
          <CharacterPanel
            backendStatus={backendStatus}
            language={language}
            onLanguageChange={handleLanguageChange}
            schema={moduleSchema}
            gameState={gameState}
          />
        </Box>
      </SwipeableDrawer>
    </Box>
  );
}
