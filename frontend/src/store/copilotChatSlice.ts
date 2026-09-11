import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { ChatMessage, ExtractionStatus } from '../types/complaint';
import { api } from '../api/client';

interface CopilotChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  extractionStatus: ExtractionStatus;
  extractionProgress: number;        // 0–100
  extractionStatusLabel: string;     // "Extracting tabular data via OCR…"
  isProcessing: boolean;
  error: string | null;
}

const initialState: CopilotChatState = {
  messages: [
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Upload a complaint document or paste text above. I will automatically extract the details and populate the form for you.',
      created_at: new Date().toISOString(),
    },
  ],
  sessionId: null,
  extractionStatus: 'idle',
  extractionProgress: 0,
  extractionStatusLabel: '',
  isProcessing: false,
  error: null,
};

// ── Thunks ────────────────────────────────────────────────────────────────────

export const sendChatMessage = createAsyncThunk(
  'copilotChat/send',
  async ({ complaintId, message }: { complaintId: string; message: string }) => {
    const { data } = await api.post('/copilot/chat', {
      complaint_id: complaintId,
      message,
    });
    return data as { reply: string; updated_fields: Record<string, string> };
  }
);

// ── Slice ─────────────────────────────────────────────────────────────────────

const copilotChatSlice = createSlice({
  name: 'copilotChat',
  initialState,
  reducers: {
    addUserMessage(state, action: PayloadAction<string>) {
      state.messages.push({
        id: `msg-${Date.now()}`,
        role: 'user',
        content: action.payload,
        created_at: new Date().toISOString(),
      });
    },
    addAssistantMessage(state, action: PayloadAction<string>) {
      state.messages.push({
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: action.payload,
        created_at: new Date().toISOString(),
      });
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
    resetChat(state) {
      Object.assign(state, initialState);
      // Fresh session ID
      state.sessionId = null;
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
        state.messages.push({
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: action.payload.reply,
          created_at: new Date().toISOString(),
        });
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
  setExtractionStatus,
  setSessionId,
  setProcessing,
  resetChat,
} = copilotChatSlice.actions;

export default copilotChatSlice.reducer;
