import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { Complaint } from '../types/complaint';
import { api } from '../api/client';
import { validateComplaintField, validateEntireComplaint, FormValidationErrors } from '../utils/validation';

export const STORAGE_ACTIVE_ID_KEY = 'complaint_iq_active_complaint_id';
export const getDraftStorageKey = (id: string) => `complaint_iq_draft_${id}`;

interface ComplaintFormState {
  current: Complaint | null;
  loading: boolean;
  saving: boolean;
  committing: boolean;
  error: string | null;
  justFilledFields: Set<string>;      // fields that just got AI-filled (for highlight animation)
  validationErrors: FormValidationErrors;
  touchedFields: Record<string, boolean>;
}

const initialState: ComplaintFormState = {
  current: null,
  loading: false,
  saving: false,
  committing: false,
  error: null,
  justFilledFields: new Set(),
  validationErrors: {},
  touchedFields: {},
};

// ── Thunks ────────────────────────────────────────────────────────────────────

/**
 * Creates a brand-new complaint draft and records its ID in localStorage.
 */
export const createComplaint = createAsyncThunk('complaintForm/create', async () => {
  const { data } = await api.post<Complaint>('/complaints/', {});
  localStorage.setItem(STORAGE_ACTIVE_ID_KEY, data.id);
  localStorage.setItem(getDraftStorageKey(data.id), JSON.stringify(data));
  return data;
});

/**
 * Restores an existing complaint session from localStorage if available;
 * otherwise creates a new draft complaint.
 */
export const restoreOrInitComplaint = createAsyncThunk(
  'complaintForm/restoreOrInit',
  async (_, { dispatch }) => {
    const savedId = localStorage.getItem(STORAGE_ACTIVE_ID_KEY);
    if (savedId) {
      try {
        const { data } = await api.get<Complaint>(`/complaints/${savedId}`);
        // If local draft has unsaved progress, merge it
        const localDraftStr = localStorage.getItem(getDraftStorageKey(savedId));
        if (localDraftStr) {
          try {
            const localDraft = JSON.parse(localDraftStr);
            const merged = { ...data, ...localDraft };
            return merged as Complaint;
          } catch {
            // ignore JSON parse failure
          }
        }
        return data;
      } catch (err) {
        console.warn(`Could not restore active complaint ${savedId}, initializing new draft.`, err);
        localStorage.removeItem(STORAGE_ACTIVE_ID_KEY);
        localStorage.removeItem(getDraftStorageKey(savedId));
      }
    }
    // Fall back to creating a new draft
    const { data } = await api.post<Complaint>('/complaints/', {});
    localStorage.setItem(STORAGE_ACTIVE_ID_KEY, data.id);
    localStorage.setItem(getDraftStorageKey(data.id), JSON.stringify(data));
    return data;
  }
);

export const fetchComplaint = createAsyncThunk(
  'complaintForm/fetch',
  async (id: string) => {
    const { data } = await api.get<Complaint>(`/complaints/${id}`);
    localStorage.setItem(STORAGE_ACTIVE_ID_KEY, data.id);
    return data;
  }
);

export const patchComplaint = createAsyncThunk(
  'complaintForm/patch',
  async ({ id, updates }: { id: string; updates: Partial<Complaint> }) => {
    const { data } = await api.patch<Complaint>(`/complaints/${id}`, updates);
    localStorage.setItem(getDraftStorageKey(id), JSON.stringify(data));
    return data;
  }
);

export const commitComplaint = createAsyncThunk(
  'complaintForm/commit',
  async (id: string) => {
    const { data } = await api.patch<{ complaint: Complaint }>(`/complaints/${id}/commit`);
    localStorage.setItem(getDraftStorageKey(id), JSON.stringify(data.complaint));
    return data.complaint;
  }
);

// ── Slice ─────────────────────────────────────────────────────────────────────

