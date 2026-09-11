import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { ChatMessage, ExtractionStatus } from '../types/complaint';
import { api } from '../api/client';

export const getChatStorageKey = (complaintId: string) => `complaint_iq_chat_${complaintId}`;

interface CopilotChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  extractionStatus: ExtractionStatus;
  extractionProgress: number;        // 0–100
  extractionStatusLabel: string;     // "Extracting tabular data via OCR…"
  isProcessing: boolean;
  error: string | null;
}

const DEFAULT_WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    'Upload a complaint document or paste text above. I will automatically extract the details and populate the form for you.',
  created_at: new Date().toISOString(),
};

const initialState: CopilotChatState = {
  messages: [DEFAULT_WELCOME_MESSAGE],
  sessionId: null,
  extractionStatus: 'idle',
  extractionProgress: 0,
  extractionStatusLabel: '',
  isProcessing: false,
  error: null,
};

function persistMessages(complaintId: string | null, messages: ChatMessage[]) {
  if (!complaintId) return;
  try {
    localStorage.setItem(getChatStorageKey(complaintId), JSON.stringify(messages));
  } catch {
    // ignore
  }
}

// ── Thunks ────────────────────────────────────────────────────────────────────

export const sendChatMessage = createAsyncThunk(
  'copilotChat/send',
  async ({ complaintId, message }: { complaintId: string; message: string }) => {
    const { data } = await api.post('/copilot/chat', {
      complaint_id: complaintId,
      message,
    });
    return {
      complaintId,
      reply: data.reply as string,
      updated_fields: (data.updated_fields || {}) as Record<string, string>,
    };
  }
);

// ── Slice ─────────────────────────────────────────────────────────────────────

const copilotChatSlice = createSlice({
  name: 'copilotChat',
  initialState,
  reducers: {
    addUserMessage(
      state,
      action: PayloadAction<string | { message: string; complaintId?: string | null }>
    ) {
      const content = typeof action.payload === 'string' ? action.payload : action.payload.message;
      const complaintId = typeof action.payload === 'string' ? null : action.payload.complaintId;
      const newMsg: ChatMessage = {
        id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      state.messages.push(newMsg);
      if (complaintId) {
        persistMessages(complaintId, state.messages);
      }
    },
    addAssistantMessage(
      state,
      action: PayloadAction<string | { message: string; complaintId?: string | null }>
    ) {
      const content = typeof action.payload === 'string' ? action.payload : action.payload.message;
      const complaintId = typeof action.payload === 'string' ? null : action.payload.complaintId;
      const newMsg: ChatMessage = {
        id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role: 'assistant',
        content,
        created_at: new Date().toISOString(),
      };
      state.messages.push(newMsg);
      if (complaintId) {
        persistMessages(complaintId, state.messages);
      }
    },
    restoreChatForComplaint(state, action: PayloadAction<string>) {
      const complaintId = action.payload;
      const saved = localStorage.getItem(getChatStorageKey(complaintId));
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) {
            state.messages = parsed;
            return;
          }
        } catch {
          // ignore parse error
        }
      }
      state.messages = [DEFAULT_WELCOME_MESSAGE];
    },
    setExtractionStatus(
      state,
      action: PayloadAction<{ status: ExtractionStatus; progress: number; label?: string }>
    ) {
      state.extractionStatus = action.payload.status;
      state.extractionProgress = action.payload.progress;
      state.extractionStatusLabel = action.payload.label ?? '';
    },
    setSessionId(state, action: PayloadAction<string>) {
      state.sessionId = action.payload;
    },
    setProcessing(state, action: PayloadAction<boolean>) {
      state.isProcessing = action.payload;
    },
    resetChat(state, action: PayloadAction<string | undefined>) {
      const complaintId = action.payload;
      if (complaintId) {
        localStorage.removeItem(getChatStorageKey(complaintId));
      }
      state.messages = [DEFAULT_WELCOME_MESSAGE];
      state.sessionId = null;
      state.extractionStatus = 'idle';
      state.extractionProgress = 0;
      state.extractionStatusLabel = '';
      state.isProcessing = false;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendChatMessage.pending, (state) => {
        state.isProcessing = true;
        state.error = null;
      })
      .addCase(sendChatMessage.fulfilled, (state, action) => {
        state.isProcessing = false;
        const newMsg: ChatMessage = {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: action.payload.reply,
          created_at: new Date().toISOString(),
        };
        state.messages.push(newMsg);
        persistMessages(action.payload.complaintId, state.messages);
      })
      .addCase(sendChatMessage.rejected, (state, action) => {
        state.isProcessing = false;
        state.error = action.error.message ?? 'Failed to send message';
      });
  },
});

export const {
  addUserMessage,
  addAssistantMessage,
  restoreChatForComplaint,
  setExtractionStatus,
  setSessionId,
  setProcessing,
  resetChat,
} = copilotChatSlice.actions;

export default copilotChatSlice.reducer;
