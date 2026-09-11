import { configureStore } from '@reduxjs/toolkit';
import complaintFormReducer from './complaintFormSlice';
import copilotChatReducer from './copilotChatSlice';

export const store = configureStore({
  reducer: {
    complaintForm: complaintFormReducer,
    copilotChat: copilotChatReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      // Allow Sets in state (for justFilledFields)
      serializableCheck: {
        ignoredPaths: ['complaintForm.justFilledFields'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