const complaintFormSlice = createSlice({
  name: 'complaintForm',
  initialState,
  reducers: {
    resetForm(state) {
      const activeId = state.current?.id;
      if (activeId) {
        localStorage.removeItem(getDraftStorageKey(activeId));
      }
      localStorage.removeItem(STORAGE_ACTIVE_ID_KEY);
      state.current = null;
      state.error = null;
      state.justFilledFields = new Set();
      state.validationErrors = {};
      state.touchedFields = {};
    },
    setFieldLocally(
      state,
      action: PayloadAction<{ field: keyof Complaint; value: string | null }>
    ) {
      const { field, value } = action.payload;
      if (state.current) {
        (state.current as any)[field] = value;

        // Persist to local storage draft backup
        try {
          localStorage.setItem(
            getDraftStorageKey(state.current.id),
            JSON.stringify(state.current)
          );
        } catch {
          // ignore quota errors
        }

        // Real-time validation if touched
        if (state.touchedFields[field as string]) {
          const err = validateComplaintField(field as string, value, state.current);
          if (err) {
            state.validationErrors[field as string] = err;
          } else {
            delete state.validationErrors[field as string];
          }
        }
      }
    },
    setFieldTouched(state, action: PayloadAction<string>) {
      const field = action.payload;
      state.touchedFields[field] = true;
      if (state.current) {
        const val = (state.current as any)[field];
        const err = validateComplaintField(field, val, state.current);
        if (err) {
          state.validationErrors[field] = err;
        } else {
          delete state.validationErrors[field];
        }
      }
    },
    validateForm(state) {
      if (!state.current) return;
      const { errors } = validateEntireComplaint(state.current);
      state.validationErrors = errors;
      // Mark all validated fields as touched so errors display
      Object.keys(errors).forEach((f) => {
        state.touchedFields[f] = true;
      });
    },
    clearValidationError(state, action: PayloadAction<string>) {
      delete state.validationErrors[action.payload];
    },
    markFieldFilled(state, action: PayloadAction<string[]>) {
      state.justFilledFields = new Set(action.payload);
      // Re-validate fields that were filled by AI to clear errors
      if (state.current) {
        action.payload.forEach((f) => {
          const val = (state.current as any)[f];
          const err = validateComplaintField(f, val, state.current);
          if (err) {
            state.validationErrors[f] = err;
          } else {
            delete state.validationErrors[f];
          }
        });
      }
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
            // Clear any previous validation errors for populated fields
            delete state.validationErrors[key as string];
          }
        });
        state.justFilledFields = new Set(filled);
        try {
          localStorage.setItem(
            getDraftStorageKey(state.current.id),
            JSON.stringify(state.current)
          );
        } catch {
          // ignore quota
        }
      } else {
        state.current = action.payload as Complaint;
        state.justFilledFields = new Set(Object.keys(action.payload));
      }
    },
    clearFormError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Create
      .addCase(createComplaint.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(createComplaint.fulfilled, (state, action) => {
        state.loading = false;
        state.current = action.payload;
        state.validationErrors = {};
        state.touchedFields = {};
      })
      .addCase(createComplaint.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Failed to create complaint';
      })
      // Restore or Init
      .addCase(restoreOrInitComplaint.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(restoreOrInitComplaint.fulfilled, (state, action) => {
        state.loading = false;
        state.current = action.payload;
        // Do not display errors on fresh restore until user interacts or commits
        state.validationErrors = {};
        state.touchedFields = {};
      })
      .addCase(restoreOrInitComplaint.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Failed to initialize complaint session';
      })
      // Fetch
      .addCase(fetchComplaint.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchComplaint.fulfilled, (state, action) => {
        state.loading = false;
        state.current = action.payload;
      })
      .addCase(fetchComplaint.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? 'Failed to load complaint';
      })
      // Patch
      .addCase(patchComplaint.pending, (state) => {
        state.saving = true;
      })
      .addCase(patchComplaint.fulfilled, (state, action) => {
        state.saving = false;
        state.current = action.payload;
      })
      .addCase(patchComplaint.rejected, (state, action) => {
        state.saving = false;
        state.error = action.error.message ?? 'Failed to save';
      })
      // Commit
      .addCase(commitComplaint.pending, (state) => {
        state.committing = true;
      })
      .addCase(commitComplaint.fulfilled, (state, action) => {
        state.committing = false;
        state.current = action.payload;
        state.validationErrors = {};
      })
      .addCase(commitComplaint.rejected, (state, action) => {
        state.committing = false;
        state.error = action.error.message ?? 'Failed to commit';
      });
  },
});

export const {
  resetForm,
  setFieldLocally,
  setFieldTouched,
  validateForm,
  clearValidationError,
  markFieldFilled,
  clearFilledFields,
  applyAIExtraction,
  clearFormError,
} = complaintFormSlice.actions;

export default complaintFormSlice.reducer;
