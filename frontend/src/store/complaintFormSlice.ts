import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { Complaint, SeverityLevel, PriorityLevel } from '../types/complaint';
import { api } from '../api/client';

interface ComplaintFormState {
  current: Complaint | null;
  loading: boolean;
  saving: boolean;
  committing: boolean;
  error: string | null;
  justFilledFields: Set<string>;  // fields that just got AI-filled (for highlight animation)
}

const initialState: ComplaintFormState = {
  current: null,
  loading: false,
  saving: false,
  committing: false,
  error: null,
  justFilledFields: new Set(),
};

// ── Thunks ────────────────────────────────────────────────────────────────────

export const createComplaint = createAsyncThunk('complaintForm/create', async () => {
  const { data } = await api.post<Complaint>('/complaints/', {});
  return data;
});

export const fetchComplaint = createAsyncThunk(
  'complaintForm/fetch',
  async (id: string) => {
    const { data } = await api.get<Complaint>(`/complaints/${id}`);
    return data;
  }
);

export const patchComplaint = createAsyncThunk(
  'complaintForm/patch',
  async ({ id, updates }: { id: string; updates: Partial<Complaint> }) => {
    const { data } = await api.patch<Complaint>(`/complaints/${id}`, updates);
    return data;
  }
);

export const commitComplaint = createAsyncThunk(
  'complaintForm/commit',
  async (id: string) => {
    const { data } = await api.patch<{ complaint: Complaint }>(`/complaints/${id}/commit`);
    return data.complaint;
  }
);

// ── Slice ─────────────────────────────────────────────────────────────────────

const complaintFormSlice = createSlice({
  name: 'complaintForm',
  initialState,
  reducers: {
    resetForm(state) {
      state.current = null;
      state.error = null;
      state.justFilledFields = new Set();
    },
    setFieldLocally(
      state,
      action: PayloadAction<{ field: keyof Complaint; value: string | null }>
    ) {
      if (state.current) {
        (state.current as any)[action.payload.field] = action.payload.value;
      }
    },
    markFieldFilled(state, action: PayloadAction<string[]>) {
      // Track which fields were just AI-filled for highlight animation
      state.justFilledFields = new Set(action.payload);
    },
    clearFilledFields(state) {
      state.justFilledFields = new Set();
    },
    applyAIExtraction(state, action: PayloadAction<Partial<Complaint>>) {
      if (state.current) {
        const newFields = Object.keys(action.payload) as (keyof Complaint)[];
        const filled: string[] = [];
        newFields.forEach((key) => {
          const val = action.payload[key];
          if (val !== null && val !== undefined) {
            (state.current as any)[key] = val;
            filled.push(key);
          }
        });
        state.justFilledFields = new Set(filled);
      } else {
        state.current = action.payload as Complaint;
        state.justFilledFields = new Set(Object.keys(action.payload));
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Create
      .addCase(createComplaint.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(createComplaint.fulfilled, (state, action) => {
        state.loading = false;
        state.current = action.payload;
      })
      .addCase(createComplaint.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Failed to create complaint';
      })
      // Fetch
      .addCase(fetchComplaint.pending, (state) => { state.loading = true; })
      .addCase(fetchComplaint.fulfilled, (state, action) => {
        state.loading = false;
        state.current = action.payload;
      })
      .addCase(fetchComplaint.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Failed to load complaint';
      })
      // Patch
      .addCase(patchComplaint.pending, (state) => { state.saving = true; })
      .addCase(patchComplaint.fulfilled, (state, action) => {
        state.saving = false;
        state.current = action.payload;
      })
      .addCase(patchComplaint.rejected, (state, action) => {
        state.saving = false;
        state.error = action.error.message ?? 'Failed to save';
      })
      // Commit
      .addCase(commitComplaint.pending, (state) => { state.committing = true; })
      .addCase(commitComplaint.fulfilled, (state, action) => {
        state.committing = false;
        state.current = action.payload;
      })
      .addCase(commitComplaint.rejected, (state, action) => {
        state.committing = false;
        state.error = action.error.message ?? 'Failed to commit';
      });
  },
});

export const { resetForm, setFieldLocally, markFieldFilled, clearFilledFields, applyAIExtraction } =
  complaintFormSlice.actions;

export default complaintFormSlice.reducer;
